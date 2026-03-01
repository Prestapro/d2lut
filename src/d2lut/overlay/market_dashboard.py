"""Browser market dashboard — searchable, filterable, self-contained HTML.

Reads ``price_estimates`` (and optionally ``refresh_metadata``) from the
d2lut SQLite DB and produces a single HTML file with:

* Category filters (weapons, armor, runes, charms, jewels, uniques, sets,
  runewords, bases, other)
* Confidence filter (all / high / medium / low)
* Freshness indicator from ``refresh_metadata.last_success_at``
* Sample-count column
* Premium uplift column (baseline vs premium for items in ``ROLL_RANGES``)
* Market refresh status bar (last refresh, next scheduled, deltas)
* Dark theme consistent with ``valuation_export.py``
"""

from __future__ import annotations

import html
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Sequence

from d2lut.overlay.premium_pricing import ROLL_RANGES

# ---------------------------------------------------------------------------
# Category classification
# ---------------------------------------------------------------------------

_PREFIX_CATEGORY_MAP: dict[str, str] = {
    "rune:": "runes",
    "unique:": "uniques",
    "runeword:": "runewords",
    "set:": "sets",
    "base:": "bases",
    "charm:": "charms",
    "jewel:": "jewels",
}

# Keyword fallback for variant_keys without a colon prefix
_KEYWORD_CATEGORY_MAP: dict[str, str] = {
    "weapon": "weapons",
    "armor": "armor",
    "helm": "armor",
    "shield": "armor",
    "boot": "armor",
    "glove": "armor",
    "belt": "armor",
    "sword": "weapons",
    "axe": "weapons",
    "mace": "weapons",
    "polearm": "weapons",
    "spear": "weapons",
    "bow": "weapons",
    "crossbow": "weapons",
    "javelin": "weapons",
    "dagger": "weapons",
    "scepter": "weapons",
    "wand": "weapons",
    "staff": "weapons",
    "claw": "weapons",
    "orb": "weapons",
}

CATEGORIES = [
    "all", "weapons", "armor", "runes", "charms", "jewels",
    "uniques", "sets", "runewords", "bases", "other",
]


def classify_category(variant_key: str) -> str:
    """Classify a variant_key into a dashboard category."""
    vk = variant_key.lower()
    for prefix, cat in _PREFIX_CATEGORY_MAP.items():
        if vk.startswith(prefix):
            return cat
    for kw, cat in _KEYWORD_CATEGORY_MAP.items():
        if kw in vk:
            return cat
    return "other"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DashboardRow:
    """Single row in the market dashboard."""

    variant_key: str
    category: str
    estimate_fg: float | None
    range_low_fg: float | None
    range_high_fg: float | None
    confidence: str | None
    sample_count: int
    updated_at: str | None
    # Premium fields (None when not applicable)
    premium_class: str | None = None
    premium_multiplier: float | None = None
    premium_price_fg: float | None = None


@dataclass
class RefreshInfo:
    """Refresh status for the dashboard header."""

    last_success_at: str | None = None
    last_refresh_at: str | None = None
    observations_delta: int | None = None
    estimates_delta: int | None = None
    last_error: str | None = None


@dataclass
class DashboardData:
    """All data needed to render the dashboard."""

    rows: list[DashboardRow] = field(default_factory=list)
    refresh: RefreshInfo = field(default_factory=RefreshInfo)
    market_key: str = "d2r_sc_ladder"
    generated_at: str = ""


# ---------------------------------------------------------------------------
# DB queries
# ---------------------------------------------------------------------------

def load_dashboard_data(
    db_path: str | Path,
    market_key: str = "d2r_sc_ladder",
) -> DashboardData:
    """Load price estimates and refresh metadata from the DB."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = _load_price_rows(conn, market_key)
        refresh = _load_refresh_info(conn)
    finally:
        conn.close()

    return DashboardData(
        rows=rows,
        refresh=refresh,
        market_key=market_key,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def _load_price_rows(
    conn: sqlite3.Connection,
    market_key: str,
) -> list[DashboardRow]:
    query = """
    SELECT
        pe.variant_key,
        pe.estimate_fg,
        pe.range_low_fg,
        pe.range_high_fg,
        pe.confidence,
        pe.sample_count,
        pe.updated_at
    FROM price_estimates pe
    WHERE pe.market_key = ?
    ORDER BY pe.estimate_fg DESC, pe.sample_count DESC
    """
    out: list[DashboardRow] = []
    for r in conn.execute(query, (market_key,)):
        vk = r["variant_key"] or ""
        cat = classify_category(vk)
        est = r["estimate_fg"]

        # Premium uplift detection
        pclass, pmult, pprice = _detect_premium(vk, est)

        out.append(DashboardRow(
            variant_key=vk,
            category=cat,
            estimate_fg=est,
            range_low_fg=r["range_low_fg"],
            range_high_fg=r["range_high_fg"],
            confidence=r["confidence"],
            sample_count=r["sample_count"] or 0,
            updated_at=r["updated_at"],
            premium_class=pclass,
            premium_multiplier=pmult,
            premium_price_fg=pprice,
        ))
    return out


def _detect_premium(
    variant_key: str,
    estimate_fg: float | None,
) -> tuple[str | None, float | None, float | None]:
    """Check if variant_key matches a ROLL_RANGES class.

    Returns (premium_class, max_multiplier, premium_price_at_max) or
    (None, None, None) when not applicable.
    """
    if estimate_fg is None:
        return None, None, None
    vk = variant_key.lower()
    for cls_key in ROLL_RANGES:
        # Match prefix or exact (e.g. "torch" in "unique:hellfire_torch:sorceress")
        if cls_key in vk:
            from d2lut.overlay.premium_pricing import DEFAULT_TIER_MULTIPLIERS
            max_mult = DEFAULT_TIER_MULTIPLIERS.get("perfect", 2.5)
            return cls_key, max_mult, round(estimate_fg * max_mult, 1)
    return None, None, None


def _load_refresh_info(conn: sqlite3.Connection) -> RefreshInfo:
    """Load latest refresh metadata (best-effort; table may not exist)."""
    info = RefreshInfo()
    try:
        row = conn.execute(
            "SELECT * FROM refresh_metadata ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            info.last_refresh_at = row["started_at"]
            if row["success"]:
                info.last_success_at = row["finished_at"]
            info.observations_delta = row["observations_delta"]
            info.estimates_delta = row["estimates_delta"]
            info.last_error = row["last_error"]
        # Also check for the most recent *successful* refresh
        srow = conn.execute(
            "SELECT finished_at FROM refresh_metadata "
            "WHERE success = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if srow:
            info.last_success_at = srow["finished_at"]
    except sqlite3.OperationalError:
        pass  # table doesn't exist yet
    return info


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def _rows_to_json(rows: Sequence[DashboardRow]) -> str:
    out = []
    for r in rows:
        out.append({
            "vk": r.variant_key,
            "cat": r.category,
            "fg": r.estimate_fg,
            "lo": r.range_low_fg,
            "hi": r.range_high_fg,
            "conf": r.confidence,
            "samples": r.sample_count,
            "updated": r.updated_at,
            "pcls": r.premium_class,
            "pmult": r.premium_multiplier,
            "pprice": r.premium_price_fg,
        })
    return json.dumps(out, ensure_ascii=False)


def _refresh_to_json(info: RefreshInfo) -> str:
    return json.dumps({
        "last_success": info.last_success_at,
        "last_refresh": info.last_refresh_at,
        "obs_delta": info.observations_delta,
        "est_delta": info.estimates_delta,
        "last_error": info.last_error,
    }, ensure_ascii=False)


def build_dashboard_html(data: DashboardData) -> str:
    """Build a self-contained HTML market dashboard.

    Parameters
    ----------
    data:
        Pre-loaded ``DashboardData`` (from ``load_dashboard_data``).
    """
    payload = _rows_to_json(data.rows)
    refresh_json = _refresh_to_json(data.refresh)
    title = html.escape(f"Market Dashboard — {data.market_key}")
    ts = html.escape(data.generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    total_items = len(data.rows)
    priced = sum(1 for r in data.rows if r.estimate_fg is not None)
    premium_count = sum(1 for r in data.rows if r.premium_class is not None)

    return _DASHBOARD_TEMPLATE.format(
        title=title,
        timestamp=ts,
        market_key=html.escape(data.market_key),
        payload=payload,
        refresh_json=refresh_json,
        total_items=total_items,
        priced_items=priced,
        premium_items=premium_count,
    )


# ---------------------------------------------------------------------------
# Convenience: load + build in one call
# ---------------------------------------------------------------------------

def export_dashboard(
    db_path: str | Path,
    out_path: str | Path,
    market_key: str = "d2r_sc_ladder",
) -> Path:
    """Load data from DB and write dashboard HTML to *out_path*.

    Returns the resolved output path.
    """
    data = load_dashboard_data(db_path, market_key)
    html_str = build_dashboard_html(data)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_str, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# HTML template — self-contained, inline CSS + JS, dark theme
# ---------------------------------------------------------------------------

_DASHBOARD_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #0b1118; --panel: #101923; --line: #223042;
      --text: #dbe6f3; --muted: #93a5bb;
      --good: #7dd3fc; --warn: #fde68a; --bad: #fca5a5; --accent: #86efac;
      --gold: #f59e0b; --highlight-row: rgba(245,158,11,0.10);
      --premium-row: rgba(134,239,172,0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 16px;
      background: radial-gradient(circle at 20% 0%, #16202d, var(--bg));
      color: var(--text);
      font: 14px/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }}
    .wrap {{ max-width: 1400px; margin: 0 auto; }}
    h1 {{ font-size: 18px; margin: 0 0 4px; }}
    .ts {{ color: var(--muted); font-size: 12px; margin-bottom: 12px; }}
    /* --- refresh status bar --- */
    .refresh-bar {{
      display: flex; gap: 16px; flex-wrap: wrap; align-items: center;
      background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
      padding: 8px 14px; margin-bottom: 8px; font-size: 12px;
    }}
    .refresh-bar .lbl {{ color: var(--muted); }}
    .refresh-bar .val {{ font-weight: 700; }}
    .refresh-bar .fresh {{ color: var(--accent); }}
    .refresh-bar .stale {{ color: var(--warn); }}
    .refresh-bar .err {{ color: var(--bad); }}
    /* --- stats bar --- */
    .stats {{
      display: flex; gap: 16px; flex-wrap: wrap;
      background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
      padding: 10px 14px; margin-bottom: 12px; font-size: 13px;
    }}
    .stats span {{ white-space: nowrap; }}
    .stats .lbl {{ color: var(--muted); }}
    .stats .val {{ font-weight: 700; }}
    .stats .val-gold {{ color: var(--gold); font-weight: 700; }}
    /* --- filter bar --- */
    .bar {{
      display: grid; grid-template-columns: 1fr auto auto auto auto; gap: 8px;
      background: color-mix(in srgb, var(--panel) 92%, black);
      border: 1px solid var(--line); border-radius: 12px; padding: 10px;
      position: sticky; top: 0; backdrop-filter: blur(8px); z-index: 5;
    }}
    input, select {{
      background: #0b141d; color: var(--text); border: 1px solid var(--line);
      border-radius: 8px; padding: 8px 10px;
    }}
    /* --- table --- */
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
    .conf-high {{ color: var(--accent); }}
    .conf-medium {{ color: var(--warn); }}
    .conf-low {{ color: var(--bad); }}
    .row-highvalue {{ background: var(--highlight-row); }}
    .row-premium {{ background: var(--premium-row); }}
    .tag {{
      display: inline-block; padding: 1px 6px; border-radius: 4px;
      font-size: 11px; margin-left: 4px;
    }}
    .tag-cat {{ background: rgba(125,211,252,0.12); color: var(--good); }}
    .tag-prem {{ background: rgba(134,239,172,0.15); color: var(--accent); }}
    .empty {{ color: var(--muted); padding: 18px 10px; }}
    .meta {{ color: var(--muted); margin: 4px 2px 8px; font-size: 12px; }}
    @media (max-width: 900px) {{
      .bar {{ grid-template-columns: 1fr 1fr; }}
      thead th:nth-child(7), tbody td:nth-child(7),
      thead th:nth-child(8), tbody td:nth-child(8) {{ display: none; }}
    }}
  </style>
</head>
<body>
<div class="wrap">
  <h1>{title}</h1>
  <div class="ts">Generated {timestamp}</div>
  <div class="refresh-bar" id="refreshBar"></div>
  <div class="stats">
    <span><span class="lbl">Items:</span> <span class="val">{total_items}</span></span>
    <span><span class="lbl">Priced:</span> <span class="val">{priced_items}</span></span>
    <span><span class="lbl">Premium-eligible:</span> <span class="val-gold">{premium_items}</span></span>
  </div>
  <div class="bar">
    <input id="q" type="search" placeholder="Search variant key…">
    <select id="cat">
      <option value="">All categories</option>
      <option value="weapons">Weapons</option>
      <option value="armor">Armor</option>
      <option value="runes">Runes</option>
      <option value="charms">Charms</option>
      <option value="jewels">Jewels</option>
      <option value="uniques">Uniques</option>
      <option value="sets">Sets</option>
      <option value="runewords">Runewords</option>
      <option value="bases">Bases</option>
      <option value="other">Other</option>
    </select>
    <select id="conf">
      <option value="">All confidence</option>
      <option value="high">High</option>
      <option value="medium">Medium</option>
      <option value="low">Low</option>
    </select>
    <select id="sort">
      <option value="fg_desc">FG high &rarr; low</option>
      <option value="fg_asc">FG low &rarr; high</option>
      <option value="name_asc">Name A &rarr; Z</option>
      <option value="samples_desc">Samples high &rarr; low</option>
    </select>
  </div>
  <div class="meta" id="meta"></div>
  <table>
    <thead><tr>
      <th>Variant</th>
      <th>Category</th>
      <th class="num">FG</th>
      <th class="num">Range</th>
      <th>Confidence</th>
      <th class="num">Samples</th>
      <th class="num">Premium</th>
      <th>Updated</th>
    </tr></thead>
    <tbody id="rows"></tbody>
  </table>
</div>
<script>
const DATA={payload};
const REFRESH={refresh_json};
const st={{q:"",cat:"",conf:"",sort:"fg_desc"}};
const $=id=>document.getElementById(id);
const tbody=$("rows"), meta=$("meta");
function esc(s){{return String(s??"").replace(/[&<>"]/g,c=>({{
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));}}
function fmtN(v){{if(v==null||Number.isNaN(v))return"";return Math.round(Number(v)).toLocaleString();}}
function fgVal(r){{return r.fg!=null?Number(r.fg):-1;}}
/* refresh bar */
(function renderRefresh(){{
  const bar=$("refreshBar");
  if(!REFRESH){{bar.style.display="none";return;}}
  let parts=[];
  if(REFRESH.last_success){{
    const ago=timeSince(REFRESH.last_success);
    const cls=ago.mins<60?"fresh":ago.mins<1440?"stale":"err";
    parts.push('<span class="lbl">Last success:</span> <span class="val '+cls+'">'+esc(REFRESH.last_success)+' ('+ago.text+')</span>');
  }} else {{
    parts.push('<span class="lbl">Last success:</span> <span class="val err">never</span>');
  }}
  if(REFRESH.obs_delta!=null) parts.push('<span class="lbl">&Delta; obs:</span> <span class="val">'+(REFRESH.obs_delta>=0?"+":"")+REFRESH.obs_delta+'</span>');
  if(REFRESH.est_delta!=null) parts.push('<span class="lbl">&Delta; est:</span> <span class="val">'+(REFRESH.est_delta>=0?"+":"")+REFRESH.est_delta+'</span>');
  if(REFRESH.last_error) parts.push('<span class="lbl">Error:</span> <span class="err">'+esc(REFRESH.last_error)+'</span>');
  bar.innerHTML=parts.join(" ");
}})();
function timeSince(ts){{
  try{{
    const d=new Date(ts.replace(" ","T"));
    const mins=Math.round((Date.now()-d.getTime())/60000);
    if(mins<1)return{{mins:0,text:"just now"}};
    if(mins<60)return{{mins,text:mins+"m ago"}};
    if(mins<1440)return{{mins,text:Math.round(mins/60)+"h ago"}};
    return{{mins,text:Math.round(mins/1440)+"d ago"}};
  }}catch(e){{return{{mins:99999,text:"unknown"}};}}
}}
/* sorting */
function cmp(a,b){{
  switch(st.sort){{
    case"fg_asc":return fgVal(a)-fgVal(b);
    case"name_asc":return(a.vk||"").localeCompare(b.vk||"");
    case"samples_desc":return(b.samples??0)-(a.samples??0)||fgVal(b)-fgVal(a);
    default:return fgVal(b)-fgVal(a);
  }}
}}
/* filtering */
function filt(rows){{
  const q=st.q.trim().toLowerCase();
  return rows.filter(r=>{{
    if(st.cat&&r.cat!==st.cat)return false;
    if(st.conf&&(r.conf||"").toLowerCase()!==st.conf)return false;
    if(!q)return true;
    return(r.vk||"").toLowerCase().includes(q)||(r.cat||"").includes(q);
  }});
}}
/* render */
function render(){{
  const rows=filt(DATA).sort(cmp);
  meta.textContent="Showing "+rows.length+" / "+DATA.length+" items";
  if(!rows.length){{tbody.innerHTML='<tr><td colspan="8" class="empty">No items match filters.</td></tr>';return;}}
  tbody.innerHTML=rows.map(r=>{{
    const isHV=r.fg!=null&&r.fg>=300;
    const isPrem=!!r.pcls;
    const cls=isPrem?"row-premium":isHV?"row-highvalue":"";
    const confLbl=(r.conf||"").toLowerCase();
    const confCls=confLbl?("conf-"+confLbl):"";
    const premCell=isPrem?fmtN(r.fg)+" &rarr; "+fmtN(r.pprice)+" fg <span class='tag tag-prem'>"+esc(r.pcls)+"</span>":"";
    const rangeCell=r.lo!=null?fmtN(r.lo)+"–"+fmtN(r.hi):"";
    return'<tr class="'+cls+'">'
      +'<td>'+esc(r.vk)+'</td>'
      +'<td><span class="tag tag-cat">'+esc(r.cat)+'</span></td>'
      +'<td class="num">'+(r.fg!=null?fmtN(r.fg)+" fg":"")+'</td>'
      +'<td class="num muted">'+rangeCell+'</td>'
      +'<td>'+(confLbl?'<span class="pill '+confCls+'">'+esc(confLbl)+'</span>':"")+'</td>'
      +'<td class="num">'+fmtN(r.samples)+'</td>'
      +'<td class="num">'+premCell+'</td>'
      +'<td class="muted">'+esc(r.updated||"")+'</td>'
      +'</tr>';
  }}).join("");
}}
$("q").addEventListener("input",e=>{{st.q=e.target.value;render();}});
$("cat").addEventListener("change",e=>{{st.cat=e.target.value;render();}});
$("conf").addEventListener("change",e=>{{st.conf=e.target.value;render();}});
$("sort").addEventListener("change",e=>{{st.sort=e.target.value;render();}});
render();
</script>
</body>
</html>"""
