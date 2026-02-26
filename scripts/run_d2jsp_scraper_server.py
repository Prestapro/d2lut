#!/usr/bin/env python3
"""
Python server to receive scraped HTML from the Tampermonkey script and save it to disk.
Also serves the next URL from the queue it maintains.
"""
import http.server
import json
import logging
import os
import socketserver
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import argparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def get_expected_info(url, forum_dir: Path, topic_dir: Path):
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    
    filename = None
    save_dir = None
    
    if 'forum.php' in parsed.path:
        save_dir = forum_dir
        f = qs.get('f', [''])[0]
        c = qs.get('c', [''])[0]
        o = qs.get('o', ['0'])[0]
        if f:
            if c:
                filename = f"forum_f{f}_c{c}_o{o}.html"
            else:
                filename = f"forum_f{f}_o{o}.html"
    elif 'topic.php' in parsed.path:
        save_dir = topic_dir
        t = qs.get('t', [''])[0]
        f = qs.get('f', [''])[0]
        o = qs.get('o', ['0'])[0]
        if t:
            if o and o != '0':
                filename = f"topic_t{t}_f{f}_o{o}.html" if f else f"topic_t{t}_o{o}.html"
            else:
                filename = f"topic_t{t}_f{f}.html" if f else f"topic_t{t}.html"
                
    return save_dir, filename

class ScraperHandler(http.server.SimpleHTTPRequestHandler):
    server_state = None

    def log_message(self, format, *args):
        # Mute standard HTTP logs to keep console clean
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_GET(self):
        if self.path == '/next':
            self._handle_next()
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path == '/save':
            self._handle_save()
        else:
            self.send_error(404, "Not Found")

    def _handle_next(self):
        self.send_response(200)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        state = self.server_state
        
        response_data = {"url": None, "remaining": len(state['queue'])}
        if state['queue']:
            response_data["url"] = state['queue'][0]
        
        self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def _handle_save(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body)
            url = data.get('url')
            html = data.get('html')
            
            if not url or not html:
                self.send_error(400, "Missing url or html")
                return

            state = self.server_state
            
            save_dir, filename = get_expected_info(url, state['forum_dir'], state['topic_dir'])
            
            if not filename or not save_dir:
                logging.warning(f"Could not determine filename for URL: {url}, creating fallback name.")
                filename = f"unknown_{int(time.time())}.html"
                save_dir = state['forum_dir']
                
            save_path = save_dir / filename
            save_dir.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(html)
                
            logging.info(f"Saved: {filename} ({len(html)//1024} KB)")
            
            # Remove from queue if it matches the front of the queue
            queue_popped = False
            if state['queue'] and state['queue'][0] == url:
                state['queue'].pop(0)
                queue_popped = True
            
            self.send_response(200)
            self._send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            self.wfile.write(json.dumps({"status": "success", "remaining": len(state['queue'])}).encode('utf-8'))
            
        except Exception as e:
            logging.error(f"Error handling save: {e}")
            self.send_error(500, "Internal Server Error")

def parse_args():
    parser = argparse.ArgumentParser(description="Local HTTP server for Tampermonkey batch web scraper.")
    parser.add_argument("--url-file", default=None, help="File containing list of URLs to scrape line by line")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    parser.add_argument("--forum-dir", default="data/raw/d2jsp/forum_pages", help="Directory to save forum pages")
    parser.add_argument("--topic-dir", default="data/raw/d2jsp/topic_pages", help="Directory to save topic pages")
    return parser.parse_args()

def main():
    args = parse_args()
    
    forum_dir = Path(args.forum_dir)
    topic_dir = Path(args.topic_dir)
    
    urls = []
    if args.url_file:
        try:
            with open(args.url_file, 'r', encoding='utf-8') as f:
                raw_urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                
            # Filter already loaded URLs
            for url in raw_urls:
                d, name = get_expected_info(url, forum_dir, topic_dir)
                if d and name and (d / name).exists():
                    # Skip if already downloaded
                    pass
                else:
                    urls.append(url)
                    
            logging.info(f"Loaded {len(urls)} pending URLs from {args.url_file} (skipped {len(raw_urls)-len(urls)} already saved)")
        except Exception as e:
            logging.error(f"Failed to load URL file: {e}")
            return 1
            
    state = {
        'queue': urls,
        'forum_dir': forum_dir,
        'topic_dir': topic_dir
    }
    
    ScraperHandler.server_state = state
    
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", args.port), ScraperHandler) as httpd:
        logging.info(f"Listening on http://127.0.0.1:{args.port}")
        logging.info(f"Saving forum pages to: {args.forum_dir}")
        logging.info(f"Saving topic pages to: {args.topic_dir}")
        if not urls:
            logging.warning("No URLs provided. The scraper will just save any POSTed pages.")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logging.info("\nShutting down server...")

if __name__ == "__main__":
    raise SystemExit(main())
