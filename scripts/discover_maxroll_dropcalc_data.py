#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


DEFAULT_DIR = Path("data/raw/maxroll/d2planner")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Inspect saved Maxroll D2 planner/dropcalc assets and report bundle shard + dropcalc data clues."
    )
    p.add_argument("--dir", default=str(DEFAULT_DIR))
    p.add_argument("--write-json", help="Optional output path for JSON report")
    p.add_argument("--snippet-context", type=int, default=220)
    return p.parse_args()


def snippet(text: str, pos: int, ctx: int) -> str:
    s = max(0, pos - ctx)
    e = min(len(text), pos + ctx)
    return text[s:e].replace("\n", " ")


def main() -> int:
    args = parse_args()
    root = Path(args.dir)
    itemlib_path = root / "itemlibNew.json"
    loader_candidates = sorted(root.glob("loader-*.js"))
    auto_loader_path = root / "auto-loader.js"
    planner_blob_path = root / "planner_data_blob.bin"
    route_path = root / "d2-drop-calculator-route.js"

    report: dict[str, object] = {"root": str(root)}

    if itemlib_path.exists():
        itemlib = json.loads(itemlib_path.read_text())
        items = {
            k: v for k, v in itemlib.items() if isinstance(k, str) and isinstance(v, list) and len(v) >= 3
        }
        bundle_ids = sorted({int(v[0]) for v in items.values()})
        report["itemlib"] = {
            "items": len(items),
            "bundle_ids": bundle_ids,
            "bundle_count": len(bundle_ids),
            "sample_keys": sorted(list(items.keys()))[:15],
            "bytes_per_item_payload_total": sum(int(v[2]) for v in items.values()),
        }
    else:
        report["itemlib"] = {"error": "missing itemlibNew.json"}

    if loader_candidates:
        loader_path = max(loader_candidates, key=lambda p: p.stat().st_mtime)
        text = loader_path.read_text(errors="ignore")
        report["loader"] = {
            "path": str(loader_path),
            "size_bytes": loader_path.stat().st_size,
        }
        m_blob = re.search(r'data:application/octet-stream;base64,([A-Za-z0-9+/=]+)"', text)
        report["loader"]["embedded_octet_blob"] = {
            "present": bool(m_blob),
            "base64_chars": len(m_blob.group(1)) if m_blob else 0,
            "decoded_bytes_estimate": (len(m_blob.group(1)) * 3) // 4 if m_blob else 0,
        }
        core_modules = []
        for pat in [r'"\./data\.min-[A-Za-z0-9]+\.js"', r'"\./strings\.min-[A-Za-z0-9]+\.js"']:
            for m in re.finditer(pat, text):
                rel = m.group(0).strip('"')
                if rel not in core_modules:
                    core_modules.append(rel)
        report["loader"]["core_modules"] = core_modules
        tokens = [
            "itemlibNew.json",
            "itemsNew",
            "tcData",
            "monsterById",
            "autoTc",
            "staffMods",
            "mods",
            "DropCalculatorContextProvider",
            "useDropCalculatorData",
        ]
        hits = {}
        for token in tokens:
            idx = text.find(token)
            if idx >= 0:
                hits[token] = {"index": idx, "snippet": snippet(text, idx, args.snippet_context)}
        report["loader"]["token_hits"] = hits

        # Pull likely URL-like strings for planner/dropcalc assets
        urlish = sorted(
            {
                m.group(0)
                for m in re.finditer(
                    r"https://assets-ng\\.maxroll\\.gg/d2planner/[A-Za-z0-9_./-]+|/d2/d2-drop-calculator",
                    text,
                )
            }
        )
        report["loader"]["url_hints"] = urlish[:200]
    else:
        report["loader"] = {"error": "missing loader-*.js"}

    if auto_loader_path.exists():
        auto_text = auto_loader_path.read_text(errors="ignore")
        report["auto_loader"] = {
            "path": str(auto_loader_path),
            "size_bytes": auto_loader_path.stat().st_size,
            "imports_loader": "loader-" in auto_text,
        }
    else:
        report["auto_loader"] = {"error": "missing auto-loader.js"}

    if route_path.exists():
        route_text = route_path.read_text(errors="ignore")
        report["dropcalc_route"] = {
            "path": str(route_path),
            "size_bytes": route_path.stat().st_size,
            "imports_planner_page": "planner-page" in route_text,
            "imports_context": "context-" in route_text,
        }
    else:
        report["dropcalc_route"] = {"error": "missing d2-drop-calculator-route.js"}

    bundles = sorted(root.glob("itemsNew*.bundle"))
    if bundles:
        bundle_info = []
        for p in bundles:
            magic = p.read_bytes()[:16]
            bundle_info.append(
                {
                    "name": p.name,
                    "bytes": p.stat().st_size,
                    "magic_hex": magic.hex(),
                }
            )
        report["bundles_local"] = bundle_info
    else:
        report["bundles_local"] = []

    if planner_blob_path.exists():
        blob = planner_blob_path.read_bytes()
        report["planner_blob"] = {
            "path": str(planner_blob_path),
            "size_bytes": len(blob),
            "first_u32_le": int.from_bytes(blob[:4], "little") if len(blob) >= 4 else None,
            "head_magic_hex": blob[:16].hex(),
            "head_ascii": "".join(chr(x) if 32 <= x < 127 else "." for x in blob[:32]),
        }
    else:
        report["planner_blob"] = {"error": "missing planner_data_blob.bin"}

    print(json.dumps(report, indent=2, ensure_ascii=True))
    if args.write_json:
        out = Path(args.write_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=True))
        print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
