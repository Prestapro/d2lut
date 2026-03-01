#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Report counts from locally exported Maxroll D2 Planner core modules (data.min / strings.min)."
    )
    p.add_argument("--dir", default="data/raw/maxroll/d2planner")
    p.add_argument("--write-json", help="Optional output path for JSON report")
    return p.parse_args()


def latest(glob_pat: str, root: Path) -> Path:
    files = sorted(root.glob(glob_pat))
    if not files:
        raise FileNotFoundError(f"Missing {glob_pat} in {root}")
    return max(files, key=lambda p: p.stat().st_mtime)


def node_import_report(data_js: Path, strings_js: Path) -> dict:
    script = rf"""
const path = require('node:path');
const {{ pathToFileURL }} = require('node:url');
(async () => {{
  const dataMod = await import(pathToFileURL(path.resolve({json.dumps(str(data_js))})).href);
  const stringsMod = await import(pathToFileURL(path.resolve({json.dumps(str(strings_js))})).href);
  const data = dataMod.default;
  const strings = stringsMod.default;
  const countOf = (v) => Array.isArray(v) ? v.length : (v && typeof v === 'object' ? Object.keys(v).length : null);
  const keys = Object.keys(data).sort();
  const pick = [
    'armor','weapons','misc','items','itemTypes',
    'magicPrefix','magicSuffix','autoMagic','crafted','qualityItems','propertyGroups',
    'itemStatCost','skills','monsters','states','missiles',
    'uniqueItems','setItems','sets','runes'
  ];
  const counts = {{}};
  for (const k of pick) counts[k] = countOf(data[k]);
  const out = {{
    data_module: path.basename({json.dumps(str(data_js))}),
    strings_module: path.basename({json.dumps(str(strings_js))}),
    data_top_keys: keys.length,
    data_top_key_sample: keys.slice(0, 30),
    strings_rows: countOf(strings),
    strings_sample: Array.isArray(strings) ? strings.slice(0, 5) : null,
    counts,
  }};
  console.log(JSON.stringify(out));
}})().catch((e) => {{ console.error(e); process.exit(1); }});
"""
    proc = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def main() -> int:
    args = parse_args()
    root = Path(args.dir)
    data_js = latest("data.min-*.js", root)
    strings_js = latest("strings.min-*.js", root)
    report = node_import_report(data_js, strings_js)
    report["root"] = str(root)
    print(json.dumps(report, indent=2, ensure_ascii=True))
    if args.write_json:
        out = Path(args.write_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=True))
        print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
