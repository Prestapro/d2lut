#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from pathlib import Path

from export_property_price_table_html import extract_props, props_signature


def main() -> int:
    p = argparse.ArgumentParser(
        description="Report market coverage by price threshold (variant coverage vs property-signature coverage)"
    )
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--min-fg", type=float, default=300.0, help="Minimum observed FG (default: 300)")
    p.add_argument("--top", type=int, default=25, help="Top missing variants to print")
    p.add_argument(
        "--premium-threshold",
        type=float,
        default=0.5,
        help="Include extra variants when estimate >= baseline * (1 + threshold). Default 0.5 = +50%%",
    )
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, source, variant_key, price_fg, signal_kind, source_kind,
                   COALESCE(raw_excerpt, '') AS raw_excerpt,
                   COALESCE(source_url, '') AS source_url
            FROM observed_prices
            WHERE market_key = ? AND price_fg >= ?
            ORDER BY price_fg DESC, id DESC
            """,
            (args.market_key, args.min_fg),
        ).fetchall()
    finally:
        conn.close()

    by_variant_total: Counter[str] = Counter()
    by_variant_sig: Counter[str] = Counter()
    by_variant_no_sig: Counter[str] = Counter()
    example_by_variant: dict[str, tuple[float, str, str]] = {}

    rows_with_sig = 0
    rows_without_sig = 0

    for r in rows:
        variant = str(r["variant_key"] or "")
        by_variant_total[variant] += 1
        excerpt = str(r["raw_excerpt"] or "").strip()
        sig = None
        if excerpt:
            sig = props_signature(extract_props(excerpt, variant))
        if sig:
            rows_with_sig += 1
            by_variant_sig[variant] += 1
            continue
        rows_without_sig += 1
        by_variant_no_sig[variant] += 1
        example_by_variant.setdefault(
            variant,
            (float(r["price_fg"] or 0), excerpt[:180], str(r["source_url"] or "")),
        )

    title_obs = sum(1 for r in rows if (r["source_kind"] or "") == "title")
    post_obs = sum(1 for r in rows if (r["source_kind"] or "") == "post")
    image_ocr_obs = sum(1 for r in rows if str(r["source"] or "").startswith("image_ocr_candidate:"))
    sig_groups = set()
    for r in rows:
        excerpt = str(r["raw_excerpt"] or "").strip()
        if not excerpt:
            continue
        sig = props_signature(extract_props(excerpt, str(r["variant_key"] or "")))
        if sig:
            sig_groups.add(sig)

    print(f"market={args.market_key} min_fg>={args.min_fg:g}")
    print(
        "observations="
        f"{len(rows)} variants={len(by_variant_total)} title_obs={title_obs} post_obs={post_obs} "
        f"image_ocr_obs={image_ocr_obs}"
    )
    print(
        "property_sig_rows="
        f"{rows_with_sig} property_sig_groups={len(sig_groups)} "
        f"property_sig_coverage={round(100 * rows_with_sig / max(len(rows), 1), 1)}%"
    )

    # Item + premium-variant coverage summary (user-facing market table policy):
    # include one baseline row per canonical item with demand, plus variants with
    # a significant premium versus the cheapest estimated variant.
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        est_rows = conn.execute(
            """
            WITH canon AS (
              SELECT market_key, variant_key,
                     COALESCE(MAX(NULLIF(canonical_item_id,'')), variant_key) AS canonical_item_id,
                     COUNT(*) AS obs_total
              FROM observed_prices
              WHERE market_key = ?
              GROUP BY market_key, variant_key
            )
            SELECT pe.variant_key, pe.estimate_fg,
                   COALESCE(c.canonical_item_id, pe.variant_key) AS canonical_item_id,
                   COALESCE(c.obs_total, 0) AS obs_total
            FROM price_estimates pe
            LEFT JOIN canon c
              ON c.market_key = pe.market_key
             AND c.variant_key = pe.variant_key
            WHERE pe.market_key = ? AND pe.estimate_fg IS NOT NULL
            """,
            (args.market_key, args.market_key),
        ).fetchall()
    finally:
        conn.close()

    by_item: dict[str, list[sqlite3.Row]] = {}
    for r in est_rows:
        by_item.setdefault(str(r["canonical_item_id"] or r["variant_key"] or ""), []).append(r)
    selected_rows = 0
    selected_items = 0
    premium_rows = 0
    premium_multiplier = 1.0 + max(args.premium_threshold, 0.0)
    for item, variants in by_item.items():
        demanded = [v for v in variants if int(v["obs_total"] or 0) > 0]
        if not demanded:
            continue
        selected_items += 1
        selected_rows += 1  # baseline row
        baseline = min(demanded, key=lambda v: float(v["estimate_fg"] or 0))
        base_price = float(baseline["estimate_fg"] or 0)
        for v in demanded:
            if str(v["variant_key"]) == str(baseline["variant_key"]):
                continue
            if float(v["estimate_fg"] or 0) >= base_price * premium_multiplier:
                selected_rows += 1
                premium_rows += 1
    print(
        "item_plus_premium_variant_rows="
        f"{selected_rows} (canonical_items={selected_items}, premium_rows={premium_rows}, "
        f"premium_threshold=+{round(max(args.premium_threshold,0.0)*100)}%)"
    )

    # Resolved-by-image contribution (observed and estimate rows)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        img_obs = conn.execute(
            """
            SELECT COUNT(*) AS n,
                   COUNT(DISTINCT variant_key) AS variants,
                   COUNT(DISTINCT COALESCE(NULLIF(canonical_item_id,''), variant_key)) AS canonical_items
            FROM observed_prices
            WHERE market_key = ?
              AND price_fg >= ?
              AND source LIKE 'image_ocr_candidate:%'
            """,
            (args.market_key, args.min_fg),
        ).fetchone()
    finally:
        conn.close()
    print(
        "resolved_by_image="
        f"obs={int(img_obs['n'] or 0)} variants={int(img_obs['variants'] or 0)} canonical_items={int(img_obs['canonical_items'] or 0)}"
    )

    print("\nTop variants missing property signatures (high-value focus):")
    for variant, count in by_variant_no_sig.most_common(args.top):
        total = by_variant_total[variant]
        sig_count = by_variant_sig[variant]
        cov = round(100 * sig_count / max(total, 1))
        price, excerpt, _url = example_by_variant.get(variant, (0.0, "", ""))
        print(f"{count:>3}/{total:<3} {variant:<40} sig_cov={cov:>3}% ex_price={price:g} | {excerpt}")

    print("\nTop variants by observation count:")
    for variant, total in by_variant_total.most_common(args.top):
        sig_count = by_variant_sig[variant]
        miss_count = by_variant_no_sig[variant]
        cov = round(100 * sig_count / max(total, 1))
        print(f"{variant:<40} total={total:<3} sig={sig_count:<3} miss={miss_count:<3} sig_cov={cov:>3}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
