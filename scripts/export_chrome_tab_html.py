#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path


APPLE_SCRIPT_EXPORT = r'''
on run argv
    set browserApp to "Google Chrome"
    set urlSubstr to ""
    if (count of argv) > 0 then set browserApp to item 1 of argv
    if (count of argv) > 1 then set urlSubstr to item 2 of argv

    tell application browserApp
        if (count of windows) = 0 then error browserApp & " has no windows"

        set targetTab to missing value
        set targetWin to missing value

        if urlSubstr is "" then
            set targetWin to front window
            set targetTab to active tab of targetWin
        else
            repeat with w in windows
                repeat with t in tabs of w
                    if (URL of t contains urlSubstr) then
                        set targetWin to w
                        set targetTab to t
                        exit repeat
                    end if
                end repeat
                if targetTab is not missing value then exit repeat
            end repeat

            if targetTab is missing value then error "No tab URL contains: " & urlSubstr
            set active tab index of targetWin to (index of targetTab)
            set index of targetWin to 1
            activate
        end if

        set pageURL to URL of active tab of front window
        set pageTitle to title of active tab of front window
        set pageHTML to execute active tab of front window javascript "document.documentElement.outerHTML"
        return pageURL & linefeed & pageTitle & linefeed & pageHTML
    end tell
end run
'''

APPLE_SCRIPT_LIST = r'''
on run argv
    set browserApp to "Google Chrome"
    if (count of argv) > 0 then set browserApp to item 1 of argv
    tell application browserApp
        if (count of windows) = 0 then return "NO_WINDOWS"
        set outLines to {}
        repeat with w in windows
            set widx to (index of w)
            repeat with t in tabs of w
                set lineText to (widx as string) & tab & (index of t as string) & tab & (title of t) & tab & (URL of t)
                copy lineText to end of outLines
            end repeat
        end repeat
        return outLines as string
    end tell
end run
'''



def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export HTML from a tab in the main Google Chrome browser")
    p.add_argument(
        "--url-contains",
        default="forums.d2jsp.org/forum.php?f=271",
        help="Find a Chrome tab whose URL contains this substring; empty string uses active tab",
    )
    p.add_argument(
        "--browser-app",
        default="Google Chrome",
        help='macOS application name (default: "Google Chrome")',
    )
    p.add_argument(
        "--out",
        default="data/raw/d2jsp/forum_271_from_chrome.html",
        help="Output HTML file path",
    )
    p.add_argument(
        "--print-meta",
        action="store_true",
        help="Print selected URL and title",
    )
    p.add_argument(
        "--list-tabs",
        action="store_true",
        help="List browser tabs (window index, tab index, title, URL) and exit",
    )
    p.add_argument(
        "--open-url-if-not-found",
        default=None,
        help="If target tab/window is missing, open/create a browser window and navigate to this URL",
    )
    p.add_argument(
        "--wait-seconds",
        type=float,
        default=0.0,
        help="Sleep before export (useful after auto-opening URL)",
    )
    return p.parse_args()


def run_osascript(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["osascript", "-", *args],
        input=script,
        text=True,
        capture_output=True,
    )


def list_tabs(browser_app: str) -> int:
    proc = run_osascript(APPLE_SCRIPT_LIST, browser_app)
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or "osascript failed"
        if "Executing JavaScript through AppleScript is turned off" in err:
            err += (
                "\nEnable it in Google Chrome: View > Developer > Allow JavaScript from Apple Events"
            )
        raise SystemExit(err)
    out = proc.stdout.strip()
    if out == "NO_WINDOWS":
        print("NO_WINDOWS")
        return 0
    print(out)
    return 0


def ensure_browser_window(browser_app: str, url: str | None) -> None:
    cmd = ["open", "-a", browser_app]
    if url:
        cmd.append(url)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or "failed to open browser window"
        raise SystemExit(err)


def main() -> int:
    args = parse_args()
    if args.list_tabs:
        return list_tabs(args.browser_app)

    proc = run_osascript(APPLE_SCRIPT_EXPORT, args.browser_app, args.url_contains)
    if proc.returncode != 0 and args.open_url_if_not_found:
        ensure_browser_window(args.browser_app, args.open_url_if_not_found)
        if args.wait_seconds > 0:
            time.sleep(args.wait_seconds)
        proc = run_osascript(APPLE_SCRIPT_EXPORT, args.browser_app, args.url_contains)
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or "osascript failed"
        raise SystemExit(err)

    payload = proc.stdout
    parts = payload.split("\n", 2)
    if len(parts) < 3:
        raise SystemExit("Unexpected AppleScript output (expected URL, title, HTML)")
    page_url, page_title, html_text = parts[0], parts[1], parts[2]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_text, encoding="utf-8")

    if args.print_meta:
        print(f"url={page_url}")
        print(f"title={page_title}")
        if "cloudflare" in html_text.lower() or "just a moment" in html_text.lower():
            print("warning=exported page looks like Cloudflare challenge, not forum content")
    print(f"wrote html to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
