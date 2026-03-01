#!/usr/bin/env python3
from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate d2jsp forum page URL plan (offset paging by 25)")
    p.add_argument("--forum-id", type=int, default=271)
    p.add_argument("--pages", type=int, default=1000, help="How many pages to generate (25 topics per page)")
    p.add_argument("--start-page", type=int, default=1, help="1-based page number")
    p.add_argument(
        "--categories",
        default="",
        help="Comma-separated category ids (e.g. '2,3,4,5'). Empty = main forum pages",
    )
    p.add_argument(
        "--include-main",
        action="store_true",
        help="When categories are provided, also emit main forum pages",
    )
    return p.parse_args()


def iter_urls(forum_id: int, pages: int, start_page: int, category: int | None):
    start_offset = max(start_page - 1, 0) * 25
    for i in range(pages):
        offset = start_offset + i * 25
        if category is None:
            yield f"https://forums.d2jsp.org/forum.php?f={forum_id}&o={offset}"
        else:
            yield f"https://forums.d2jsp.org/forum.php?f={forum_id}&c={category}&o={offset}"


def main() -> int:
    args = parse_args()
    cats = [int(x) for x in args.categories.split(",") if x.strip()] if args.categories else []

    emitted = 0
    if not cats or args.include_main:
        for url in iter_urls(args.forum_id, args.pages, args.start_page, None):
            print(url)
            emitted += 1

    for cat in cats:
        for url in iter_urls(args.forum_id, args.pages, args.start_page, cat):
            print(url)
            emitted += 1

    print(f"# emitted={emitted}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

