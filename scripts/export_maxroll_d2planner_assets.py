#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


PLANNER_URL = "https://maxroll.gg/d2/d2planner"
DROP_URL = "https://maxroll.gg/d2/d2-drop-calculator"
ASSETS_BASE = "https://assets-ng.maxroll.gg/d2planner"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Export Maxroll D2 Planner assets via browser context (bypasses 403 on direct fetch)."
    )
    p.add_argument("--planner-url", default=PLANNER_URL)
    p.add_argument("--dropcalc-url", default=DROP_URL)
    p.add_argument("--profile-dir", default="data/cache/playwright-maxroll-profile")
    p.add_argument("--out-dir", default="data/raw/maxroll/d2planner")
    p.add_argument("--timeout-ms", type=int, default=30000)
    p.add_argument("--channel", default="chrome", help="Browser channel for Playwright persistent context (e.g. chrome).")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--manual-start", action="store_true", help="Pause after opening planner page for manual login/challenge handling.")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--skip-bundles", action="store_true")
    return p.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def fetch_bytes(page, context, url: str) -> tuple[int, str, bytes]:
    # Prefer Playwright's APIRequestContext to bypass page CORS restrictions while
    # keeping browser-like headers/session. Fall back to in-page fetch if needed.
    try:
        r = context.request.get(url, timeout=30000)
        status = r.status
        headers = r.headers
        content_type = headers.get("content-type", "") if headers else ""
        body = r.body()
        if status and body is not None:
            return int(status), str(content_type), body
    except Exception:
        pass

    res = page.evaluate(
        """
        async (url) => {
          const r = await fetch(url, { credentials: "include", mode: "cors" });
          const buf = await r.arrayBuffer();
          const bytes = new Uint8Array(buf);
          let binary = "";
          const CHUNK = 0x8000;
          for (let i = 0; i < bytes.length; i += CHUNK) {
            binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
          }
          return {
            status: r.status,
            contentType: r.headers.get("content-type") || "",
            bodyB64: btoa(binary),
          };
        }
        """,
        url,
    )
    return int(res["status"]), str(res.get("contentType") or ""), base64.b64decode(res["bodyB64"])


def write_if_needed(path: Path, data: bytes, overwrite: bool) -> bool:
    if path.exists() and not overwrite:
        return False
    path.write_bytes(data)
    return True


def discover_loader_url(page) -> str | None:
    html = page.content()
    m = re.search(r"https://assets-ng\\.maxroll\\.gg/d2planner/loader-[A-Za-z0-9_-]+\\.js", html)
    if m:
        return m.group(0)
    entries = page.evaluate(
        "() => performance.getEntriesByType('resource').map(e => String(e.name || ''))"
    )
    for url in entries:
        if "assets-ng.maxroll.gg/d2planner/loader-" in url and url.endswith(".js"):
            return url
    return None


def discover_drop_route_url(page) -> str | None:
    entries = page.evaluate(
        "() => performance.getEntriesByType('resource').map(e => String(e.name || ''))"
    )
    for url in entries:
        if "/assets/d2.d2-drop-calculator-" in url and url.endswith(".js"):
            return url
    return None


def discover_core_module_paths(loader_text: str) -> list[str]:
    paths = []
    for pat in [r'"\./data\.min-[A-Za-z0-9]+\.js"', r'"\./strings\.min-[A-Za-z0-9]+\.js"']:
        for m in re.finditer(pat, loader_text):
            rel = m.group(0).strip('"')
            if rel not in paths:
                paths.append(rel)
    return paths


def load_itemlib_index(itemlib_path: Path) -> dict[str, list[int]]:
    data = json.loads(itemlib_path.read_text())
    if not isinstance(data, dict):
        raise ValueError("itemlibNew.json is not a dict")
    out: dict[str, list[int]] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, list) and len(v) >= 3:
            out[k] = [int(v[0]), int(v[1]), int(v[2])]
    return out


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)

    manifest: dict[str, object] = {
        "planner_url": args.planner_url,
        "dropcalc_url": args.dropcalc_url,
        "exported": {},
    }

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(Path(args.profile_dir)),
            channel=args.channel,
            headless=args.headless,
        )
        try:
            page = context.new_page()
            page.goto(args.planner_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
            if args.manual_start:
                print("Manual step: handle Maxroll page/login/challenge if needed, then press Enter...")
                input()
                page.reload(wait_until="domcontentloaded", timeout=args.timeout_ms)

            loader_url = discover_loader_url(page)
            loader_path: Path | None = None
            if loader_url:
                print(f"loader_url={loader_url}")
                status, ctype, body = fetch_bytes(page, context, loader_url)
                loader_path = out_dir / loader_url.rsplit("/", 1)[-1]
                wrote = write_if_needed(loader_path, body, args.overwrite)
                manifest["exported"]["loader_js"] = {
                    "url": loader_url,
                    "status": status,
                    "content_type": ctype,
                    "bytes": len(body),
                    "path": str(loader_path),
                    "written": wrote,
                }
            else:
                print("warning: loader URL not discovered", file=sys.stderr)
                existing_loaders = sorted(out_dir.glob("loader-*.js"))
                if existing_loaders:
                    loader_path = max(existing_loaders, key=lambda p: p.stat().st_mtime)
                    print(f"using existing loader file: {loader_path}")

            itemlib_url = f"{ASSETS_BASE}/itemlibNew.json"
            status, ctype, body = fetch_bytes(page, context, itemlib_url)
            itemlib_path = out_dir / "itemlibNew.json"
            wrote = write_if_needed(itemlib_path, body, args.overwrite)
            print(f"itemlib status={status} bytes={len(body)} path={itemlib_path}")
            manifest["exported"]["itemlib"] = {
                "url": itemlib_url,
                "status": status,
                "content_type": ctype,
                "bytes": len(body),
                "path": str(itemlib_path),
                "written": wrote,
            }

            if loader_path and loader_path.exists():
                loader_text = loader_path.read_text(errors="ignore")
                core_modules = []
                for rel in discover_core_module_paths(loader_text):
                    filename = rel.split("/")[-1]
                    url = f"{ASSETS_BASE}/{filename}"
                    status, ctype, body = fetch_bytes(page, context, url)
                    mod_path = out_dir / filename
                    wrote = write_if_needed(mod_path, body, args.overwrite)
                    print(f"core_module={filename} status={status} bytes={len(body)}")
                    core_modules.append(
                        {
                            "rel": rel,
                            "url": url,
                            "status": status,
                            "content_type": ctype,
                            "bytes": len(body),
                            "path": str(mod_path),
                            "written": wrote,
                        }
                    )
                if core_modules:
                    manifest["exported"]["core_modules"] = core_modules

            if not args.skip_bundles:
                item_index = load_itemlib_index(itemlib_path)
                bundle_ids = sorted({v[0] for v in item_index.values()})
                bundle_meta = []
                for bundle_id in bundle_ids:
                    bundle_url = f"{ASSETS_BASE}/itemsNew{bundle_id}.bundle"
                    status, ctype, body = fetch_bytes(page, context, bundle_url)
                    bundle_path = out_dir / f"itemsNew{bundle_id}.bundle"
                    wrote = write_if_needed(bundle_path, body, args.overwrite)
                    print(
                        f"bundle={bundle_id} status={status} bytes={len(body)} path={bundle_path.name}"
                    )
                    bundle_meta.append(
                        {
                            "bundle_id": bundle_id,
                            "url": bundle_url,
                            "status": status,
                            "content_type": ctype,
                            "bytes": len(body),
                            "path": str(bundle_path),
                            "written": wrote,
                        }
                    )
                manifest["exported"]["item_bundles"] = bundle_meta

            drop_page = context.new_page()
            drop_page.goto(args.dropcalc_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
            drop_route_url = discover_drop_route_url(drop_page)
            if drop_route_url:
                print(f"drop_route_url={drop_route_url}")
                status, ctype, body = fetch_bytes(drop_page, context, drop_route_url)
                route_path = out_dir / "d2-drop-calculator-route.js"
                wrote = write_if_needed(route_path, body, args.overwrite)
                manifest["exported"]["dropcalc_route_js"] = {
                    "url": drop_route_url,
                    "status": status,
                    "content_type": ctype,
                    "bytes": len(body),
                    "path": str(route_path),
                    "written": wrote,
                }
            else:
                print("warning: dropcalc route JS not discovered", file=sys.stderr)

            manifest_path = out_dir / "export_manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True))
            print(f"wrote manifest={manifest_path}")
            return 0
        finally:
            context.close()


if __name__ == "__main__":
    raise SystemExit(main())
