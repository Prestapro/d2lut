#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html as html_lib
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


def _safe_ext_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
        if path.endswith(ext):
            return ext
    return ".img"


def _title_from_html(html_text: str) -> str:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html_text)
    if not m:
        return ""
    return html_lib.unescape(re.sub(r"\s+", " ", m.group(1))).strip()


def _thread_id_from_name_or_html(topic_html: Path, html_text: str) -> int | None:
    m = re.search(r"topic_t(\d+)", topic_html.name)
    if m:
        return int(m.group(1))
    m = re.search(r"topic\.php\?(?:[^\"'>]*&)?t=(\d+)", html_text)
    if m:
        return int(m.group(1))
    return None


def _download(url: str, out_path: Path, timeout_sec: float = 20.0) -> None:
    opener = urllib.request.build_opener()
    opener.addheaders = [("User-Agent", "Mozilla/5.0 (compatible; d2lut-topic-inspector/0.1)")]
    with opener.open(url, timeout=timeout_sec) as resp:
        out_path.write_bytes(resp.read())


def main() -> int:
    p = argparse.ArgumentParser(description="Inspect first body image in a saved d2jsp topic HTML and OCR it")
    p.add_argument("--topic-html", required=True, help="Path to saved topic_t*.html file")
    p.add_argument("--download-dir", default="data/raw/d2jsp/topic_images_manual", help="Where to save the image")
    p.add_argument("--ocr-engine", default="pytesseract", choices=["pytesseract", "easyocr"])
    p.add_argument("--ocr-confidence-threshold", type=float, default=0.25)
    p.add_argument("--skip-download", action="store_true", help="Do not download image; just print URL")
    p.add_argument("--skip-ocr", action="store_true", help="Do not OCR image; just print URL/path")
    args = p.parse_args()

    topic_html = Path(args.topic_html)
    if not topic_html.exists():
        print(f"ERROR: topic HTML not found: {topic_html}")
        return 2

    # Reuse the same body-image extraction logic as the image recovery queue.
    try:
        from scripts.enqueue_topic_image_recovery import extract_body_images_from_html
    except Exception:
        # Fallback import when invoked as `python scripts/...` with cwd repo root
        sys.path.insert(0, str(Path.cwd()))
        from scripts.enqueue_topic_image_recovery import extract_body_images_from_html

    html_text = topic_html.read_text(encoding="utf-8", errors="ignore")
    title = _title_from_html(html_text)
    imgs = extract_body_images_from_html(html_text)
    if not imgs:
        print(f"title={title!r}")
        print("first_body_image_url=")
        print("result=no_body_image_found")
        return 0

    first = imgs[0]
    print(f"title={title!r}")
    print(f"first_body_image_post_id={first.post_id if first.post_id is not None else -1}")
    print(f"first_body_image_url={first.image_url}")

    out_path = None
    if not args.skip_download:
        out_dir = Path(args.download_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        tid = _thread_id_from_name_or_html(topic_html, html_text) or 0
        pid = first.post_id if first.post_id is not None else -1
        out_path = out_dir / f"topic_t{tid}_p{pid}_first{_safe_ext_from_url(first.image_url)}"
        _download(first.image_url, out_path)
        print(f"downloaded_image={out_path}")

    if args.skip_ocr:
        return 0
    if out_path is None:
        print("ERROR: OCR requires downloaded image (omit --skip-download)")
        return 3

    try:
        from d2lut.overlay.ocr_parser import OCRTooltipParser, TooltipCoords
        from d2lut.normalize.d2jsp_market import normalize_item_hint
        from PIL import Image
    except Exception as e:
        print(f"ERROR: OCR dependencies/imports unavailable: {e}")
        return 4

    parser = OCRTooltipParser(engine=args.ocr_engine, confidence_threshold=args.ocr_confidence_threshold)
    image_bytes = out_path.read_bytes()
    with Image.open(out_path) as im:
        w, h = im.size
    parsed = parser.parse_tooltip(image_bytes, TooltipCoords(x=0, y=0, width=w, height=h))
    raw_text = (parsed.raw_text or "").strip()
    item_name = (parsed.item_name or "").strip()
    hint = None
    if item_name:
        hint = normalize_item_hint(item_name)
    if hint is None and raw_text:
        hint = normalize_item_hint(raw_text[:300])
    variant_hint = hint[1] if hint else ""
    canonical_hint = hint[0] if hint else ""

    print(f"ocr_confidence={parsed.confidence:.4f}")
    print(f"ocr_item_name={item_name!r}")
    print(f"ocr_canonical_hint={canonical_hint}")
    print(f"ocr_variant_hint={variant_hint}")
    print(f"ocr_error={parsed.error!r}")
    print("ocr_raw_text_begin")
    print(raw_text[:2000])
    print("ocr_raw_text_end")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
