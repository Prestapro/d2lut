#!/usr/bin/env python3
"""
Remote Overlay Server for D2R Magic Item Pricer.

This script runs on the gaming PC and:
1. Captures D2R game screen
2. Detects item tooltips using OCR
3. Prices items using d2lut pricing engine
4. Streams items via WebSocket to connected dashboard clients

Usage:
    python run_remote_overlay_server.py [--port 8765] [--host 0.0.0.0]

The server listens on all network interfaces (0.0.0.0) by default,
allowing connections from other devices on the same WiFi network.

To connect from another device:
1. Find gaming PC IP: open CMD, run `ipconfig`
2. On dashboard device: enter IP in Connection Settings
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from d2lut.overlay.websocket_server import WebSocketServer, DroppedItem
from d2lut.overlay.ground_scanner import GroundItemScanner

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RemoteOverlayServer:
    """Server that captures game screen and streams items to dashboard clients."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        """Initialize the remote overlay server.
        
        Args:
            host: Host to bind to (0.0.0.0 for all interfaces)
            port: WebSocket port
        """
        self.host = host
        self.port = port
        self.ws_server = WebSocketServer(host=host, port=port)
        self.scanner = GroundItemScanner()
        self.running = False
        
        # Demo mode - generates mock items periodically
        self.demo_mode = True
        self.demo_interval = 15.0  # seconds between demo items
        
    def start(self) -> None:
        """Start the server."""
        logger.info(f"Starting Remote Overlay Server on {self.host}:{self.port}")
        logger.info("=" * 60)
        logger.info("D2R Magic Item Pricer - Remote Overlay Server")
        logger.info("=" * 60)
        logger.info("")
        logger.info("To connect from another device on same WiFi:")
        logger.info("  1. Find this PC's IP address: open CMD, run 'ipconfig'")
        logger.info("  2. On dashboard device: open Live Dashboard tab")
        logger.info("  3. Enter the IP address in Connection Settings")
        logger.info("  4. Click Connect")
        logger.info("")
        logger.info("WebSocket URL: ws://<YOUR_IP>:%d", self.port)
        logger.info("=" * 60)
        
        self.ws_server.start()
        self.running = True
        
        # Start demo mode
        if self.demo_mode:
            logger.info("Running in DEMO mode - generating mock items every %.1f seconds", self.demo_interval)
            self._run_demo()
        
    def stop(self) -> None:
        """Stop the server."""
        logger.info("Stopping Remote Overlay Server...")
        self.running = False
        self.ws_server.stop()
        
    def _run_demo(self) -> None:
        """Run demo mode - generate mock items periodically."""
        import threading
        
        def demo_loop():
            item_index = 0
            while self.running:
                try:
                    # Generate mock items
                    mock_items = self.scanner.create_mock_items(8)
                    
                    # Send one item at a time
                    if item_index < len(mock_items):
                        item = mock_items[item_index]
                        logger.info("Demo: Sending item - %s (%.0f FG)", item.name, item.estimated_fg)
                        self.ws_server.broadcast_item(item)
                        item_index += 1
                    else:
                        # Reset and send all items
                        item_index = 0
                        for item in mock_items:
                            if not self.running:
                                break
                            logger.info("Demo: Sending item - %s (%.0f FG)", item.name, item.estimated_fg)
                            self.ws_server.broadcast_item(item)
                            time.sleep(0.5)  # Small delay between items
                    
                    # Wait before next batch
                    time.sleep(self.demo_interval)
                    
                except Exception as e:
                    logger.error("Demo loop error: %s", e)
                    time.sleep(1)
        
        thread = threading.Thread(target=demo_loop, daemon=True)
        thread.start()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="D2R Magic Item Pricer - Remote Overlay Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_remote_overlay_server.py
  python run_remote_overlay_server.py --port 9000
  python run_remote_overlay_server.py --host 192.168.1.100

To connect from another device:
  1. Run this server on gaming PC
  2. Find gaming PC IP: ipconfig (Windows) or ifconfig (Linux/Mac)
  3. On dashboard device: enter IP in Connection Settings
        """
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0 for all interfaces)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="WebSocket port (default: 8765)"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        default=True,
        help="Run in demo mode with mock items (default: True)"
    )
    parser.add_argument(
        "--no-demo",
        action="store_true",
        help="Disable demo mode (requires actual screen capture)"
    )
    
    args = parser.parse_args()
    
    server = RemoteOverlayServer(host=args.host, port=args.port)
    
    if args.no_demo:
        server.demo_mode = False
    
    try:
        server.start()
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        server.stop()


if __name__ == "__main__":
    main()
