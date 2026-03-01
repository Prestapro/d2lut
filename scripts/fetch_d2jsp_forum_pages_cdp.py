#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch d2jsp forum pages via CDP from an already-open Chrome session")
    p.add_argument("--cdp-url", default="http://127.0.0.1:9222", help="Chrome remote debugging endpoint")
    p.add_argument("--forum-id", type=int, default=271)
    p.add_argument("--pages", type=int, default=1000)
    p.add_argument("--start-page", type=int, default=1)
    p.add_argument("--categories", default="", help="Comma-separated category ids (e.g. 2,3,4,5)")
    p.add_argument(
        "--category-page-limits",
        default="",
        help="Per-category page limits, e.g. '4:10,3:100,5:20' (overrides --pages for listed categories)",
    )
    p.add_argument("--include-main", action="store_true", default=True)
    p.add_argument("--no-include-main", dest="include_main", action="store_false")
    p.add_argument("--out-dir", default="data/raw/d2jsp/forum_pages")
    p.add_argument("--delay-ms", type=int, default=800)
    p.add_argument("--timeout-ms", type=int, default=30000)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--skip-existing", action="store_true", default=True)
    p.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    p.add_argument("--manual-start", action="store_true", default=True, help="Pause and wait for Enter before crawling")
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


def looks_like_valid_forum(html: str, title: str) -> bool:
    h = html.lower()
    t = (title or "").lower()
    if "just a moment" in t or "cloudflare" in h:
        return False
    return "d2jsp" in t and "topic.php?t=" in h and "forum.php?f=" in h


def choose_page(browser, forum_id: int):
    for context in browser.contexts:
        for page in context.pages:
            try:
                u = page.url or ""
            except Exception:
                continue
            if "forums.d2jsp.org" in u and f"f={forum_id}" in u:
                return page
    # fallback: reuse first page if any
    for context in browser.contexts:
        if context.pages:
            return context.pages[0]
    # create new page in first context
    if not browser.contexts:
        raise RuntimeError("No browser contexts found in connected Chrome")
    return browser.contexts[0].new_page()


def main() -> int:
    args = parse_args()
    categories = [int(x) for x in args.categories.split(",") if x.strip()] if args.categories else []
    category_page_limits = parse_category_page_limits(args.category_page_limits)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp_url)
        page = choose_page(browser, args.forum_id)
        page.set_default_timeout(args.timeout_ms)

        print(f"Connected to Chrome via CDP: {args.cdp_url}")
        print(f"Using tab: {page.url}")
        if args.manual_start:
            print(
                f"Open/log in/pass Cloudflare in this tab (or navigate to f={args.forum_id}) and press Enter to start crawl..."
            )
            input()

        total = saved = skipped = failed = 0
        failures: list[str] = []
        exhausted_categories: set[int] = set()
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
            for _attempt in range(args.retries + 1):
                try:
                    page.goto(url, wait_until="domcontentloaded")
                    page.wait_for_timeout(250)
                    title = page.title()
                    html = page.content()
                    if not looks_like_valid_forum(html, title):
                        last_err = f"invalid page title={title!r}"
                        page.wait_for_timeout(1200)
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
                page.wait_for_timeout(800)

            if not ok:
                failed += 1
                failures.append(f"{url}\t{last_err}")
                print(f"[{total}] FAILED {url} :: {last_err}")
                if category is not None and str(last_err).startswith("invalid page"):
                    exhausted_categories.add(category)
                    print(f"[{total}] stopping category c={category} after invalid page at offset={offset}")

            if args.delay_ms > 0:
                page.wait_for_timeout(args.delay_ms)

        if failures:
            fail_log = out_dir / "_fetch_failures.txt"
            fail_log.write_text("\n".join(failures) + "\n", encoding="utf-8")
            print(f"Wrote failures: {fail_log}")

        print(f"Done. total={total} saved={saved} skipped={skipped} failed={failed} out={out_dir}")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
