"""Export inventory/stash scan results as self-contained HTML valuation tables.

Produces browser-viewable HTML with inline CSS/JS for filtering, sorting,
and highlighting valuable or missing-data items.  Compatible with
``StashScanner`` / ``StashScanResult`` output.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Sequence


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ValuationItem:
    """Flat representation of a scanned item for export."""

    slot_index: int
    item_name: str
    canonical_item_id: str | None = None
    match_confidence: float = 0.0
    match_type: str = ""
    price_fg: float | None = None
    price_low_fg: float | None = None
    price_high_fg: float | None = None
    price_confidence: str | None = None
    sample_count: int | None = None
    has_price: bool = False


@dataclass
class ValuationSummary:
    """Aggregate stats for a valuation export."""

    total_value_fg: float = 0.0
    item_count: int = 0
    priced_count: int = 0
    no_data_count: int = 0
    high_value_count: int = 0


@dataclass
class ValuationExportConfig:
    """Configuration for HTML valuation export."""

    title: str = "Inventory Valuation"
    min_fg: float = 0.0
    high_value_threshold: float = 300.0
    show_no_data: bool = True
    min_confidence: str | None = None  # None = all; "low"/"medium"/"high"
    export_type: str = "inventory"  # "inventory" or "stash"


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}


def _passes_confidence(item_conf: str | None, min_conf: str | None) -> bool:
    if min_conf is None:
        return True
    return CONFIDENCE_RANK.get((item_conf or "").lower(), 0) >= CONFIDENCE_RANK.get(min_conf.lower(), 0)


def items_from_scan_result(scan_result: Any) -> list[ValuationItem]:
    """Convert a ``StashScanResult`` (or compatible dict list) to flat items."""
    # Accept either a StashScanResult object or a plain list[dict]
    if hasattr(scan_result, "items"):
        raw_items = scan_result.items  # StashScanResult.items
        out: list[ValuationItem] = []
        for si in raw_items:
            pe = si.price_estimate
            out.append(ValuationItem(
                slot_index=si.slot_index,
                item_name=si.match_result.matched_name or (si.parsed_item.item_name if si.parsed_item else None) or "Unknown",
                canonical_item_id=si.match_result.canonical_item_id,
                match_confidence=si.match_result.confidence,
                match_type=si.match_result.match_type,
                price_fg=pe.estimate_fg if pe else None,
                price_low_fg=pe.range_low_fg if pe else None,
                price_high_fg=pe.range_high_fg if pe else None,
                price_confidence=pe.confidence if pe else None,
                sample_count=pe.sample_count if pe else None,
                has_price=pe is not None,
            ))
        return out
    # Assume list[dict] (e.g. from JSON)
    if isinstance(scan_result, list):
        return [_dict_to_item(d) for d in scan_result]
    raise TypeError(f"Unsupported scan_result type: {type(scan_result)}")


def _dict_to_item(d: dict) -> ValuationItem:
    return ValuationItem(
        slot_index=d.get("slot_index", 0),
        item_name=d.get("item_name") or "Unknown",
        canonical_item_id=d.get("canonical_item_id"),
        match_confidence=d.get("match_confidence", 0.0),
        match_type=d.get("match_type", ""),
        price_fg=d.get("price_fg"),
        price_low_fg=d.get("price_low_fg"),
        price_high_fg=d.get("price_high_fg"),
        price_confidence=d.get("price_confidence"),
        sample_count=d.get("sample_count"),
        has_price=bool(d.get("has_price", d.get("price_fg") is not None)),
    )


# ---------------------------------------------------------------------------
# Filtering / summarisation
# ---------------------------------------------------------------------------

def filter_items(
    items: Sequence[ValuationItem],
    cfg: ValuationExportConfig,
) -> list[ValuationItem]:
    """Apply min-fg, confidence, and no-data filters."""
    out: list[ValuationItem] = []
    for it in items:
        if not it.has_price:
            if cfg.show_no_data:
                out.append(it)
            continue
        if it.price_fg is not None and it.price_fg < cfg.min_fg:
            continue
        if not _passes_confidence(it.price_confidence, cfg.min_confidence):
            continue
        out.append(it)
    return out


def compute_summary(
    items: Sequence[ValuationItem],
    high_value_threshold: float = 300.0,
) -> ValuationSummary:
    s = ValuationSummary(item_count=len(items))
    for it in items:
        if it.has_price and it.price_fg is not None:
            s.total_value_fg += it.price_fg
            s.priced_count += 1
            if it.price_fg >= high_value_threshold:
                s.high_value_count += 1
        else:
            s.no_data_count += 1
    return s


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def _items_to_json(items: Sequence[ValuationItem]) -> str:
    rows = []
    for it in items:
        rows.append({
            "slot": it.slot_index,
            "name": it.item_name,
            "cid": it.canonical_item_id,
            "mconf": round(it.match_confidence, 2),
            "mtype": it.match_type,
            "fg": it.price_fg,
            "lo": it.price_low_fg,
            "hi": it.price_high_fg,
            "conf": it.price_confidence,
            "samples": it.sample_count,
            "has_price": it.has_price,
        })
    return json.dumps(rows, ensure_ascii=False)


def build_valuation_html(
    items: Sequence[ValuationItem],
    cfg: ValuationExportConfig | None = None,
) -> str:
    """Build a self-contained HTML valuation table.

    Parameters
    ----------
    items:
        Pre-filtered list of ``ValuationItem`` (call ``filter_items`` first
        if you want server-side filtering; the HTML also has client-side
        filters).
    cfg:
        Export configuration.  Defaults are sensible for inventory export.
    """
    if cfg is None:
        cfg = ValuationExportConfig()

    summary = compute_summary(items, cfg.high_value_threshold)
    payload = _items_to_json(items)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title_esc = html.escape(cfg.title)
    hv_thresh = cfg.high_value_threshold

    return _HTML_TEMPLATE.format(
        title=title_esc,
        timestamp=ts,
        payload=payload,
        hv_threshold=hv_thresh,
        summary_total=f"{summary.total_value_fg:,.0f}",
        summary_items=summary.item_count,
        summary_priced=summary.priced_count,
        summary_nodata=summary.no_data_count,
        summary_highvalue=summary.high_value_count,
        export_type=cfg.export_type,
    )


# ---------------------------------------------------------------------------
# HTML template (self-contained, inline CSS + JS)
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """<!doctype html>
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
      --nodata-row: rgba(252,165,165,0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 16px;
      background: radial-gradient(circle at 20% 0%, #16202d, var(--bg));
      color: var(--text);
      font: 14px/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }}
    .wrap {{ max-width: 1200px; margin: 0 auto; }}
    h1 {{ font-size: 18px; margin: 0 0 4px; }}
    .ts {{ color: var(--muted); font-size: 12px; margin-bottom: 12px; }}
    .stats {{
      display: flex; gap: 16px; flex-wrap: wrap;
      background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
      padding: 10px 14px; margin-bottom: 12px; font-size: 13px;
    }}
    .stats span {{ white-space: nowrap; }}
    .stats .lbl {{ color: var(--muted); }}
    .stats .val {{ font-weight: 700; }}
    .stats .val-gold {{ color: var(--gold); font-weight: 700; }}
    .stats .val-bad {{ color: var(--bad); font-weight: 700; }}
    .bar {{
      display: grid; grid-template-columns: 1fr auto auto auto; gap: 8px;
      background: color-mix(in srgb, var(--panel) 92%, black);
      border: 1px solid var(--line); border-radius: 12px; padding: 10px;
      position: sticky; top: 0; backdrop-filter: blur(8px); z-index: 5;
    }}
    input, select {{
      background: #0b141d; color: var(--text); border: 1px solid var(--line);
      border-radius: 8px; padding: 8px 10px;
    }}
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
    .row-nodata {{ background: var(--nodata-row); }}
    .tag {{
      display: inline-block; padding: 1px 6px; border-radius: 4px;
      font-size: 11px; margin-left: 4px;
    }}
    .tag-hv {{ background: rgba(245,158,11,0.2); color: var(--gold); }}
    .tag-nd {{ background: rgba(252,165,165,0.15); color: var(--bad); }}
    .empty {{ color: var(--muted); padding: 18px 10px; }}
    .meta {{ color: var(--muted); margin: 4px 2px 8px; font-size: 12px; }}
    @media (max-width: 800px) {{
      .bar {{ grid-template-columns: 1fr 1fr; }}
      thead th:nth-child(6), tbody td:nth-child(6),
      thead th:nth-child(7), tbody td:nth-child(7) {{ display: none; }}
    }}
  </style>
</head>
<body>
<div class="wrap">
  <h1>{title}</h1>
  <div class="ts">Generated {timestamp} | type: {export_type}</div>
  <div class="stats">
    <span><span class="lbl">Total value:</span> <span class="val-gold">{summary_total} fg</span></span>
    <span><span class="lbl">Items:</span> <span class="val">{summary_items}</span></span>
    <span><span class="lbl">Priced:</span> <span class="val">{summary_priced}</span></span>
    <span><span class="lbl">No data:</span> <span class="val-bad">{summary_nodata}</span></span>
    <span><span class="lbl">High value (&ge;{hv_threshold:.0f}fg):</span> <span class="val-gold">{summary_highvalue}</span></span>
  </div>
  <div class="bar">
    <input id="q" type="search" placeholder="Search item name / id">
    <input id="minFg" type="number" min="0" step="1" placeholder="Min fg">
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
      <option value="nodata_first">No-data first</option>
    </select>
  </div>
  <div class="meta" id="meta"></div>
  <table>
    <thead><tr>
      <th data-key="slot">#</th>
      <th data-key="name">Item</th>
      <th data-key="fg" class="num">FG</th>
      <th data-key="range" class="num">Range</th>
      <th data-key="conf">Conf</th>
      <th data-key="samples" class="num">Samples</th>
      <th data-key="mconf" class="num">Match</th>
    </tr></thead>
    <tbody id="rows"></tbody>
  </table>
</div>
<script>
const DATA={payload};
const HV={hv_threshold};
const st={{q:"",minFg:null,conf:"",sort:"fg_desc"}};
const $=id=>document.getElementById(id);
const tbody=$("rows"), meta=$("meta");
function esc(s){{return String(s??"").replace(/[&<>"]/g,c=>({{
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));}}
function fmtN(v){{if(v==null||Number.isNaN(v))return"";return Math.round(Number(v)).toLocaleString();}}
function fgVal(r){{return r.has_price&&r.fg!=null?Number(r.fg):-1;}}
function cmp(a,b){{
  switch(st.sort){{
    case"fg_asc":return fgVal(a)-fgVal(b);
    case"name_asc":return(a.name||"").localeCompare(b.name||"");
    case"samples_desc":return(b.samples??0)-(a.samples??0)||fgVal(b)-fgVal(a);
    case"nodata_first":return(a.has_price?1:0)-(b.has_price?1:0)||fgVal(b)-fgVal(a);
    default:return fgVal(b)-fgVal(a);
  }}
}}
function filt(rows){{
  const q=st.q.trim().toLowerCase();
  return rows.filter(r=>{{
    if(st.conf&&(r.conf||"").toLowerCase()!==st.conf)return false;
    if(st.minFg!=null&&fgVal(r)<st.minFg)return false;
    if(!q)return true;
    return[r.name,r.cid,r.mtype].join(" ").toLowerCase().includes(q);
  }});
}}
function render(){{
  const rows=filt(DATA).sort(cmp);
  meta.textContent="Showing "+rows.length+" / "+DATA.length+" items";
  if(!rows.length){{tbody.innerHTML='<tr><td colspan="7" class="empty">No items match filters.</td></tr>';return;}}
  tbody.innerHTML=rows.map(r=>{{
    const isHV=r.has_price&&r.fg!=null&&r.fg>=HV;
    const isND=!r.has_price;
    const cls=isHV?"row-highvalue":isND?"row-nodata":"";
    const fgCell=r.has_price?fmtN(r.fg)+" fg":"";
    const rangeCell=r.has_price&&r.lo!=null?fmtN(r.lo)+"-"+fmtN(r.hi):"";
    const confLbl=r.has_price?(r.conf||""):"";
    const confCls=confLbl?("conf-"+confLbl.toLowerCase()):"";
    const tags=(isHV?'<span class="tag tag-hv">HIGH VALUE</span>':"")+(isND?'<span class="tag tag-nd">NO DATA</span>':"");
    return'<tr class="'+cls+'">'
      +'<td class="num">'+(r.slot+1)+'</td>'
      +'<td>'+esc(r.name)+tags+'</td>'
      +'<td class="num">'+fgCell+'</td>'
      +'<td class="num muted">'+rangeCell+'</td>'
      +'<td>'+(confLbl?'<span class="pill '+confCls+'">'+esc(confLbl)+'</span>':(isND?'<span class="pill conf-low">no data</span>':""))+'</td>'
      +'<td class="num muted">'+fmtN(r.samples)+'</td>'
      +'<td class="num muted">'+(r.mconf!=null?Math.round(r.mconf*100)+"%":"")+'</td>'
      +'</tr>';
  }}).join("");
}}
$("q").addEventListener("input",e=>{{st.q=e.target.value;render();}});
$("minFg").addEventListener("input",e=>{{const v=e.target.value.trim();st.minFg=v===""?null:Number(v);render();}});
$("conf").addEventListener("change",e=>{{st.conf=e.target.value;render();}});
$("sort").addEventListener("change",e=>{{st.sort=e.target.value;render();}});
render();
</script>
</body>
</html>"""
