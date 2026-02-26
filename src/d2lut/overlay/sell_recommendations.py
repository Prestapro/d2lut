"""Sell recommendations engine for inventory/stash items.

Classifies items into actionable recommendation tags, detects duplicates
and excess inventory, estimates quick-sell totals, and prioritises items
for a manual listing workflow.

Recommendation tags
-------------------
- ``sell_now``       – liquid commodity with decent confidence; list immediately
- ``check_roll``     – premium potential; verify roll before pricing
- ``keep``           – high-tier roll or explicitly retained
- ``low_confidence`` – price data exists but confidence is weak
- ``no_market_data`` – no price estimate at all
"""

from __future__ import annotations

import html
import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Sequence

from d2lut.overlay.premium_pricing import PremiumEstimate
from d2lut.overlay.valuation_export import ValuationItem

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SELL_NOW = "sell_now"
CHECK_ROLL = "check_roll"
KEEP = "keep"
LOW_CONFIDENCE = "low_confidence"
NO_MARKET_DATA = "no_market_data"

ALL_TAGS = (SELL_NOW, CHECK_ROLL, KEEP, LOW_CONFIDENCE, NO_MARKET_DATA)

# Priority ordering (lower = higher priority in output)
_TAG_PRIORITY: dict[str, int] = {
    SELL_NOW: 0,
    CHECK_ROLL: 1,
    KEEP: 2,
    LOW_CONFIDENCE: 3,
    NO_MARKET_DATA: 4,
}

# Tiers that signal premium review potential
_PREMIUM_TIERS = {"perfect", "near_perfect", "strong"}
_KEEP_TIERS = {"perfect", "near_perfect"}

# Confidence levels considered "low"
_LOW_CONFIDENCE_LEVELS = {"low", None}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RecommendedItem:
    """A ValuationItem wrapped with a sell recommendation."""

    item: ValuationItem
    recommendation: str  # one of ALL_TAGS
    reason: str = ""
    priority_score: float = 0.0
    is_duplicate: bool = False
    duplicate_count: int = 1


# ---------------------------------------------------------------------------
# Core classification
# ---------------------------------------------------------------------------

def classify_recommendation(
    item: ValuationItem,
    premium: PremiumEstimate | None = None,
    *,
    low_confidence_threshold: str | None = None,
) -> tuple[str, str]:
    """Return ``(tag, reason)`` for a single item.

    Parameters
    ----------
    item:
        The valuation item to classify.
    premium:
        Optional premium estimate (from ``compute_premium``).
    low_confidence_threshold:
        Confidence level at or below which items are tagged
        ``low_confidence``.  Defaults to ``"low"``.
    """
    # No price data at all
    if not item.has_price or item.price_fg is None:
        return NO_MARKET_DATA, "No market price available"

    # Low confidence
    lc = low_confidence_threshold or "low"
    if item.price_confidence in _LOW_CONFIDENCE_LEVELS or item.price_confidence == lc:
        if item.sample_count is not None and item.sample_count < 3:
            return LOW_CONFIDENCE, f"Low confidence ({item.price_confidence}; {item.sample_count} samples)"

    # Premium tier analysis
    if premium is not None:
        if premium.roll_tier in _KEEP_TIERS:
            return KEEP, f"Premium roll ({premium.roll_tier}, {premium.roll_percentile:.0f}%)"
        if premium.roll_tier in _PREMIUM_TIERS:
            return CHECK_ROLL, f"Potential premium ({premium.roll_tier}, {premium.roll_percentile:.0f}%); verify roll"

    # Default: liquid sell candidate
    return SELL_NOW, "Liquid item with market data; safe to list"


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def detect_duplicates(
    items: list[ValuationItem],
) -> dict[str, list[ValuationItem]]:
    """Group items by canonical name and return groups with >1 copy."""
    groups: dict[str, list[ValuationItem]] = defaultdict(list)
    for it in items:
        key = (it.canonical_item_id or it.item_name).lower().strip()
        groups[key].append(it)
    return {k: v for k, v in groups.items() if len(v) > 1}


# ---------------------------------------------------------------------------
# Quick-sell estimation
# ---------------------------------------------------------------------------

def estimate_quick_sell_total(items: list[RecommendedItem]) -> float:
    """Sum prices of all ``sell_now`` items."""
    return sum(
        ri.item.price_fg
        for ri in items
        if ri.recommendation == SELL_NOW
        and ri.item.price_fg is not None
    )


# ---------------------------------------------------------------------------
# Prioritisation
# ---------------------------------------------------------------------------

def _priority_score(ri: RecommendedItem) -> float:
    """Compute a numeric priority (lower = listed first)."""
    tag_base = _TAG_PRIORITY.get(ri.recommendation, 99) * 1_000_000
    # Within a tag group, sort by price descending (negate)
    price_part = -(ri.item.price_fg or 0.0)
    return tag_base + price_part


def prioritize_items(
    items: list[RecommendedItem],
) -> list[RecommendedItem]:
    """Sort items: liquid sell_now first, then check_roll, then rest."""
    for ri in items:
        ri.priority_score = _priority_score(ri)
    return sorted(items, key=lambda ri: ri.priority_score)


# ---------------------------------------------------------------------------
# High-level builder
# ---------------------------------------------------------------------------

def build_recommendations(
    items: list[ValuationItem],
    premiums: dict[int, PremiumEstimate] | None = None,
) -> list[RecommendedItem]:
    """Classify, tag duplicates, and prioritise a list of valuation items.

    Parameters
    ----------
    items:
        Flat list of ``ValuationItem`` (e.g. from a stash scan).
    premiums:
        Optional mapping of ``slot_index`` -> ``PremiumEstimate``.
    """
    premiums = premiums or {}
    duplicates = detect_duplicates(items)

    # Build a set of slot indices that belong to duplicate groups
    dup_slots: dict[int, int] = {}
    for group in duplicates.values():
        for it in group:
            dup_slots[it.slot_index] = len(group)

    result: list[RecommendedItem] = []
    for it in items:
        premium = premiums.get(it.slot_index)
        tag, reason = classify_recommendation(it, premium)
        ri = RecommendedItem(
            item=it,
            recommendation=tag,
            reason=reason,
            is_duplicate=it.slot_index in dup_slots,
            duplicate_count=dup_slots.get(it.slot_index, 1),
        )
        result.append(ri)

    return prioritize_items(result)


# ---------------------------------------------------------------------------
# HTML export
# ---------------------------------------------------------------------------

_TAG_COLORS: dict[str, str] = {
    SELL_NOW: "#27ae60",
    CHECK_ROLL: "#f39c12",
    KEEP: "#2980b9",
    LOW_CONFIDENCE: "#95a5a6",
    NO_MARKET_DATA: "#e74c3c",
}

_TAG_LABELS: dict[str, str] = {
    SELL_NOW: "Sell now",
    CHECK_ROLL: "Check roll manually",
    KEEP: "Keep",
    LOW_CONFIDENCE: "Low confidence",
    NO_MARKET_DATA: "No market data",
}


def _items_to_json(items: Sequence[RecommendedItem]) -> str:
    rows = []
    for ri in items:
        rows.append({
            "slot": ri.item.slot_index,
            "name": ri.item.item_name,
            "canonical": ri.item.canonical_item_id or "",
            "price_fg": ri.item.price_fg,
            "price_low": ri.item.price_low_fg,
            "price_high": ri.item.price_high_fg,
            "confidence": ri.item.price_confidence or "",
            "samples": ri.item.sample_count,
            "tag": ri.recommendation,
            "tag_label": _TAG_LABELS.get(ri.recommendation, ri.recommendation),
            "reason": ri.reason,
            "is_duplicate": ri.is_duplicate,
            "dup_count": ri.duplicate_count,
            "priority": ri.priority_score,
        })
    return json.dumps(rows, indent=None, ensure_ascii=False)


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #1a1a2e; color: #e0e0e0; margin: 0; padding: 16px; }}
  h1 {{ color: #f5f5f5; font-size: 1.4rem; }}
  .summary {{ display: flex; gap: 18px; flex-wrap: wrap; margin-bottom: 12px; }}
  .summary .card {{ background: #16213e; border-radius: 6px; padding: 10px 16px; min-width: 120px; }}
  .summary .card .val {{ font-size: 1.3rem; font-weight: 700; }}
  .summary .card .lbl {{ font-size: 0.8rem; color: #aaa; }}
  .filters {{ margin-bottom: 10px; }}
  .filters select, .filters input {{ background: #16213e; color: #e0e0e0; border: 1px solid #333; padding: 4px 8px; border-radius: 4px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th {{ background: #16213e; position: sticky; top: 0; padding: 8px 6px; text-align: left; cursor: pointer; }}
  td {{ padding: 6px; border-bottom: 1px solid #222; }}
  tr:hover {{ background: #16213e55; }}
  .tag {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 0.78rem; font-weight: 600; color: #fff; }}
  .dup {{ color: #f39c12; font-weight: 600; }}
  .ts {{ color: #666; font-size: 0.75rem; margin-top: 8px; }}
</style></head><body>
<h1>{title}</h1>
<div class="summary">
  <div class="card"><div class="val">{summary_total} fg</div><div class="lbl">Quick-sell total</div></div>
  <div class="card"><div class="val">{summary_items}</div><div class="lbl">Items</div></div>
  <div class="card"><div class="val">{summary_sell_now}</div><div class="lbl">Sell now</div></div>
  <div class="card"><div class="val">{summary_check}</div><div class="lbl">Check roll</div></div>
  <div class="card"><div class="val">{summary_keep}</div><div class="lbl">Keep</div></div>
  <div class="card"><div class="val">{summary_low_conf}</div><div class="lbl">Low confidence</div></div>
  <div class="card"><div class="val">{summary_no_data}</div><div class="lbl">No data</div></div>
</div>
<div class="filters">
  Filter: <select id="tagFilter"><option value="">All</option>
  <option value="sell_now">Sell now</option><option value="check_roll">Check roll</option>
  <option value="keep">Keep</option><option value="low_confidence">Low confidence</option>
  <option value="no_market_data">No market data</option></select>
  <label><input type="checkbox" id="dupOnly"> Duplicates only</label>
</div>
<table><thead><tr>
  <th>Item</th><th>Tag</th><th>Price (fg)</th><th>Range</th>
  <th>Confidence</th><th>Samples</th><th>Dup</th><th>Reason</th>
</tr></thead><tbody id="tbody"></tbody></table>
<div class="ts">Generated {timestamp}</div>
<script>
const DATA={payload};
const COLORS={colors};
function render(data){{
  const tb=document.getElementById("tbody");
  tb.innerHTML="";
  data.forEach(r=>{{
    const tr=document.createElement("tr");
    const bg=COLORS[r.tag]||"#555";
    const dup=r.is_duplicate?`<span class="dup">${{r.dup_count}}x</span>`:"";
    const price=r.price_fg!=null?r.price_fg.toLocaleString():"—";
    const lo=r.price_low!=null?r.price_low.toLocaleString():"";
    const hi=r.price_high!=null?r.price_high.toLocaleString():"";
    const range=(lo||hi)?`${{lo}} – ${{hi}}`:"—";
    tr.innerHTML=`<td>${{r.name}}</td><td><span class="tag" style="background:${{bg}}">${{r.tag_label}}</span></td>`+
      `<td>${{price}}</td><td>${{range}}</td><td>${{r.confidence}}</td><td>${{r.samples!=null?r.samples:"—"}}</td>`+
      `<td>${{dup}}</td><td>${{r.reason}}</td>`;
    tb.appendChild(tr);
  }});
}}
function applyFilters(){{
  let d=DATA;
  const tag=document.getElementById("tagFilter").value;
  const dup=document.getElementById("dupOnly").checked;
  if(tag) d=d.filter(r=>r.tag===tag);
  if(dup) d=d.filter(r=>r.is_duplicate);
  render(d);
}}
document.getElementById("tagFilter").addEventListener("change",applyFilters);
document.getElementById("dupOnly").addEventListener("change",applyFilters);
render(DATA);
</script></body></html>"""


def build_sell_recommendations_html(
    items: list[RecommendedItem],
    *,
    title: str = "Sell Recommendations",
) -> str:
    """Render a self-contained HTML page for sell recommendations."""
    quick_sell = estimate_quick_sell_total(items)
    tag_counts: dict[str, int] = defaultdict(int)
    for ri in items:
        tag_counts[ri.recommendation] += 1

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = _items_to_json(items)
    colors_json = json.dumps(_TAG_COLORS, ensure_ascii=False)

    return _HTML_TEMPLATE.format(
        title=html.escape(title),
        timestamp=ts,
        payload=payload,
        colors=colors_json,
        summary_total=f"{quick_sell:,.0f}",
        summary_items=len(items),
        summary_sell_now=tag_counts.get(SELL_NOW, 0),
        summary_check=tag_counts.get(CHECK_ROLL, 0),
        summary_keep=tag_counts.get(KEEP, 0),
        summary_low_conf=tag_counts.get(LOW_CONFIDENCE, 0),
        summary_no_data=tag_counts.get(NO_MARKET_DATA, 0),
    )
