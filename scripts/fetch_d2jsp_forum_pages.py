#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch d2jsp forum pages via Playwright and save HTML snapshots")
    p.add_argument("--forum-id", type=int, default=271)
    p.add_argument("--pages", type=int, default=1000, help="Number of pages (25 topics each)")
    p.add_argument("--start-page", type=int, default=1, help="1-based page number")
    p.add_argument("--categories", default="", help="Comma-separated category ids (e.g. 2,3,4,5)")
    p.add_argument(
        "--category-page-limits",
        default="",
        help="Per-category page limits, e.g. '4:10,3:100,5:20' (overrides --pages for listed categories)",
    )
    p.add_argument("--include-main", action="store_true", default=True, help="Include main forum pages")
    p.add_argument("--no-include-main", dest="include_main", action="store_false")
    p.add_argument("--out-dir", default="data/raw/d2jsp/forum_pages")
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
    return p.parse_args()


def parse_category_page_limits(raw: str) -> dict[int, int]:
    out: dict[int, int] = {}
    if not raw.strip():
        return out
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"invalid category page limit {part!r} (expected c:pages)")
        c_raw, pages_raw = part.split(":", 1)
        c = int(c_raw.strip())
        n = int(pages_raw.strip())
        if n < 0:
            raise ValueError(f"negative page limit for category {c}: {n}")
        out[c] = n
    return out


def iter_targets(
    forum_id: int,
    pages: int,
    start_page: int,
    categories: list[int],
    include_main: bool,
    category_page_limits: dict[int, int] | None = None,
):
    category_page_limits = category_page_limits or {}
    start_offset = max(start_page - 1, 0) * 25
    if include_main or not categories:
        for i in range(pages):
            o = start_offset + i * 25
            yield (None, o, f"https://forums.d2jsp.org/forum.php?f={forum_id}&o={o}")
    for c in categories:
        cat_pages = category_page_limits.get(c, pages)
        for i in range(cat_pages):
            o = start_offset + i * 25
            yield (c, o, f"https://forums.d2jsp.org/forum.php?f={forum_id}&c={c}&o={o}")


def output_name(forum_id: int, category: int | None, offset: int) -> str:
    if category is None:
        return f"forum_f{forum_id}_o{offset}.html"
    return f"forum_f{forum_id}_c{category}_o{offset}.html"


def page_looks_valid(html: str, title: str) -> bool:
    h = html.lower()
    t = (title or "").lower()
    if "just a moment" in t or "cloudflare" in h:
        return False
    return "d2jsp" in t and "topic.php?t=" in h


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = Path(args.profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)
    categories = [int(x) for x in args.categories.split(",") if x.strip()] if args.categories else []
    category_page_limits = parse_category_page_limits(args.category_page_limits)

    total = saved = skipped = failed = 0
    failures: list[str] = []
    exhausted_categories: set[int] = set()

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

        start_url = f"https://forums.d2jsp.org/forum.php?f={args.forum_id}"
        page.goto(start_url, wait_until="domcontentloaded")

        if args.manual_start:
            print("Browser opened. Log in / pass Cloudflare in this browser window, open the target forum, then press Enter here.")
            input()

        for category, offset, url in iter_targets(
            args.forum_id,
            args.pages,
            args.start_page,
            categories,
            args.include_main,
            category_page_limits,
        ):
            if category is not None and category in exhausted_categories:
                continue
            total += 1
            out_path = out_dir / output_name(args.forum_id, category, offset)
            if args.skip_existing and out_path.exists() and out_path.stat().st_size > 1000:
                skipped += 1
                continue

            ok = False
            last_err = ""
            for attempt in range(1, args.retries + 2):
                try:
                    page.goto(url, wait_until="domcontentloaded")
                    page.wait_for_timeout(300)
                    title = page.title()
                    html = page.content()
                    if not page_looks_valid(html, title):
                        last_err = f"invalid page (title={title!r})"
                        page.wait_for_timeout(1000)
                        continue
                    out_path.write_text(html, encoding="utf-8")
                    saved += 1
                    ok = True
                    print(f"[{total}] saved {out_path.name} ({len(html)} bytes)")
                    break
                except PlaywrightTimeoutError as e:
                    last_err = f"timeout: {e}"
                except Exception as e:  # keep crawling
                    last_err = str(e)
                page.wait_for_timeout(1000)

            if not ok:
                failed += 1
                msg = f"{url} :: {last_err}"
                failures.append(msg)
                print(f"[{total}] FAILED {msg}")
                # Category pages can legitimately end early (e.g. short LLD category).
                # Stop crawling that category after the first confirmed invalid page.
                if category is not None and last_err.startswith("invalid page"):
                    exhausted_categories.add(category)
                    print(f"[{total}] stopping category c={category} after invalid page at offset={offset}")

            if args.delay_ms > 0:
                page.wait_for_timeout(args.delay_ms)

        fail_log = out_dir / "_fetch_failures.txt"
        if failures:
            fail_log.write_text("\n".join(failures) + "\n", encoding="utf-8")
            print(f"Wrote failures to {fail_log}")

        print(f"Done. total={total} saved={saved} skipped={skipped} failed={failed} out={out_dir}")
        ctx.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
