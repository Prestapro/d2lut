#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _thread_id_from_url(url: str) -> int:
    qs = parse_qs(urlparse(url).query)
    vals = qs.get("t") or []
    if not vals:
        raise ValueError("URL must contain ?t=<thread_id>")
    return int(vals[0])


def _find_topic_html(out_dir: Path, thread_id: int) -> Path | None:
    matches = sorted(out_dir.glob(f"topic_t{thread_id}*.html"))
    return matches[0] if matches else None


def main() -> int:
    p = argparse.ArgumentParser(
        description="Fetch one d2jsp topic via separate Chrome profile and OCR the first body image"
    )
    p.add_argument("--url", required=True, help="Full d2jsp topic URL (topic.php?t=...&f=...)")
    p.add_argument("--out-dir", default="data/raw/d2jsp/topic_pages", help="Topic HTML output dir")
    p.add_argument(
        "--profile-dir",
        default="data/cache/playwright-d2jsp-profile-alt",
        help="Separate Playwright profile dir (avoid SingletonLock with bulk fetch)",
    )
    p.add_argument("--manual-start", action="store_true", default=True, help="Pause for Cloudflare/login (default: on)")
    p.add_argument("--no-manual-start", dest="manual_start", action="store_false")
    p.add_argument("--skip-fetch", action="store_true", help="Assume topic HTML already exists locally")
    p.add_argument("--ocr-engine", default="pytesseract", choices=["pytesseract", "easyocr"])
    p.add_argument("--ocr-confidence-threshold", type=float, default=0.25)
    p.add_argument("--download-dir", default="data/raw/d2jsp/topic_images_manual", help="Where to save first body image")
    args = p.parse_args()

    url = args.url.strip()
    thread_id = _thread_id_from_url(url)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.skip_fetch:
        # Write a tiny temp URL file so we don't depend on shell process substitution.
        tmp_url_file = out_dir / f"_single_topic_{thread_id}.txt"
        tmp_url_file.write_text(url + "\n", encoding="utf-8")
        cmd = [
            sys.executable,
            "scripts/fetch_d2jsp_topic_pages.py",
            "--url-file",
            str(tmp_url_file),
            "--out-dir",
            str(out_dir),
            "--profile-dir",
            args.profile_dir,
            "--skip-existing",
            "--delay-ms",
            "200",
            "--retries",
            "2",
            "--limit",
            "1",
        ]
        if args.manual_start:
            cmd.append("--manual-start")
        else:
            cmd.append("--no-manual-start")
        try:
            r = subprocess.run(cmd, check=False)
        finally:
            try:
                tmp_url_file.unlink()
            except OSError:
                pass
        if r.returncode != 0:
            print(f"ERROR: fetch step failed (exit={r.returncode})")
            return r.returncode

    topic_html = _find_topic_html(out_dir, thread_id)
    if topic_html is None:
        print(f"ERROR: topic HTML not found after fetch for thread_id={thread_id} in {out_dir}")
        return 5

    inspect_cmd = [
        sys.executable,
        "scripts/inspect_topic_first_body_image.py",
        "--topic-html",
        str(topic_html),
        "--download-dir",
        args.download_dir,
        "--ocr-engine",
        args.ocr_engine,
        "--ocr-confidence-threshold",
        str(args.ocr_confidence_threshold),
    ]
    # Ensure local src imports work for OCR + normalizer.
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = "src" if not prev else f"src:{prev}"
    r2 = subprocess.run(inspect_cmd, env=env, check=False)
    return r2.returncode


if __name__ == "__main__":
    raise SystemExit(main())
