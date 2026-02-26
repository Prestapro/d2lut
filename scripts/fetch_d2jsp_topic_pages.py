#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch d2jsp topic pages via Playwright and save HTML snapshots")
    p.add_argument("--url-file", required=True, help="File with topic.php URLs (one per line)")
    p.add_argument("--out-dir", default="data/raw/d2jsp/topic_pages")
    p.add_argument("--profile-dir", default="data/cache/playwright-d2jsp-profile")
    p.add_argument("--channel", default="chrome", help="Playwright browser channel (default: chrome)")
    p.add_argument("--headless", action="store_true", help="Headless mode (not recommended for Cloudflare)")
    p.add_argument("--timeout-ms", type=int, default=30000)
    p.add_argument("--delay-ms", type=int, default=1200, help="Delay between page saves")
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--skip-existing", action="store_true", default=True)
    p.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    p.add_argument("--manual-start", action="store_true", default=True, help="Pause for manual Cloudflare/login before crawl")
    p.add_argument("--no-manual-start", dest="manual_start", action="store_false")
    p.add_argument("--limit", type=int, default=0, help="Optional max URLs to process (0 = all)")
    return p.parse_args()


def _normalize_url_line(line: str) -> str | None:
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    # Accept plain URL or tab-separated rows where URL is one of the fields.
    if s.startswith("http://") or s.startswith("https://"):
        return s.split()[0]
    for part in s.split("\t"):
        part = part.strip()
        if part.startswith("http://") or part.startswith("https://"):
            return part
    return None


def load_urls(path: Path, limit: int = 0) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        url = _normalize_url_line(line)
        if not url or "topic.php" not in url:
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
        if limit > 0 and len(urls) >= limit:
            break
    return urls


def topic_output_name(url: str) -> str | None:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "topic.php" not in parsed.path:
        return None
    t = (qs.get("t") or [None])[0]
    f = (qs.get("f") or [None])[0]
    o = (qs.get("o") or ["0"])[0]
    if not t:
        return None
    if o and o != "0":
        return f"topic_t{t}_f{f}_o{o}.html" if f else f"topic_t{t}_o{o}.html"
    return f"topic_t{t}_f{f}.html" if f else f"topic_t{t}.html"


def topic_page_looks_valid(html: str, title: str) -> bool:
    h = html.lower()
    t = (title or "").lower()
    if "just a moment" in t or "cloudflare" in h:
        return False
    if "d2jsp" not in t:
        return False
    # Titles for valid topic pages usually end with "- Topic - d2jsp".
    if " topic - d2jsp" in t:
        return True
    # Fallback HTML heuristic for pages with unusual titles.
    return "topic.php?t=" in h


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = Path(args.profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)

    urls = load_urls(Path(args.url_file), limit=args.limit)
    if not urls:
        print(f"No topic URLs found in {args.url_file}")
        return 1

    total = saved = skipped = failed = 0
    failures: list[str] = []

    with sync_playwright() as p:
        browser_type = p.chromium
        ctx = browser_type.launch_persistent_context(
            str(profile_dir),
            channel=args.channel,
            headless=args.headless,
            viewport={"width": 1400, "height": 1000},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(args.timeout_ms)

        page.goto("https://forums.d2jsp.org/", wait_until="domcontentloaded")
        if args.manual_start:
            print("Browser opened. Log in / pass Cloudflare in this browser window, then press Enter here.")
            input()

        for url in urls:
            total += 1
            name = topic_output_name(url)
            if not name:
                failed += 1
                failures.append(f"{url} :: cannot derive topic output filename")
                print(f"[{total}] FAILED {url} :: cannot derive topic output filename")
                continue

            out_path = out_dir / name
            if args.skip_existing and out_path.exists() and out_path.stat().st_size > 1000:
                skipped += 1
                continue

            ok = False
            last_err = ""
            for _attempt in range(args.retries + 1):
                try:
                    page.goto(url, wait_until="domcontentloaded")
                    page.wait_for_timeout(300)
                    title = page.title()
                    html = page.content()
                    if not topic_page_looks_valid(html, title):
                        last_err = f"invalid topic page (title={title!r})"
                        page.wait_for_timeout(1000)
                        continue
                    out_path.write_text(html, encoding="utf-8")
                    saved += 1
                    ok = True
                    print(f"[{total}] saved {out_path.name} ({len(html)} bytes)")
                    break
                except PlaywrightTimeoutError as e:
                    last_err = f"timeout: {e}"
                except Exception as e:
                    last_err = str(e)
                page.wait_for_timeout(1000)

            if not ok:
                failed += 1
                msg = f"{url} :: {last_err}"
                failures.append(msg)
                print(f"[{total}] FAILED {msg}")

            if args.delay_ms > 0:
                page.wait_for_timeout(args.delay_ms)

        if failures:
            fail_log = out_dir / "_fetch_topic_failures.txt"
            fail_log.write_text("\n".join(failures) + "\n", encoding="utf-8")
            print(f"Wrote failures to {fail_log}")

        print(f"Done. total={total} saved={saved} skipped={skipped} failed={failed} out={out_dir}")
        ctx.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
