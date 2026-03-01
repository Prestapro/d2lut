#!/usr/bin/env python3
"""Export a full catalog price table HTML from catalog_price_map.

Unlike export_price_table_html.py (which sources from price_estimates),
this exports ALL catalog items from catalog_price_map, including heuristic
and unknown entries. Produces data/cache/price_table_full.html.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def _normalize_variant_match(v: str | None) -> str:
    if not v:
        return ""
    s = str(v).strip()
    marker = " (+"
    if marker in s:
        return s.split(marker, 1)[0].strip()
    return s


def _build_html(market_key: str, rows: list[dict]) -> str:
    payload = json.dumps(rows, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>d2lut full catalog price table - {market_key}</title>
  <style>
    :root {{
      --bg: #0b1118; --panel: #101923; --line: #223042;
      --text: #dbe6f3; --muted: #93a5bb; --good: #7dd3fc;
      --warn: #fde68a; --bad: #fca5a5; --accent: #86efac;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 16px;
      background: radial-gradient(circle at 20% 0%, #16202d, var(--bg));
      color: var(--text);
      font: 14px/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }}
    .wrap {{ max-width: 1400px; margin: 0 auto; }}
    .bar {{
      display: grid; grid-template-columns: 1fr auto auto auto auto; gap: 8px;
      background: color-mix(in srgb, var(--panel) 92%, black);
      border: 1px solid var(--line); border-radius: 12px; padding: 10px;
      position: sticky; top: 0; backdrop-filter: blur(8px); z-index: 5;
    }}
    input, select {{
      background: #0b141d; color: var(--text);
      border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px;
    }}
    .meta {{ color: var(--muted); margin: 8px 2px 10px; }}
    table {{
      width: 100%; border-collapse: collapse; background: var(--panel);
      border: 1px solid var(--line); border-radius: 12px; overflow: hidden;
    }}
    thead th {{
      text-align: left; font-weight: 700; color: var(--muted); padding: 10px;
      border-bottom: 1px solid var(--line); position: sticky; top: 62px;
      background: #0f1822; cursor: pointer; user-select: none;
    }}
    tbody td {{
      padding: 8px 10px; border-bottom: 1px solid rgba(34,48,66,0.55);
      vertical-align: top;
    }}
    tbody tr:hover {{ background: rgba(125,211,252,0.06); }}
    .num {{ text-align: right; white-space: nowrap; }}
    .muted {{ color: var(--muted); }}
    .pill {{
      display: inline-block; padding: 2px 7px; border-radius: 999px;
      border: 1px solid var(--line); font-size: 12px;
    }}
    .st-market {{ color: var(--accent); }}
    .st-variant_fallback {{ color: var(--good); }}
    .st-heuristic_range {{ color: var(--warn); }}
    .st-unknown {{ color: var(--bad); }}
    .empty {{ color: var(--muted); padding: 18px 10px; }}
    @media (max-width: 900px) {{
      .bar {{ grid-template-columns: 1fr 1fr; }}
      thead th {{ top: 108px; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="bar">
      <input id="q" type="search" placeholder="Search item name, category, id...">
      <select id="cat">
        <option value="">All categories</option>
      </select>
      <select id="status">
        <option value="">All statuses</option>
        <option value="market">market</option>
        <option value="variant_fallback">variant_fallback</option>
        <option value="heuristic_range">heuristic_range</option>
        <option value="unknown">unknown</option>
      </select>
      <input id="minFg" type="number" min="0" step="1" placeholder="Min fg">
      <select id="sort">
        <option value="fg_desc">Sort: FG high → low</option>
        <option value="fg_asc">Sort: FG low → high</option>
        <option value="name_asc">Sort: name A → Z</option>
        <option value="cat_asc">Sort: category</option>
      </select>
    </div>
    <div class="meta" id="meta"></div>
    <table>
      <thead>
        <tr>
          <th data-key="canonical_item_id">Item ID</th>
          <th data-key="display_name">Name</th>
          <th data-key="category">Category</th>
          <th data-key="price_status">Status</th>
          <th data-key="fg_median" class="num">FG (median)</th>
          <th class="num">Range</th>
          <th data-key="seed_tier">Seed Tier</th>
          <th data-key="source_type">Source</th>
          <th data-key="sample_count" class="num">Samples</th>
          <th data-key="last_seen">Last Seen</th>
          <th data-key="updated_at">Updated</th>
          <th>Matched</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <script>
    const DATA = {payload};
    const state = {{ q: "", cat: "", status: "", minFg: null, sort: "fg_desc" }};
    const $ = id => document.getElementById(id);
    const tbody = $("rows"), meta = $("meta");

    // Populate category dropdown
    const cats = [...new Set(DATA.map(r => r.category))].sort();
    const catSel = $("cat");
    cats.forEach(c => {{
      const o = document.createElement("option");
      o.value = c; o.textContent = c;
      catSel.appendChild(o);
    }});

    function esc(s) {{
      return String(s ?? "").replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));
    }}
    function fmtNum(v) {{
      if (v == null || Number.isNaN(v)) return "";
      return Number(v) < 1 ? String(Number(v)) : Math.round(Number(v)).toString();
    }}
    function fgVal(r) {{
      if (r.fg_median != null) return Number(r.fg_median);
      return -1;
    }}
    function cmp(a, b) {{
      switch (state.sort) {{
        case "fg_asc": return fgVal(a) - fgVal(b);
        case "name_asc": return (a.display_name||"").localeCompare(b.display_name||"");
        case "cat_asc": return (a.category||"").localeCompare(b.category||"") || fgVal(b) - fgVal(a);
        case "last_seen_desc": return String(b.last_seen || "").localeCompare(String(a.last_seen || ""));
        case "updated_desc": return String(b.updated_at || "").localeCompare(String(a.updated_at || ""));
        default: return fgVal(b) - fgVal(a);
      }}
    }}
    function filter(rows) {{
      const q = state.q.trim().toLowerCase();
      return rows.filter(r => {{
        if (state.cat && r.category !== state.cat) return false;
        if (state.status && r.price_status !== state.status) return false;
        if (state.minFg != null && fgVal(r) < state.minFg) return false;
        if (!q) return true;
        return [r.canonical_item_id, r.display_name, r.category, r.seed_tier, r.variant_key_matched]
          .join(" ").toLowerCase().includes(q);
      }});
    }}
    function render() {{
      const rows = filter(DATA).sort(cmp);
      meta.textContent = `Market: {market_key} | ${{rows.length}} / ${{DATA.length}} items`;
      if (!rows.length) {{
        tbody.innerHTML = `<tr><td colspan="12" class="empty">No rows match.</td></tr>`;
        return;
      }}
      tbody.innerHTML = rows.map(r => `<tr>
        <td class="muted">${{esc(r.canonical_item_id)}}</td>
        <td>${{esc(r.display_name)}}</td>
        <td class="muted">${{esc(r.category)}}</td>
        <td><span class="pill st-${{r.price_status}}">${{esc(r.price_status)}}</span></td>
        <td class="num">${{fmtNum(r.fg_median)}} ${{r.fg_median != null ? "fg" : ""}}</td>
        <td class="num">${{r.fg_min != null ? fmtNum(r.fg_min)+"-"+fmtNum(r.fg_max) : ""}}</td>
        <td class="muted">${{esc(r.seed_tier||"")}}</td>
        <td class="muted">${{esc(r.source_type||"")}}</td>
        <td class="num">${{fmtNum(r.sample_count)}}</td>
        <td class="muted">${{esc(r.last_seen || "")}}</td>
        <td class="muted">${{esc(r.updated_at || "")}}</td>
        <td class="muted">${{esc(r.variant_key_matched||"")}}</td>
      </tr>`).join("");
    }}
    $("q").addEventListener("input", e => {{ state.q = e.target.value; render(); }});
    $("cat").addEventListener("change", e => {{ state.cat = e.target.value; render(); }});
    $("status").addEventListener("change", e => {{ state.status = e.target.value; render(); }});
    $("minFg").addEventListener("input", e => {{
      const v = e.target.value.trim();
      state.minFg = v === "" ? null : Number(v);
      render();
    }});
    $("sort").addEventListener("change", e => {{ state.sort = e.target.value; render(); }});
    document.querySelectorAll("th[data-key]").forEach(th => {{
      th.addEventListener("click", () => {{
        const key = th.dataset.key;
        if (key === "fg_median") state.sort = "fg_desc";
        else if (key === "display_name") state.sort = "name_asc";
        else if (key === "category") state.sort = "cat_asc";
        else if (key === "last_seen") state.sort = "last_seen_desc";
        else if (key === "updated_at") state.sort = "updated_desc";
        render();
      }});
    }});
    render();
  </script>
</body>
</html>
"""


def main() -> int:
    p = argparse.ArgumentParser(description="Export full catalog price table HTML from catalog_price_map")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key (for display)")
    p.add_argument("--out", default="data/cache/price_table_full.html", help="Output HTML file")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM catalog_price_map ORDER BY category, canonical_item_id"
        ).fetchall()]
        observed_max = {
            r["variant_key"]: (r["last_seen"] or "")
            for r in conn.execute(
                """
                SELECT variant_key, MAX(observed_at) AS last_seen
                FROM observed_prices
                WHERE market_key = ?
                GROUP BY variant_key
                """,
                (args.market_key,),
            ).fetchall()
        }
        for row in rows:
            vk = _normalize_variant_match(row.get("variant_key_matched"))
            row["last_seen"] = observed_max.get(vk, "")
    finally:
        conn.close()

    if not rows:
        print("ERROR: catalog_price_map is empty. Run build_catalog_price_map.py first.")
        return 2

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_build_html(args.market_key, rows), encoding="utf-8")
    print(f"exported {len(rows)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
