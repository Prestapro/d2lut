#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


REQUIRED_MAXROLL_FAMILIES = [
    "magicPrefix",
    "magicSuffix",
    "autoMagic",
    "crafted",
    "qualityItems",
    "propertyGroups",
    "itemStatCost",
]
REQUIRED_CATEGORY_KEYS = ["runes", "torch", "anni", "jewel", "base_armor", "base_weapon"]


def main() -> int:
    p = argparse.ArgumentParser(description="Audit modifier lexicon foundation coverage (catalog + Maxroll + alias/constraints)")
    p.add_argument("--db", default="data/cache/d2lut.db")
    p.add_argument("--write-json")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        report: dict[str, object] = {"db": str(db_path)}
        # Catalog affix lexicon
        try:
            report["catalog_affix_lexicon"] = {
                "rows": int(conn.execute("SELECT COUNT(*) FROM catalog_affix_lexicon").fetchone()[0]),
                "affixes": int(conn.execute("SELECT COUNT(DISTINCT affix_id) FROM catalog_affix_lexicon").fetchone()[0]),
            }
        except sqlite3.OperationalError:
            report["catalog_affix_lexicon"] = {"error": "missing"}

        # Maxroll family stats
        fam_rows = []
        try:
            fam_rows = conn.execute(
                "SELECT family, row_count FROM maxroll_data_family_stats ORDER BY family"
            ).fetchall()
            report["maxroll_data_family_stats"] = {str(r["family"]): int(r["row_count"]) for r in fam_rows}
        except sqlite3.OperationalError:
            report["maxroll_data_family_stats"] = {"error": "missing"}

        missing_families = [
            fam for fam in REQUIRED_MAXROLL_FAMILIES
            if not any(str(r["family"]) == fam and int(r["row_count"]) > 0 for r in fam_rows)
        ]
        report["required_maxroll_families_missing"] = missing_families

        # Maxroll modifier lexicon and alias layer
        for table in ["maxroll_modifier_lexicon", "modifier_alias_lexicon", "modifier_category_constraints"]:
            try:
                report[f"{table}_rows"] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.OperationalError:
                report[f"{table}_rows"] = None

        try:
            report["modifier_alias_by_source"] = {
                str(r["source_domain"]): int(r["n"])
                for r in conn.execute(
                    "SELECT source_domain, COUNT(*) AS n FROM modifier_alias_lexicon GROUP BY source_domain ORDER BY n DESC, source_domain"
                )
            }
            report["modifier_alias_by_kind"] = {
                str(r["token_kind"]): int(r["n"])
                for r in conn.execute(
                    "SELECT token_kind, COUNT(*) AS n FROM modifier_alias_lexicon GROUP BY token_kind ORDER BY n DESC, token_kind"
                )
            }
        except sqlite3.OperationalError:
            report["modifier_alias_by_source"] = {"error": "missing"}
            report["modifier_alias_by_kind"] = {"error": "missing"}

        try:
            cats = {
                str(r["category_key"]): int(r["n"])
                for r in conn.execute(
                    "SELECT category_key, COUNT(*) AS n FROM modifier_category_constraints GROUP BY category_key"
                )
            }
            report["constraints_by_category"] = cats
            report["required_constraint_categories_missing"] = [k for k in REQUIRED_CATEGORY_KEYS if k not in cats]
        except sqlite3.OperationalError:
            report["constraints_by_category"] = {"error": "missing"}
            report["required_constraint_categories_missing"] = REQUIRED_CATEGORY_KEYS

        # Simple pass/fail gate for critical families.
        failures: list[str] = []
        if missing_families:
            failures.append(f"missing_maxroll_families:{','.join(missing_families)}")
        if report.get("modifier_alias_lexicon_rows") in (None, 0):
            failures.append("missing_modifier_alias_lexicon")
        if report.get("modifier_category_constraints_rows") in (None, 0):
            failures.append("missing_modifier_category_constraints")
        if report.get("required_constraint_categories_missing"):
            failures.append("missing_constraint_categories")
        report["audit_pass"] = len(failures) == 0
        report["failures"] = failures

        print(json.dumps(report, indent=2, ensure_ascii=True))
        if args.write_json:
            out = Path(args.write_json)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=2, ensure_ascii=True))
            print(f"\nWrote {out}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
