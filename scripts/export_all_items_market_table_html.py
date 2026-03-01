#!/usr/bin/env python3
"""Export full game catalog items with market coverage/status into a searchable HTML table.

Shows all catalog items (game-side) with market overlays (observed/estimated) to make coverage gaps explicit.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def _class_from_canonical_id(cid: str) -> str:
    low = (cid or "").lower()
    # torch variants are explicit
    if low.startswith("unique:hellfire_torch:"):
        tail = low.split(":")[-1]
        if tail in {"amazon", "assassin", "barbarian", "druid", "necromancer", "paladin", "sorceress"}:
            return tail
    # common skiller variants / class markers in canonical ids
    for cls, needles in {
        "sorceress": ["sorc_", "sorceress", "warlock"],
        "paladin": ["pala_", "paladin"],
        "barbarian": ["barb_", "barbarian"],
        "amazon": ["ama_", "amazon"],
        "assassin": ["assa_", "assassin"],
        "necromancer": ["necro_", "necromancer"],
        "druid": ["druid_"],
    }.items():
        if any(n in low for n in needles):
            return cls
    return ""


def _pretty_name_from_canonical_id(cid: str) -> str:
    if not cid:
        return ""
    parts = cid.split(":")
    if len(parts) <= 1:
        return cid
    # drop leading namespace in display name
    label = ":".join(parts[1:])
    return label.replace("_", " ")


def _load_raw_catalog_maps(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    uniques = {
        str(r["unique_index"]): r
        for r in conn.execute("SELECT unique_index, code, levelreq, raw_json FROM catalog_uniques")
    }
    sets = {
        str(r["set_index"]): r
        for r in conn.execute("SELECT set_index, code, levelreq, raw_json FROM catalog_sets")
    }
    bases = {
        str(r["code"]): r
        for r in conn.execute("SELECT code, levelreq, gemsockets, item_class, raw_json FROM catalog_bases")
    }
    return uniques, sets, bases


def _roll_range_summary_from_raw(raw_json: str | None, max_props: int = 5) -> str:
    if not raw_json:
        return ""
    try:
        d = json.loads(raw_json)
    except Exception:
        return ""
    out: list[str] = []
    for i in range(1, 13):
        prop = str(d.get(f"prop{i}", "") or "").strip()
        if not prop:
            continue
        mn = str(d.get(f"min{i}", "") or "").strip()
        mx = str(d.get(f"max{i}", "") or "").strip()
        if mn and mx and mn != mx:
            out.append(f"{prop}:{mn}-{mx}")
        elif mn:
            out.append(f"{prop}:{mn}")
        elif mx:
            out.append(f"{prop}:{mx}")
        else:
            out.append(prop)
        if len(out) >= max_props:
            break
    return " | ".join(out)


def _base_tier_from_base_row(base_row: sqlite3.Row | None) -> str:
    if not base_row:
        return ""
    try:
        d = json.loads(base_row["raw_json"] or "{}")
    except Exception:
        return ""
    code = str(d.get("code") or base_row["code"] or "")
    if not code:
        return ""
    if code == str(d.get("normcode") or ""):
        return "normal"
    if code == str(d.get("ubercode") or ""):
        return "exceptional"
    if code == str(d.get("ultracode") or ""):
        return "elite"
    return ""


def _catalog_req_and_ranges(row: sqlite3.Row, uniques, sets, bases) -> tuple[int | None, str, str]:
    source_table = str(row["source_table"] or "")
    source_key = str(row["source_key"] or "")
    if source_table in {"uniques", "catalog_uniques"} and source_key in uniques:
        rr = uniques[source_key]
        req = int(rr["levelreq"]) if rr["levelreq"] is not None else None
        return req, _roll_range_summary_from_raw(rr["raw_json"]), _base_tier_from_base_row(bases.get(str(rr["code"] or "")))
    if source_table in {"sets", "catalog_sets"} and source_key in sets:
        rr = sets[source_key]
        req = int(rr["levelreq"]) if rr["levelreq"] is not None else None
        return req, _roll_range_summary_from_raw(rr["raw_json"]), _base_tier_from_base_row(bases.get(str(rr["code"] or "")))
    if source_table in {"bases", "catalog_bases"} and source_key in bases:
        rr = bases[source_key]
        req = int(rr["levelreq"]) if rr["levelreq"] is not None else None
        parts: list[str] = []
        if rr["item_class"]:
            parts.append(f"class:{rr['item_class']}")
        if rr["gemsockets"] is not None:
            parts.append(f"sockets:0-{int(rr['gemsockets'])}")
        return req, " | ".join(parts), _base_tier_from_base_row(rr)
    return None, "", ""


def _build_rows(conn: sqlite3.Connection, market_key: str) -> list[dict]:
    conn.row_factory = sqlite3.Row
    q = """
    WITH obs AS (
      SELECT
        canonical_item_id,
        COUNT(*) AS obs_count,
        COUNT(DISTINCT variant_key) AS variant_count,
        AVG(price_fg) AS avg_fg,
        MIN(price_fg) AS min_fg,
        MAX(price_fg) AS max_fg,
        MAX(CASE WHEN signal_kind='bin' THEN price_fg END) AS max_bin_fg,
        MAX(observed_at) AS last_seen,
        GROUP_CONCAT(DISTINCT variant_key) AS variants_csv
      FROM observed_prices
      WHERE market_key = ?
      GROUP BY canonical_item_id
    ),
    pe_by_canonical AS (
      SELECT
        op.canonical_item_id,
        MAX(pe.estimate_fg) AS est_fg_max,
        AVG(pe.estimate_fg) AS est_fg_avg,
        MAX(pe.range_high_fg) AS est_range_high_max,
        MAX(pe.range_low_fg) AS est_range_low_max,
        MAX(pe.sample_count) AS est_sample_count_max,
        MAX(pe.updated_at) AS est_updated_at,
        GROUP_CONCAT(DISTINCT pe.variant_key) AS est_variants_csv
      FROM price_estimates pe
      JOIN (
        SELECT DISTINCT canonical_item_id, variant_key
        FROM observed_prices
        WHERE market_key = ?
      ) op
        ON op.variant_key = pe.variant_key
      WHERE pe.market_key = ?
      GROUP BY op.canonical_item_id
    ),
    catalog_universe AS (
      SELECT
        ci.canonical_item_id AS canonical_item_id,
        ci.display_name AS display_name,
        ci.category AS category,
        ci.quality_class AS quality_class,
        ci.source_table AS source_table,
        ci.source_key AS source_key,
        ci.tradeable AS tradeable,
        ci.enabled AS enabled,
        ci.metadata_json AS metadata_json,
        'catalog' AS universe_source
      FROM catalog_items ci
      WHERE ci.enabled = 1 AND ci.tradeable = 1
    ),
    market_only_universe AS (
      SELECT
        op.canonical_item_id AS canonical_item_id,
        NULL AS display_name,
        CASE
          WHEN op.canonical_item_id LIKE 'runeword:%' THEN 'runeword'
          WHEN op.canonical_item_id LIKE 'rune:%' THEN 'rune'
          WHEN op.canonical_item_id LIKE 'bundle:%' THEN 'bundle'
          WHEN op.canonical_item_id LIKE 'key:%' THEN 'key'
          WHEN op.canonical_item_id LIKE 'keyset:%' THEN 'keyset'
          WHEN op.canonical_item_id LIKE 'essence:%' THEN 'essence'
          WHEN op.canonical_item_id LIKE 'token:%' THEN 'token'
          ELSE 'market_only'
        END AS category,
        'derived' AS quality_class,
        NULL AS source_table,
        NULL AS source_key,
        1 AS tradeable,
        1 AS enabled,
        NULL AS metadata_json,
        'market_only' AS universe_source
      FROM (
        SELECT DISTINCT canonical_item_id
        FROM observed_prices
        WHERE market_key = ?
      ) op
      LEFT JOIN catalog_items ci ON ci.canonical_item_id = op.canonical_item_id
      WHERE ci.canonical_item_id IS NULL
    ),
    universe AS (
      SELECT * FROM catalog_universe
      UNION ALL
      SELECT * FROM market_only_universe
    )
    SELECT
      u.canonical_item_id,
      u.display_name,
      u.category,
      u.quality_class,
      u.source_table,
      u.source_key,
      u.tradeable,
      u.enabled,
      u.metadata_json,
      u.universe_source,
      COALESCE(obs.obs_count, 0) AS obs_count,
      COALESCE(obs.variant_count, 0) AS variant_count,
      obs.avg_fg,
      obs.min_fg,
      obs.max_fg,
      obs.max_bin_fg,
      obs.last_seen,
      obs.variants_csv,
      pe_by_canonical.est_fg_max,
      pe_by_canonical.est_fg_avg,
      pe_by_canonical.est_range_high_max,
      pe_by_canonical.est_range_low_max,
      pe_by_canonical.est_sample_count_max,
      pe_by_canonical.est_updated_at,
      pe_by_canonical.est_variants_csv
    FROM universe u
    LEFT JOIN obs ON obs.canonical_item_id = u.canonical_item_id
    LEFT JOIN pe_by_canonical ON pe_by_canonical.canonical_item_id = u.canonical_item_id
    ORDER BY u.category ASC, COALESCE(u.display_name, u.canonical_item_id) ASC, u.canonical_item_id ASC
    """
    rows = conn.execute(q, (market_key, market_key, market_key, market_key)).fetchall()
    uniques_map, sets_map, bases_map = _load_raw_catalog_maps(conn)

    out: list[dict] = []
    for r in rows:
        obs_count = int(r["obs_count"] or 0)
        est_fg = float(r["est_fg_max"] or 0.0) if r["est_fg_max"] is not None else None
        sell_fg = None
        if r["max_bin_fg"] is not None:
            sell_fg = float(r["max_bin_fg"])
        elif r["max_fg"] is not None:
            sell_fg = float(r["max_fg"])
        elif est_fg is not None:
            sell_fg = est_fg

        if obs_count > 0 and est_fg is not None:
            status = "priced"
        elif obs_count > 0:
            status = "observed_only"
        elif est_fg is not None:
            status = "estimated_only"
        else:
            status = "no_data"

        variants = []
        for src in (r["variants_csv"], r["est_variants_csv"]):
            if not src:
                continue
            for v in str(src).split(","):
                vv = v.strip()
                if vv and vv not in variants:
                    variants.append(vv)

        game_req, game_ranges, base_tier = _catalog_req_and_ranges(r, uniques_map, sets_map, bases_map)
        out.append(
            {
                "canonical_item_id": r["canonical_item_id"],
                "name": r["display_name"] or _pretty_name_from_canonical_id(str(r["canonical_item_id"] or "")),
                "category": r["category"],
                "quality_class": r["quality_class"],
                "universe_source": r["universe_source"],
                "class_tag": _class_from_canonical_id(str(r["canonical_item_id"] or "")),
                "base_tier": base_tier,
                "game_req_lvl": game_req,
                "game_roll_ranges": game_ranges,
                "status": status,
                "obs_count": obs_count,
                "variant_count": int(r["variant_count"] or 0),
                "estimate_fg": est_fg,
                "sell_fg": sell_fg,
                "market_low_fg": float(r["min_fg"]) if r["min_fg"] is not None else None,
                "market_high_fg": float(r["max_fg"]) if r["max_fg"] is not None else None,
                "est_range_low_fg": float(r["est_range_low_max"]) if r["est_range_low_max"] is not None else None,
                "est_range_high_fg": float(r["est_range_high_max"]) if r["est_range_high_max"] is not None else None,
                "last_seen": r["last_seen"] or "",
                "variants": variants[:8],
                "has_market": obs_count > 0,
                "has_estimate": est_fg is not None,
            }
        )
    return out


def _html(market_key: str, rows: list[dict]) -> str:
    payload = json.dumps(rows, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>All Items Market Table — {market_key}</title>
  <style>
    :root {{
      --bg:#0a1117; --panel:#101922; --line:#223041; --text:#dce7f4; --muted:#92a6be;
      --green:#86efac; --yellow:#fde68a; --red:#fca5a5; --blue:#93c5fd;
    }}
    body {{ margin:0; padding:16px; background: radial-gradient(circle at 10% -10%, #172230, var(--bg)); color:var(--text); font:14px/1.35 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
    .wrap {{ width:100%; max-width:none; margin:0 auto; }}
    .bar {{ display:grid; gap:8px; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); background:rgba(16,25,34,.9); border:1px solid var(--line); border-radius:12px; padding:10px; position:sticky; top:0; z-index:5; }}
    input,select {{ background:#0c141c; color:var(--text); border:1px solid var(--line); border-radius:8px; padding:8px 10px; }}
    .meta {{ color:var(--muted); margin:8px 2px 10px; }}
    table {{ width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); }}
    thead th {{ position:sticky; top:56px; background:#586573; color:var(--text); border-bottom:1px solid var(--line); text-align:left; padding:10px; cursor:pointer; }}
    td {{ padding:8px 10px; border-bottom:1px solid rgba(34,48,65,.55); vertical-align:top; }}
    tbody tr:hover {{ background: rgba(147,197,253,.06); }}
    .num {{ text-align:right; white-space:nowrap; }}
    .muted {{ color:var(--muted); }}
    .pill {{ display:inline-block; padding:2px 7px; border-radius:999px; border:1px solid var(--line); font-size:12px; }}
    .status-priced {{ color:var(--green); }}
    .status-observed_only {{ color:var(--yellow); }}
    .status-estimated_only {{ color:var(--yellow); }}
    .status-no_data {{ color:var(--red); }}
    .stack > div {{ margin:0 0 2px 0; }}
    .empty {{ color:var(--muted); padding:18px 10px; }}
    @media (max-width:980px) {{
      thead th:nth-child(11), tbody td:nth-child(11), thead th:nth-child(15), tbody td:nth-child(15) {{ display:none; }}
      thead th {{ top:108px; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="bar">
      <input id="q" type="search" placeholder="Search item/canonical id/variant">
      <select id="mode">
        <option value="market">Market only</option>
        <option value="all">All game items</option>
        <option value="no_data">Only no market data</option>
      </select>
      <select id="sourceMode">
        <option value="">All sources</option>
        <option value="catalog">Catalog</option>
        <option value="market_only">Market-only derived</option>
      </select>
      <select id="category"><option value="">All categories</option></select>
      <select id="classTag">
        <option value="">All classes</option>
        <option value="sorceress">Sorceress</option>
        <option value="paladin">Paladin</option>
        <option value="barbarian">Barbarian</option>
        <option value="amazon">Amazon</option>
        <option value="assassin">Assassin</option>
        <option value="necromancer">Necromancer</option>
        <option value="druid">Druid</option>
      </select>
      <select id="baseTier">
        <option value="">All base tiers</option>
        <option value="normal">normal</option>
        <option value="exceptional">exceptional</option>
        <option value="elite">elite</option>
      </select>
      <input id="minSell" type="number" min="0" step="1" placeholder="Min sell fg">
      <select id="sort">
        <option value="sell_desc">Sell FG high → low</option>
        <option value="est_desc">Estimate FG high → low</option>
        <option value="obs_desc">Obs high → low</option>
        <option value="name_asc">Name A → Z</option>
      </select>
    </div>
    <div class="meta" id="meta"></div>
    <table>
      <thead>
        <tr>
          <th data-key="name">Name</th>
          <th data-key="canonical_item_id">Canonical</th>
          <th data-key="category">Category</th>
          <th data-key="universe_source">Source</th>
          <th data-key="quality_class">Quality</th>
          <th data-key="class_tag">Class</th>
          <th data-key="base_tier">Base Tier</th>
          <th data-key="game_req_lvl" class="num">Req</th>
          <th data-key="game_roll_ranges">Game Ranges</th>
          <th data-key="status">Status</th>
          <th data-key="estimate_fg" class="num">Estimate FG</th>
          <th data-key="sell_fg" class="num">Sell FG</th>
          <th data-key="obs_count" class="num">Obs</th>
          <th data-key="variant_count" class="num">Variants</th>
          <th data-key="last_seen">Last Seen</th>
          <th data-key="variants">Example Variants</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <script>
    const DATA = {payload};
    const state = {{ q:"", mode:"market", sourceMode:"", category:"", classTag:"", baseTier:"", minSell:null, sort:"sell_desc" }};
    const $ = (id) => document.getElementById(id);
    const tbody = $("rows"), meta = $("meta");
    function esc(s) {{ return String(s ?? "").replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c])); }}
    function n(v) {{ return v == null || v === "" ? "" : Math.round(Number(v)); }}
    function sortRows(rows) {{
      return rows.sort((a,b) => {{
        switch (state.sort) {{
          case "est_desc": return Number(b.estimate_fg||0)-Number(a.estimate_fg||0) || Number(b.sell_fg||0)-Number(a.sell_fg||0);
          case "req_desc": return Number(b.game_req_lvl||-1)-Number(a.game_req_lvl||-1) || Number(b.sell_fg||0)-Number(a.sell_fg||0);
          case "req_asc": return Number(a.game_req_lvl||999)-Number(b.game_req_lvl||999) || Number(b.sell_fg||0)-Number(a.sell_fg||0);
          case "category_asc": return String(a.category||"").localeCompare(String(b.category||"")) || String(a.name||"").localeCompare(String(b.name||""));
          case "category_desc": return String(b.category||"").localeCompare(String(a.category||"")) || String(b.name||"").localeCompare(String(a.name||""));
          case "source_asc": return String(a.universe_source||"").localeCompare(String(b.universe_source||"")) || String(a.name||"").localeCompare(String(b.name||""));
          case "source_desc": return String(b.universe_source||"").localeCompare(String(a.universe_source||"")) || String(b.name||"").localeCompare(String(a.name||""));
          case "obs_desc": return Number(b.obs_count||0)-Number(a.obs_count||0) || Number(b.sell_fg||0)-Number(a.sell_fg||0);
          case "name_asc": return String(a.name||"").localeCompare(String(b.name||""));
          case "sell_desc":
          default: return Number(b.sell_fg||0)-Number(a.sell_fg||0) || Number(b.estimate_fg||0)-Number(a.estimate_fg||0);
        }}
      }});
    }}
    function headerSortKey(k) {{
      switch (k) {{
        case "name": return "name";
        case "category": return "category";
        case "universe_source": return "source";
        case "game_req_lvl": return "req";
        case "estimate_fg": return "est";
        case "sell_fg": return "sell";
        case "obs_count": return "obs";
        default: return "";
      }}
    }}
    function toggleHeaderSort(dataKey) {{
      const base = headerSortKey(dataKey);
      if (!base) return;
      const cur = String(state.sort||"");
      if (cur === `${{base}}_desc`) state.sort = `${{base}}_asc`;
      else if (cur === `${{base}}_asc`) state.sort = `${{base}}_desc`;
      else state.sort = (base === "name") ? "name_asc" : `${{base}}_desc`;
      render();
    }}
    function filterRows(rows) {{
      const q = state.q.trim().toLowerCase();
      return rows.filter(r => {{
        if (state.mode === "market" && !r.has_market && !r.has_estimate) return false;
        if (state.mode === "no_data" && (r.has_market || r.has_estimate)) return false;
        if (state.sourceMode && String(r.universe_source||"") !== state.sourceMode) return false;
        if (state.category && String(r.category||"") !== state.category) return false;
        if (state.classTag && String(r.class_tag||"") !== state.classTag) return false;
        if (state.baseTier && String(r.base_tier||"") !== state.baseTier) return false;
        if (state.minSell != null && Number(r.sell_fg||0) < state.minSell) return false;
        if (!q) return true;
        const hay = [r.name, r.canonical_item_id, r.category, r.quality_class, r.class_tag, r.base_tier, String(r.game_req_lvl ?? ""), r.game_roll_ranges || "", r.status, ...(r.variants||[])].join(" ").toLowerCase();
        return hay.includes(q);
      }});
    }}
    function render() {{
      const rows = sortRows(filterRows(DATA));
      const totals = {{
        all: DATA.length,
        market: DATA.filter(r => r.has_market || r.has_estimate).length,
        priced: DATA.filter(r => r.status === "priced").length,
        no_data: DATA.filter(r => r.status === "no_data").length
      }};
      meta.textContent = `Catalog items: ${{totals.all}} | market-covered: ${{totals.market}} | priced: ${{totals.priced}} | no-data: ${{totals.no_data}} | showing: ${{rows.length}}`;
      if (!rows.length) {{
        tbody.innerHTML = `<tr><td class="empty" colspan="16">No rows match filters.</td></tr>`;
        return;
      }}
      tbody.innerHTML = rows.map(r => {{
        const vars = (r.variants || []).slice(0, 4);
        const varsHtml = `<div class="stack">${{vars.length ? vars.map(v => `<div class="muted">${{esc(v)}}</div>`).join("") : `<div class="muted">-</div>`}}</div>`;
        return `<tr>
          <td>${{esc(r.name)}}</td>
          <td class="muted">${{esc(r.canonical_item_id)}}</td>
          <td>${{esc(r.category)}}</td>
          <td>${{esc(r.universe_source || "")}}</td>
          <td>${{esc(r.quality_class)}}</td>
          <td>${{r.class_tag ? `<span class="pill">${{esc(r.class_tag)}}</span>` : `<span class="muted">-</span>`}}</td>
          <td>${{r.base_tier ? `<span class="pill">${{esc(r.base_tier)}}</span>` : `<span class="muted">-</span>`}}</td>
          <td class="num">${{r.game_req_lvl == null ? "-" : n(r.game_req_lvl)}}</td>
          <td class="muted">${{esc(r.game_roll_ranges || "")}}</td>
          <td><span class="pill status-${{esc(r.status)}}">${{esc(r.status)}}</span></td>
          <td class="num">${{r.estimate_fg == null ? "-" : `${{n(r.estimate_fg)}} fg`}}</td>
          <td class="num">${{r.sell_fg == null ? "-" : `${{n(r.sell_fg)}} fg`}}</td>
          <td class="num">${{n(r.obs_count||0)}}</td>
          <td class="num">${{n(r.variant_count||0)}}</td>
          <td class="muted">${{esc(r.last_seen || "")}}</td>
          <td>${{varsHtml}}</td>
        </tr>`;
      }}).join("");
    }}
    $("q").addEventListener("input", e => {{ state.q = e.target.value; render(); }});
    $("mode").addEventListener("change", e => {{ state.mode = e.target.value; render(); }});
    $("sourceMode").addEventListener("change", e => {{ state.sourceMode = e.target.value; render(); }});
    $("category").addEventListener("change", e => {{ state.category = e.target.value; render(); }});
    $("classTag").addEventListener("change", e => {{ state.classTag = e.target.value; render(); }});
    $("baseTier").addEventListener("change", e => {{ state.baseTier = e.target.value; render(); }});
    $("minSell").addEventListener("input", e => {{ const v = e.target.value.trim(); state.minSell = v ? Number(v) : null; render(); }});
    $("sort").addEventListener("change", e => {{ state.sort = e.target.value; render(); }});
    document.querySelectorAll("thead th[data-key]").forEach(th => th.addEventListener("click", () => toggleHeaderSort(th.dataset.key || "")));
    (function initCategories() {{
      const sel = $("category");
      const vals = [...new Set(DATA.map(r => String(r.category||"")).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
      for (const v of vals) {{
        const opt = document.createElement("option");
        opt.value = v;
        opt.textContent = v;
        sel.appendChild(opt);
      }}
    }})();
    render();
  </script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Export all game items with market coverage/status into HTML")
    ap.add_argument("--db", default="data/cache/d2lut.db")
    ap.add_argument("--market-key", default="d2r_sc_ladder")
    ap.add_argument("--out", default="data/cache/all_items_market_table.html")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"ERROR: DB not found: {db}")
        return 2

    conn = sqlite3.connect(db)
    try:
        rows = _build_rows(conn, args.market_key)
    finally:
        conn.close()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_html(args.market_key, rows), encoding="utf-8")

    market_n = sum(1 for r in rows if r["has_market"] or r["has_estimate"])
    priced_n = sum(1 for r in rows if r["status"] == "priced")
    no_data_n = sum(1 for r in rows if r["status"] == "no_data")
    print(
        f"exported rows={len(rows)} market_covered={market_n} priced={priced_n} "
        f"no_data={no_data_n} out={out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
