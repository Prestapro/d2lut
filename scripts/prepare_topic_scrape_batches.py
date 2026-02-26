#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path
from urllib.parse import parse_qs, urlparse


_CHARM_TERMS = (
    "charm",
    "skiller",
    "gc",
    "sc ",
    " small charm",
    " grand charm",
    " gheed",
    "gheed's",
    "sunder",
)
_LLD_TERMS = (
    "lld",
    "low lvl",
    "low level duel",
    "2/20",
    "circlet",
    "diadem",
    "jewel",
    "ring",
    "ammy",
    "amulet",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Split topic candidate URLs into scrape-ready batches")
    p.add_argument("--db", default="data/cache/d2lut.db")
    p.add_argument("--in-file", required=True, help="Input file with topic.php URLs (one per line)")
    p.add_argument("--topic-dir", default="data/raw/d2jsp/topic_pages")
    p.add_argument("--out-prefix", default="data/cache/topic_candidates_batch")
    p.add_argument("--forum-id", type=int, default=271)
    return p.parse_args()


def topic_id_from_url(url: str) -> int | None:
    try:
        qs = parse_qs(urlparse(url).query)
        t = (qs.get("t") or [None])[0]
        return int(t) if t else None
    except Exception:
        return None


def existing_topic_ids(topic_dir: Path) -> set[int]:
    ids: set[int] = set()
    for path in topic_dir.glob("topic_t*_f*.html"):
        m = re.search(r"topic_t(\d+)_f\d+\.html$", path.name)
        if m:
            ids.add(int(m.group(1)))
            continue
        m = re.search(r"topic_t(\d+)_f\d+_o\d+\.html$", path.name)
        if m:
            ids.add(int(m.group(1)))
    # fallback for broader naming variants
    for path in topic_dir.glob("topic_t*.html"):
        m = re.search(r"topic_t(\d+)", path.name)
        if m:
            ids.add(int(m.group(1)))
    return ids


def load_thread_titles(db_path: Path, forum_id: int) -> dict[int, str]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT thread_id, title
            FROM threads
            WHERE source='d2jsp' AND forum_id=?
            """,
            (forum_id,),
        ).fetchall()
        return {int(r["thread_id"]): str(r["title"] or "") for r in rows if r["thread_id"] is not None}
    finally:
        conn.close()


def classify_title(title: str) -> str:
    t = f" {title.lower()} "
    has_charm = any(term in t for term in _CHARM_TERMS)
    has_lld = any(term in t for term in _LLD_TERMS)
    if has_charm and has_lld:
        return "mixed"
    if has_charm:
        return "charms"
    if has_lld:
        return "lld"
    return "other"


def write_urls(path: Path, urls: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{u}\n" for u in urls), encoding="utf-8")


def main() -> int:
    args = parse_args()
    in_file = Path(args.in_file)
    topic_dir = Path(args.topic_dir)
    db_path = Path(args.db)
    out_prefix = Path(args.out_prefix)

    urls = [line.strip() for line in in_file.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    seen_topic_ids = existing_topic_ids(topic_dir)
    titles = load_thread_titles(db_path, args.forum_id)

    unseen: list[str] = []
    by_bucket: dict[str, list[str]] = {"charms": [], "lld": [], "mixed": [], "other": []}

    malformed = 0
    already = 0
    missing_title = 0

    for url in urls:
        tid = topic_id_from_url(url)
        if tid is None:
            malformed += 1
            continue
        if tid in seen_topic_ids:
            already += 1
            continue
        unseen.append(url)
        title = titles.get(tid, "")
        if not title:
            missing_title += 1
        bucket = classify_title(title)
        by_bucket[bucket].append(url)

    write_urls(out_prefix.with_name(out_prefix.name + "_unseen.txt"), unseen)
    for bucket, bucket_urls in by_bucket.items():
        write_urls(out_prefix.with_name(out_prefix.name + f"_{bucket}.txt"), bucket_urls)

    print(f"input_urls={len(urls)}")
    print(f"already_downloaded={already}")
    print(f"malformed={malformed}")
    print(f"unseen={len(unseen)}")
    print(f"missing_title={missing_title}")
    for bucket in ("charms", "lld", "mixed", "other"):
        print(f"{bucket}={len(by_bucket[bucket])}")
    print(f"wrote={out_prefix.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

