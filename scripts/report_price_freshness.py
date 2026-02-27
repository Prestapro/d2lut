#!/usr/bin/env python3
"""Report catalog price freshness against recent d2jsp observations."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from statistics import median


def _is_low_rune_cid(cid: str) -> bool:
    if not cid.startswith("rune:"):
        return False
    if cid.startswith("rune:r"):
        try:
            n = int(cid.split(":r", 1)[1])
        except (ValueError, IndexError):
            return False
        return 1 <= n <= 20
    low = {
        "el", "eld", "tir", "nef", "eth", "ith", "tal", "ral", "ort", "thul",
        "amn", "sol", "shael", "dol", "hel", "io", "lum", "ko", "fal", "lem",
    }
    return cid.split(":", 1)[1].lower() in low


def _is_perfect_gem(cid: str, name: str) -> bool:
    n = (name or "").lower()
    return n.startswith("perfect ") or cid.startswith("misc:gp") or cid == "misc:skz"


def _normalize_variant_match(v: str | None) -> str | None:
    if not v:
        return None
    if " (+" in v:
        return v.split(" (+", 1)[0].strip()
    return v.strip()


def main() -> int:
    p = argparse.ArgumentParser(description="Report freshness: catalog fg_median vs recent d2jsp median")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite DB path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--hours", type=int, default=72, help="Recent window in hours")
    p.add_argument("--threshold-pct", type=float, default=50.0, help="Flag if deviation >= threshold pct")
    p.add_argument("--kind", choices=["all", "low-runes-gems"], default="all", help="Subset")
    p.add_argument("--limit", type=int, default=40, help="Max rows to print")
    args = p.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"ERROR: DB not found: {db}")
        return 2

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    cpm_rows = conn.execute(
        """
        SELECT canonical_item_id, display_name, price_status, fg_median, variant_key_matched
        FROM catalog_price_map
        WHERE fg_median IS NOT NULL AND variant_key_matched IS NOT NULL
        """
    ).fetchall()

    recent_rows = conn.execute(
        """
        SELECT variant_key, price_fg
        FROM observed_prices
        WHERE market_key = ?
          AND source = 'd2jsp'
          AND price_fg IS NOT NULL
          AND price_fg > 0
          AND observed_at >= datetime('now', ?)
        """,
        (args.market_key, f"-{max(1, args.hours)} hours"),
    ).fetchall()
    by_variant: dict[str, list[float]] = {}
    for r in recent_rows:
        by_variant.setdefault(r["variant_key"], []).append(float(r["price_fg"]))

    # Robust caps for low runes/perfect gems (same intent as catalog refresh).
    lem_vals = sorted(by_variant.get("rune:lem", []))
    lem_anchor = median(lem_vals) if lem_vals else 30.0
    low_rune_cap = max(90.0, lem_anchor * 3.0)
    perfect_gem_cap = max(80.0, lem_anchor * 2.0)

    checked = 0
    flagged: list[dict] = []
    thr = max(0.0, float(args.threshold_pct)) / 100.0

    for r in cpm_rows:
        cid = r["canonical_item_id"]
        name = r["display_name"]
        if args.kind == "low-runes-gems":
            if not (_is_low_rune_cid(cid) or _is_perfect_gem(cid, name)):
                continue

        vk = _normalize_variant_match(r["variant_key_matched"])
        if not vk:
            continue
        vals = sorted(by_variant.get(vk, []))
        if not vals:
            continue

        if _is_low_rune_cid(cid):
            vals2 = [v for v in vals if v <= low_rune_cap]
            vals = sorted(vals2 or vals)
        elif _is_perfect_gem(cid, name):
            vals2 = [v for v in vals if v <= perfect_gem_cap]
            vals = sorted(vals2 or vals)

        cur = float(r["fg_median"])
        rec_med = float(median(vals))
        rel = abs(rec_med - cur) / max(cur, 1.0)
        checked += 1
        if rel >= thr:
            flagged.append(
                {
                    "canonical_item_id": cid,
                    "current_fg": round(cur, 1),
                    "recent_median": round(rec_med, 1),
                    "delta_pct": round(rel * 100.0, 1),
                    "recent_n": len(vals),
                    "variant": vk,
                }
            )

    flagged.sort(key=lambda x: (-x["delta_pct"], -x["recent_n"], x["canonical_item_id"]))

    print("=" * 88)
    print("PRICE FRESHNESS REPORT")
    print("=" * 88)
    print(f"subset={args.kind}  window={args.hours}h  threshold={args.threshold_pct}%")
    print(f"rows_checked={checked}  flagged={len(flagged)}")
    print("canonical_item_id | current_fg | recent_median | delta% | n | variant")
    for row in flagged[: max(1, args.limit)]:
        print(
            f"{row['canonical_item_id']} | {row['current_fg']} | {row['recent_median']} | "
            f"{row['delta_pct']}% | {row['recent_n']} | {row['variant']}"
        )
    print("=" * 88)

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
