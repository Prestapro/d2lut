#!/usr/bin/env python3
"""Export a browser-viewable searchable price table from d2lut SQLite DB."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


# Expert seed (Maxroll-like relative trade value categories for uniques/sets/sunders).
# This is not a price source; it is a qualitative hint to avoid missing key items.
SEED_TIER_ORDER = {"TRASH": 0, "NONE": 1, "LOW": 2, "MED": 3, "HIGH": 4}
SEED_VARIANT_HINTS: list[tuple[str, str, list[str]]] = [
    # High (excerpt-driven, common canonical keys)
    ("annihilus", "HIGH", ["unique_charm", "every_build"]),
    ("hellfire_torch", "HIGH", ["unique_charm", "class_dependent"]),
    ("arachnid_mesh", "HIGH", ["caster_bis"]),
    ("bul-kathos", "HIGH", ["ring", "skill_builds"]),
    ("bk_wedding", "HIGH", ["ring", "skill_builds"]),
    ("cold_rupture", "HIGH", ["sunder"]),
    ("crack_of_the_heavens", "HIGH", ["sunder"]),
    ("crown_of_ages", "HIGH", ["hardcore"]),
    ("deaths_fathom", "HIGH", ["sorc_cold"]),
    ("deaths_web", "HIGH", ["necro_poison"]),
    ("griffons_eye", "HIGH", ["lightning_bis"]),
    ("harlequin_crest", "HIGH", ["mf", "early_ladder"]),
    ("herald_of_zakarum", "HIGH", ["paladin"]),
    ("highlords_wrath", "HIGH", ["attack_amulet"]),
    ("maras_kaleidoscope", "HIGH", ["all_skills_amulet"]),
    ("rainbow_facet", "HIGH", ["facet"]),
    ("skin_of_the_vipermagi", "HIGH", ["caster"]),
    ("tal_rashas_adjudication", "HIGH", ["tal_set"]),
    ("tal_rashas_guardianship", "HIGH", ["tal_set", "early_ladder"]),
    ("the_oculus", "HIGH", ["sorc_mf"]),
    ("stone_of_jordan", "HIGH", ["ring", "dclone"]),
    ("the_stone_of_jordan", "HIGH", ["ring", "dclone"]),
    ("tyraels_might", "HIGH", ["trophy"]),
    ("war_traveler", "HIGH", ["boots", "mf"]),
    ("wisp_projector", "HIGH", ["ring", "uber"]),
    # Med (selected common items from excerpt)
    ("andariels_visage", "MED", ["mercenary"]),
    ("chance_guards", "MED", ["mf"]),
    ("draculs_grasp", "MED", ["ubers"]),
    ("gheeds_fortune", "MED", ["charm", "mf_goldfind"]),
    ("gore_rider", "MED", ["melee"]),
    ("guillaumes_face", "MED", ["ubers", "mercenary"]),
    ("homunculus", "MED", ["necro"]),
    ("metalgrid", "MED", ["attack"]),
    ("nightwings_veil", "MED", ["cold"]),
    ("ondals_wisdom", "MED", ["xp"]),
    ("ormus_robes", "MED", ["sorc"]),
    ("raven_frost", "MED", ["ring", "cannot_be_frozen"]),
    ("skullders_ire", "MED", ["mf"]),
    ("tal_rashas_fine-spun_cloth", "MED", ["tal_set"]),
    ("tal_rashas_horadric_crest", "MED", ["tal_set", "mercenary"]),
    ("tal_rashas_lidless_eye", "MED", ["tal_set"]),
    ("the_reapers_toll", "MED", ["mercenary"]),
    ("thunderstroke", "MED", ["amazon_jav"]),
    ("titans_revenge", "MED", ["amazon_jav"]),
    ("verdungos_hearty_cord", "MED", ["pvp"]),
    ("waterwalk", "MED", ["survivability"]),
    ("wizardspike", "MED", ["caster"]),
    # Low (selected common tradeable but lower-value)
    ("magefist", "LOW", ["caster"]),
    ("nagelring", "LOW", ["mf"]),
    ("mosers_blessed_circle", "LOW", ["res_shield"]),
    ("jalals_mane", "LOW", ["druid"]),
    ("kiras_guardian", "LOW", ["res", "cannot_be_frozen"]),
    ("laying_of_hands", "LOW", ["attack_gloves"]),
    ("goldwrap", "LOW", ["mf_goldfind"]),
    ("dwarf_star", "LOW", ["goldfind"]),
]


def _default_seed_entries() -> list[dict]:
    return [
        {
            "needle": needle,
            "tier": tier,
            "tags": tags,
            "stat_priority": [],
            "seasonality_notes": None,
            "notes": None,
            "game_profile": "d2r",
            "source_name": "builtin_seed",
        }
        for needle, tier, tags in SEED_VARIANT_HINTS
    ]


def _load_seed_entries(seed_file: Path | None) -> list[dict]:
    if seed_file is None or not seed_file.exists():
        return _default_seed_entries()
    try:
        raw = json.loads(seed_file.read_text(encoding="utf-8"))
    except Exception:
        return _default_seed_entries()
    entries_raw = raw.get("entries") if isinstance(raw, dict) else None
    if not isinstance(entries_raw, list):
        return _default_seed_entries()
    out: list[dict] = []
    for e in entries_raw:
        if not isinstance(e, dict):
            continue
        needle = str(e.get("needle") or "").strip().lower()
        tier = str(e.get("tier") or "").strip().upper()
        if not needle or tier not in SEED_TIER_ORDER:
            continue
        tags = [str(t).strip() for t in (e.get("tags") or []) if str(t).strip()]
        stat_priority = [str(t).strip() for t in (e.get("stat_priority") or []) if str(t).strip()]
        out.append(
            {
                "needle": needle,
                "tier": tier,
                "tags": tags,
                "stat_priority": stat_priority,
                "seasonality_notes": e.get("seasonality_notes"),
                "notes": e.get("notes"),
                "game_profile": e.get("game_profile") or "d2r",
                "source_name": e.get("source_name") or "expert_seed",
            }
        )
    return out or _default_seed_entries()


def _seed_tier_for_variant(variant_key: str, seed_entries: list[dict]) -> tuple[str, list[str], dict]:
    v = (variant_key or "").lower()
    for e in seed_entries:
        needle = str(e.get("needle") or "")
        if needle and needle in v:
            return str(e.get("tier") or ""), list(e.get("tags") or []), e
    return "", [], {}


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def _heuristic_ranges_by_tier(rows: list[dict]) -> dict[str, tuple[float, float]]:
    by_tier: dict[str, list[float]] = {}
    for r in rows:
        tier = str(r.get("seed_tier") or "").upper()
        est = r.get("estimate_fg")
        if not tier or est is None:
            continue
        by_tier.setdefault(tier, []).append(float(est))
    out: dict[str, tuple[float, float]] = {}
    for tier, vals in by_tier.items():
        if not vals:
            continue
        low = _quantile(vals, 0.25)
        high = _quantile(vals, 0.75)
        if high < low:
            low, high = high, low
        out[tier] = (round(low, 1), round(high, 1))
    return out


def _build_seed_only_rows(
    existing_rows: list[dict], tier_ranges: dict[str, tuple[float, float]], seed_entries: list[dict]
) -> list[dict]:
    existing_variants = [str(r.get("variant_key") or "").lower() for r in existing_rows]
    out: list[dict] = []
    for e in seed_entries:
        needle = str(e.get("needle") or "")
        tier = str(e.get("tier") or "")
        tags = list(e.get("tags") or [])
        stat_priority = list(e.get("stat_priority") or [])
        seasonality_notes = e.get("seasonality_notes")
        seed_notes = e.get("notes")
        source_name = e.get("source_name") or "expert_seed"
        if any(needle in v for v in existing_variants):
            continue
        low, high = tier_ranges.get(tier, (None, None))
        out.append(
            {
                "market_key": "",
                "variant_key": f"seed:{needle}",
                "estimate_fg": None,
                "range_low_fg": None,
                "range_high_fg": None,
                "heuristic_low_fg": low,
                "heuristic_high_fg": high,
                "confidence": "seed",
                "sample_count": 0,
                "updated_at": "",
                "obs_total": 0,
                "bin_count": 0,
                "sold_count": 0,
                "co_count": 0,
                "ask_count": 0,
                "last_source_url": "",
                "seed_tier": tier,
                "seed_tags": tags,
                "seed_stat_priority": stat_priority,
                "seed_seasonality_notes": seasonality_notes,
                "seed_notes": seed_notes,
                "seed_source_name": source_name,
                "is_seed_only": 1,
            }
        )
    return out


def _build_html(market_key: str, rows: list[dict]) -> str:
    payload = json.dumps(rows, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>d2lut price table - {market_key}</title>
  <style>
    :root {{
      --bg: #0b1118;
      --panel: #101923;
      --line: #223042;
      --text: #dbe6f3;
      --muted: #93a5bb;
      --good: #7dd3fc;
      --warn: #fde68a;
      --bad: #fca5a5;
      --accent: #86efac;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 16px; background: radial-gradient(circle at 20% 0%, #16202d, var(--bg));
      color: var(--text); font: 14px/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }}
    .wrap {{ max-width: 1400px; margin: 0 auto; }}
    .bar {{
      display: grid; grid-template-columns: 1fr auto auto auto auto; gap: 8px;
      background: color-mix(in srgb, var(--panel) 92%, black);
      border: 1px solid var(--line); border-radius: 12px; padding: 10px; position: sticky; top: 0;
      backdrop-filter: blur(8px); z-index: 5;
    }}
    input, select {{
      background: #0b141d; color: var(--text); border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px;
    }}
    .meta {{ color: var(--muted); margin: 8px 2px 10px; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }}
    thead th {{
      text-align: left; font-weight: 700; color: var(--muted); padding: 10px; border-bottom: 1px solid var(--line);
      position: sticky; top: 62px; background: #0f1822; cursor: pointer; user-select: none;
    }}
    tbody td {{ padding: 8px 10px; border-bottom: 1px solid rgba(34,48,66,0.55); vertical-align: top; }}
    tbody tr:hover {{ background: rgba(125,211,252,0.06); }}
    .num {{ text-align: right; white-space: nowrap; }}
    .variant {{ color: var(--text); }}
    .muted {{ color: var(--muted); }}
    .conf-high {{ color: var(--accent); }}
    .conf-medium {{ color: var(--warn); }}
    .conf-low {{ color: var(--bad); }}
    .pill {{
      display: inline-block; padding: 2px 7px; border-radius: 999px; border: 1px solid var(--line); font-size: 12px;
    }}
    .empty {{ color: var(--muted); padding: 18px 10px; }}
    a {{ color: var(--good); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    @media (max-width: 900px) {{
      .bar {{ grid-template-columns: 1fr 1fr; }}
      thead th:nth-child(6), tbody td:nth-child(6),
      thead th:nth-child(8), tbody td:nth-child(8),
      thead th:nth-child(9), tbody td:nth-child(9) {{ display:none; }}
      thead th {{ top: 108px; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="bar">
      <input id="q" type="search" placeholder="Search variant/item (e.g. torch, vex, archon, tal ammy)">
      <select id="conf">
        <option value="">All confidence</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>
      <select id="seedTier">
        <option value="">All seed tiers</option>
        <option value="HIGH">HIGH</option>
        <option value="MED">MED</option>
        <option value="LOW">LOW</option>
        <option value="NONE">NONE</option>
        <option value="TRASH">TRASH</option>
        <option value="UNSEEDED">UNSEEDED</option>
      </select>
      <input id="minFg" type="number" min="0" step="1" placeholder="Min fg">
      <select id="sort">
        <option value="estimate_desc">Sort: FG high → low</option>
        <option value="estimate_asc">Sort: FG low → high</option>
        <option value="samples_desc">Sort: samples high → low</option>
        <option value="seed_desc">Sort: seed tier high → low</option>
        <option value="updated_desc">Sort: newest</option>
        <option value="variant_asc">Sort: name A → Z</option>
      </select>
    </div>
    <div class="meta" id="meta"></div>
    <table>
      <thead>
        <tr>
          <th data-key="variant_key">Variant</th>
          <th data-key="estimate_fg" class="num">FG</th>
          <th data-key="sell_fg" class="num">Sell FG</th>
          <th data-key="range_low_fg" class="num">Range</th>
          <th data-key="confidence">Conf</th>
          <th data-key="seed_tier">Seed</th>
          <th data-key="sample_count" class="num">Samples</th>
          <th data-key="obs_total" class="num">Obs</th>
          <th data-key="signal_mix">Signals</th>
          <th data-key="updated_at">Updated</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <script>
    const DATA = {payload};
    const state = {{
      q: "",
      conf: "",
      seedTier: "",
      minFg: null,
      sort: "estimate_desc",
    }};
    const $ = (id) => document.getElementById(id);
    const tbody = $("rows");
    const meta = $("meta");

    function esc(s) {{
      return String(s ?? "").replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));
    }}

    function fmtNum(v) {{
      if (v == null || Number.isNaN(v)) return "";
      return Math.round(Number(v)).toString();
    }}

    function signalMix(r) {{
      const parts = [];
      if (r.bin_count) parts.push(`bin:${{r.bin_count}}`);
      if (r.sold_count) parts.push(`sold:${{r.sold_count}}`);
      if (r.co_count) parts.push(`co:${{r.co_count}}`);
      if (r.ask_count) parts.push(`ask:${{r.ask_count}}`);
      return parts.join(" ");
    }}

    function seedTierScore(r) {{
      const t = String(r.seed_tier || "");
      if (t === "HIGH") return 4;
      if (t === "MED") return 3;
      if (t === "LOW") return 2;
      if (t === "NONE") return 1;
      if (t === "TRASH") return 0;
      return -1; // unseeded
    }}

    function fgSortValue(r) {{
      if (r.sell_hint_fg != null && !Number.isNaN(Number(r.sell_hint_fg))) return Number(r.sell_hint_fg);
      if (r.estimate_fg != null && !Number.isNaN(Number(r.estimate_fg))) return Number(r.estimate_fg);
      if (r.heuristic_high_fg != null && !Number.isNaN(Number(r.heuristic_high_fg))) return Number(r.heuristic_high_fg);
      if (r.heuristic_low_fg != null && !Number.isNaN(Number(r.heuristic_low_fg))) return Number(r.heuristic_low_fg);
      return -1;
    }}

    function compareRows(a, b) {{
      switch (state.sort) {{
        case "estimate_asc": return fgSortValue(a) - fgSortValue(b);
        case "samples_desc": return (b.sample_count ?? 0) - (a.sample_count ?? 0) || fgSortValue(b) - fgSortValue(a);
        case "seed_desc": return seedTierScore(b) - seedTierScore(a) || fgSortValue(b) - fgSortValue(a);
        case "updated_desc": return String(b.updated_at ?? "").localeCompare(String(a.updated_at ?? ""));
        case "variant_asc": return String(a.variant_key ?? "").localeCompare(String(b.variant_key ?? ""));
        case "estimate_desc":
        default:
          return fgSortValue(b) - fgSortValue(a) || (b.sample_count ?? 0) - (a.sample_count ?? 0);
      }}
    }}

    function filterRows(rows) {{
      const q = state.q.trim().toLowerCase();
      return rows.filter(r => {{
        if (state.conf && (r.confidence || "").toLowerCase() !== state.conf) return false;
        if (state.seedTier) {{
          const t = (r.seed_tier || "").toUpperCase();
          if (state.seedTier === "UNSEEDED") {{
            if (t) return false;
          }} else if (t !== state.seedTier) {{
            return false;
          }}
        }}
        const fgForFilter = (r.estimate_fg != null && !Number.isNaN(Number(r.estimate_fg)))
          ? Number(r.estimate_fg)
          : ((r.heuristic_high_fg != null && !Number.isNaN(Number(r.heuristic_high_fg)))
              ? Number(r.heuristic_high_fg)
              : -1);
        if (state.minFg != null && fgForFilter < state.minFg) return false;
        if (!q) return true;
        const hay = [
          r.variant_key, r.canonical_item_id, r.last_source_url, signalMix(r), r.seed_tier, (r.seed_tags || []).join(" "), (r.seed_stat_priority || []).join(" "), r.seed_seasonality_notes || "", r.seed_notes || ""
        ].join(" ").toLowerCase();
        return hay.includes(q);
      }});
    }}

    function render() {{
      const rows = filterRows(DATA).sort(compareRows);
      meta.textContent = `Market: {market_key} | showing ${{rows.length}} / ${{DATA.length}} rows`;
      if (!rows.length) {{
        tbody.innerHTML = `<tr><td colspan="11" class="empty">No rows match current filters.</td></tr>`;
        return;
      }}
      tbody.innerHTML = rows.map(r => {{
        const conf = (r.confidence || "").toLowerCase();
        const source = r.last_source_url ? `<a href="${{esc(r.last_source_url)}}" target="_blank" rel="noopener">open</a>` : "";
        const seedCell = (r.seed_tier || "") + ((r.seed_tags && r.seed_tags.length) ? ` (${{
          r.seed_tags.join(",")
        }})` : "");
        const seedTitleParts = [];
        if (r.seed_source_name) seedTitleParts.push(`source: ${{r.seed_source_name}}`);
        if (r.seed_stat_priority && r.seed_stat_priority.length) seedTitleParts.push(`priority: ${{r.seed_stat_priority.join(', ')}}`);
        if (r.seed_seasonality_notes) seedTitleParts.push(`season: ${{r.seed_seasonality_notes}}`);
        if (r.seed_notes) seedTitleParts.push(`notes: ${{r.seed_notes}}`);
        const seedTitle = seedTitleParts.join(" | ");
        const isSeedOnly = !!r.is_seed_only;
        const hasMarket = r.estimate_fg != null && !Number.isNaN(Number(r.estimate_fg));
        const fgCell = hasMarket
          ? `${{fmtNum(r.estimate_fg)}} fg`
          : (r.heuristic_low_fg != null && r.heuristic_high_fg != null
              ? `~${{fmtNum(r.heuristic_low_fg)}}-${{fmtNum(r.heuristic_high_fg)}} fg*`
              : "");
        const sellCell = hasMarket && r.sell_hint_fg != null
          ? `${{fmtNum(r.sell_hint_fg)}} fg`
          : "";
        const rangeCell = hasMarket
          ? `${{fmtNum(r.range_low_fg)}}-${{fmtNum(r.range_high_fg)}}`
          : (r.heuristic_low_fg != null && r.heuristic_high_fg != null
              ? `seed:${{fmtNum(r.heuristic_low_fg)}}-${{fmtNum(r.heuristic_high_fg)}}`
              : "");
        const confLabel = isSeedOnly ? "seed" : (r.confidence || "");
        const confClass = isSeedOnly ? "medium" : conf;
        return `<tr>
          <td class="variant">${{esc(r.variant_key)}}</td>
          <td class="num">${{fgCell}}</td>
          <td class="num">${{sellCell}}</td>
          <td class="num">${{rangeCell}}</td>
          <td><span class="pill conf-${{confClass}}">${{esc(confLabel)}}</span></td>
          <td class="muted" title="${{esc(seedTitle)}}">${{esc(seedCell)}}</td>
          <td class="num">${{fmtNum(r.sample_count)}}</td>
          <td class="num">${{fmtNum(r.obs_total)}}</td>
          <td class="muted">${{esc(signalMix(r))}}</td>
          <td class="muted">${{esc(r.updated_at || "")}}</td>
          <td>${{source}}</td>
        </tr>`;
      }}).join("");
    }}

    $("q").addEventListener("input", (e) => {{ state.q = e.target.value; render(); }});
    $("conf").addEventListener("change", (e) => {{ state.conf = e.target.value; render(); }});
    $("seedTier").addEventListener("change", (e) => {{ state.seedTier = e.target.value; render(); }});
    $("minFg").addEventListener("input", (e) => {{
      const v = e.target.value.trim();
      state.minFg = v === "" ? null : Number(v);
      render();
    }});
    $("sort").addEventListener("change", (e) => {{ state.sort = e.target.value; render(); }});

    document.querySelectorAll("thead th[data-key]").forEach(th => {{
      th.addEventListener("click", () => {{
        const key = th.dataset.key;
        if (key === "estimate_fg") state.sort = state.sort === "estimate_desc" ? "estimate_asc" : "estimate_desc";
        else if (key === "sample_count") state.sort = "samples_desc";
        else if (key === "seed_tier") state.sort = "seed_desc";
        else if (key === "updated_at") state.sort = "updated_desc";
        else if (key === "variant_key") state.sort = "variant_asc";
        $("sort").value = state.sort;
        render();
      }});
    }});

    render();
  </script>
</body>
</html>
"""


def main() -> int:
    p = argparse.ArgumentParser(description="Export searchable HTML price table from d2lut SQLite DB")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key to export")
    p.add_argument("--out", default="data/cache/price_table.html", help="Output HTML file")
    p.add_argument("--min-fg", type=float, default=None, help="Optional minimum estimate_fg to include")
    p.add_argument(
        "--seed-file",
        default="config/expert_trade_seeds.d2r.minimal.json",
        help="Optional JSON file with important-only expert trade value seeds (D2R)",
    )
    p.add_argument(
        "--include-seed-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include seed-only rows without market estimate_fg and attach heuristic FG ranges by seed tier",
    )
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    seed_entries = _load_seed_entries(Path(args.seed_file) if args.seed_file else None)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        where_min = "AND pe.estimate_fg >= ?" if args.min_fg is not None else ""
        params = [args.market_key]
        if args.min_fg is not None:
            params.append(args.min_fg)

        query = f"""
        WITH obs AS (
          SELECT
            market_key,
            variant_key,
            COUNT(*) AS obs_total,
            SUM(CASE WHEN signal_kind='bin' THEN 1 ELSE 0 END) AS bin_count,
            SUM(CASE WHEN signal_kind='sold' THEN 1 ELSE 0 END) AS sold_count,
            SUM(CASE WHEN signal_kind='co' THEN 1 ELSE 0 END) AS co_count,
            SUM(CASE WHEN signal_kind='ask' THEN 1 ELSE 0 END) AS ask_count,
            MAX(price_fg) AS obs_max_fg,
            MAX(CASE WHEN signal_kind='bin' THEN price_fg END) AS bin_max_fg,
            MAX(observed_at) AS last_observed_at
          FROM observed_prices
          WHERE market_key = ?
          GROUP BY market_key, variant_key
        ),
        latest_src AS (
          SELECT o.market_key, o.variant_key, o.source_url AS last_source_url
          FROM observed_prices o
          JOIN (
            SELECT market_key, variant_key, MAX(COALESCE(observed_at, '')) AS max_observed_at
            FROM observed_prices
            WHERE market_key = ?
            GROUP BY market_key, variant_key
          ) t
            ON o.market_key = t.market_key
           AND o.variant_key = t.variant_key
           AND COALESCE(o.observed_at, '') = t.max_observed_at
          WHERE o.market_key = ?
        )
        SELECT
          pe.market_key,
          pe.variant_key,
          pe.estimate_fg,
          pe.range_low_fg,
          pe.range_high_fg,
          pe.confidence,
          pe.sample_count,
          pe.updated_at,
          COALESCE(obs.obs_total, 0) AS obs_total,
          COALESCE(obs.bin_count, 0) AS bin_count,
          COALESCE(obs.sold_count, 0) AS sold_count,
          COALESCE(obs.co_count, 0) AS co_count,
          COALESCE(obs.ask_count, 0) AS ask_count,
          obs.obs_max_fg,
          obs.bin_max_fg,
          ls.last_source_url
        FROM price_estimates pe
        LEFT JOIN obs
          ON pe.market_key = obs.market_key
         AND pe.variant_key = obs.variant_key
        LEFT JOIN latest_src ls
          ON pe.market_key = ls.market_key
         AND pe.variant_key = ls.variant_key
        WHERE pe.market_key = ?
          {where_min}
        ORDER BY pe.estimate_fg DESC, pe.sample_count DESC, pe.variant_key ASC
        """
        # params order for placeholders: obs market, latest subquery market, latest outer market, pe market, [min]
        qparams = [args.market_key, args.market_key, args.market_key, args.market_key]
        if args.min_fg is not None:
            qparams.append(args.min_fg)
        rows = [dict(r) for r in conn.execute(query, qparams).fetchall()]
    finally:
        conn.close()

    for r in rows:
        tier, tags, seed_meta = _seed_tier_for_variant(str(r.get("variant_key") or ""), seed_entries)
        r["seed_tier"] = tier
        r["seed_tags"] = tags
        r["seed_stat_priority"] = list(seed_meta.get("stat_priority") or [])
        r["seed_seasonality_notes"] = seed_meta.get("seasonality_notes")
        r["seed_notes"] = seed_meta.get("notes")
        r["seed_source_name"] = seed_meta.get("source_name") if seed_meta else None
        r["is_seed_only"] = 0
        r["heuristic_low_fg"] = None
        r["heuristic_high_fg"] = None
        est = float(r["estimate_fg"]) if r.get("estimate_fg") is not None else 0.0
        rng_hi = float(r["range_high_fg"]) if r.get("range_high_fg") is not None else 0.0
        bin_hi = float(r["bin_max_fg"]) if r.get("bin_max_fg") is not None else 0.0
        obs_hi = float(r["obs_max_fg"]) if r.get("obs_max_fg") is not None else 0.0
        sell_hint = max(est, rng_hi, bin_hi)
        if int(r.get("sample_count") or 0) <= 3 and obs_hi > sell_hint:
            sell_hint = obs_hi
        r["sell_hint_fg"] = round(sell_hint, 1) if sell_hint > 0 else None

    if args.include_seed_only:
        tier_ranges = _heuristic_ranges_by_tier(rows)
        rows.extend(_build_seed_only_rows(rows, tier_ranges, seed_entries))
    for r in rows:
        r.setdefault("sell_hint_fg", r.get("heuristic_high_fg") or r.get("estimate_fg"))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_build_html(args.market_key, rows), encoding="utf-8")
    seed_only_count = sum(1 for r in rows if r.get("is_seed_only"))
    print(
        f"exported rows={len(rows)} seed_only={seed_only_count} market={args.market_key} out={out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
