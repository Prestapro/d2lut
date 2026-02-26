"""KPI + regression dashboard for market coverage and OCR quality.

Persists KPI snapshots, compares baselines, checks regression thresholds,
and builds a self-contained HTML dashboard page (dark theme).

Requirements: 3.4, 11.4, 12.1, 12.4, 12.5
"""

from __future__ import annotations

import html
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

_KPI_TABLE_DDL = """\
CREATE TABLE IF NOT EXISTS kpi_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    observed_prices INTEGER,
    variants INTEGER,
    canonical_items INTEGER,
    high_value_observations INTEGER,
    high_value_variants INTEGER,
    resolved_by_image_obs INTEGER,
    resolved_by_image_variants INTEGER,
    ocr_precision REAL,
    ocr_comparable_rows INTEGER,
    ocr_exact_match INTEGER,
    ocr_mismatch_count INTEGER
);
"""

_FIELDS = [
    "observed_prices",
    "variants",
    "canonical_items",
    "high_value_observations",
    "high_value_variants",
    "resolved_by_image_obs",
    "resolved_by_image_variants",
    "ocr_precision",
    "ocr_comparable_rows",
    "ocr_exact_match",
    "ocr_mismatch_count",
]


@dataclass
class KPISnapshot:
    """A point-in-time snapshot of market coverage and OCR quality KPIs."""

    timestamp: str
    observed_prices: int = 0
    variants: int = 0
    canonical_items: int = 0
    high_value_observations: int = 0
    high_value_variants: int = 0
    resolved_by_image_obs: int = 0
    resolved_by_image_variants: int = 0
    ocr_precision: float = 0.0
    ocr_comparable_rows: int = 0
    ocr_exact_match: int = 0
    ocr_mismatch_count: int = 0


# ---------------------------------------------------------------------------
# Default regression thresholds
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLDS: dict[str, dict[str, Any]] = {
    "observed_prices": {"max_drop_pct": 0.10, "label": "Observed prices"},
    "variants": {"max_drop_pct": 0.05, "label": "Variants"},
    "high_value_observations": {"max_drop_pct": 0.15, "label": "High-value observations"},
    "ocr_precision": {"max_drop_abs": 0.05, "label": "OCR precision"},
}


# ---------------------------------------------------------------------------
# Ensure table
# ---------------------------------------------------------------------------

def ensure_kpi_table(conn: sqlite3.Connection) -> None:
    """Create the ``kpi_snapshots`` table if it does not exist."""
    conn.executescript(_KPI_TABLE_DDL)


# ---------------------------------------------------------------------------
# Collect KPIs from DB
# ---------------------------------------------------------------------------

def collect_kpi_snapshot(
    conn: sqlite3.Connection,
    market_key: str,
    *,
    min_fg: float = 300.0,
    timestamp: str | None = None,
) -> KPISnapshot:
    """Query the DB for current KPI values.

    Reuses logic from ``report_market_coverage.py`` and
    ``report_modifier_quality_by_class.py`` without importing them
    (they are CLI scripts, not library modules).
    """
    ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Market coverage KPIs ---
    row = conn.execute(
        """
        SELECT COUNT(*) AS obs,
               COUNT(DISTINCT variant_key) AS variants,
               COUNT(DISTINCT COALESCE(NULLIF(canonical_item_id,''), variant_key)) AS canonical_items
        FROM observed_prices
        WHERE market_key = ?
        """,
        (market_key,),
    ).fetchone()
    observed_prices = int(row[0] or 0)
    variants = int(row[1] or 0)
    canonical_items = int(row[2] or 0)

    # High-value (>=min_fg) coverage
    hv = conn.execute(
        """
        SELECT COUNT(*) AS obs,
               COUNT(DISTINCT variant_key) AS variants
        FROM observed_prices
        WHERE market_key = ? AND price_fg >= ?
        """,
        (market_key, min_fg),
    ).fetchone()
    high_value_observations = int(hv[0] or 0)
    high_value_variants = int(hv[1] or 0)

    # Resolved-by-image
    img = conn.execute(
        """
        SELECT COUNT(*) AS obs,
               COUNT(DISTINCT variant_key) AS variants
        FROM observed_prices
        WHERE market_key = ?
          AND source LIKE 'image_ocr_candidate:%%'
        """,
        (market_key,),
    ).fetchone()
    resolved_by_image_obs = int(img[0] or 0)
    resolved_by_image_variants = int(img[1] or 0)

    # --- OCR quality KPIs (from image_market_queue) ---
    ocr_precision = 0.0
    ocr_comparable_rows = 0
    ocr_exact_match = 0
    ocr_mismatch_count = 0
    try:
        ocr_rows = conn.execute(
            """
            SELECT observed_variant_hint, ocr_variant_hint
            FROM image_market_queue
            WHERE market_key = ? AND status = 'ocr_parsed'
            """,
            (market_key,),
        ).fetchall()
        for r in ocr_rows:
            truth = (r[0] or "").strip().lower()
            pred = (r[1] or "").strip().lower()
            if not truth or not pred:
                continue
            ocr_comparable_rows += 1
            if pred == truth:
                ocr_exact_match += 1
            else:
                ocr_mismatch_count += 1
        if ocr_comparable_rows > 0:
            ocr_precision = ocr_exact_match / ocr_comparable_rows
    except sqlite3.OperationalError:
        pass  # table may not exist

    return KPISnapshot(
        timestamp=ts,
        observed_prices=observed_prices,
        variants=variants,
        canonical_items=canonical_items,
        high_value_observations=high_value_observations,
        high_value_variants=high_value_variants,
        resolved_by_image_obs=resolved_by_image_obs,
        resolved_by_image_variants=resolved_by_image_variants,
        ocr_precision=round(ocr_precision, 4),
        ocr_comparable_rows=ocr_comparable_rows,
        ocr_exact_match=ocr_exact_match,
        ocr_mismatch_count=ocr_mismatch_count,
    )


# ---------------------------------------------------------------------------
# Persist / load snapshots
# ---------------------------------------------------------------------------

def persist_kpi_snapshot(conn: sqlite3.Connection, snapshot: KPISnapshot) -> int:
    """Insert a KPI snapshot and return its row id."""
    ensure_kpi_table(conn)
    cur = conn.execute(
        """
        INSERT INTO kpi_snapshots
            (timestamp, observed_prices, variants, canonical_items,
             high_value_observations, high_value_variants,
             resolved_by_image_obs, resolved_by_image_variants,
             ocr_precision, ocr_comparable_rows, ocr_exact_match, ocr_mismatch_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot.timestamp,
            snapshot.observed_prices,
            snapshot.variants,
            snapshot.canonical_items,
            snapshot.high_value_observations,
            snapshot.high_value_variants,
            snapshot.resolved_by_image_obs,
            snapshot.resolved_by_image_variants,
            snapshot.ocr_precision,
            snapshot.ocr_comparable_rows,
            snapshot.ocr_exact_match,
            snapshot.ocr_mismatch_count,
        ),
    )
    conn.commit()
    return cur.lastrowid or 0


def load_kpi_history(conn: sqlite3.Connection, limit: int = 50) -> list[KPISnapshot]:
    """Load recent KPI snapshots ordered newest-first."""
    ensure_kpi_table(conn)
    rows = conn.execute(
        """
        SELECT timestamp, observed_prices, variants, canonical_items,
               high_value_observations, high_value_variants,
               resolved_by_image_obs, resolved_by_image_variants,
               ocr_precision, ocr_comparable_rows, ocr_exact_match, ocr_mismatch_count
        FROM kpi_snapshots
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        KPISnapshot(
            timestamp=str(r[0]),
            observed_prices=int(r[1] or 0),
            variants=int(r[2] or 0),
            canonical_items=int(r[3] or 0),
            high_value_observations=int(r[4] or 0),
            high_value_variants=int(r[5] or 0),
            resolved_by_image_obs=int(r[6] or 0),
            resolved_by_image_variants=int(r[7] or 0),
            ocr_precision=float(r[8] or 0.0),
            ocr_comparable_rows=int(r[9] or 0),
            ocr_exact_match=int(r[10] or 0),
            ocr_mismatch_count=int(r[11] or 0),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Compare snapshots
# ---------------------------------------------------------------------------

def compare_snapshots(
    current: KPISnapshot,
    baseline: KPISnapshot,
) -> dict[str, dict[str, Any]]:
    """Compute deltas and percentage changes for each metric."""
    result: dict[str, dict[str, Any]] = {}
    for f in _FIELDS:
        cur_val = getattr(current, f)
        base_val = getattr(baseline, f)
        delta = cur_val - base_val
        if base_val != 0:
            pct_change = delta / abs(base_val)
        else:
            pct_change = 0.0 if delta == 0 else float("inf")
        result[f] = {
            "current": cur_val,
            "baseline": base_val,
            "delta": delta,
            "pct_change": round(pct_change, 4),
        }
    return result


# ---------------------------------------------------------------------------
# Regression threshold checking
# ---------------------------------------------------------------------------

def check_regression_thresholds(
    current: KPISnapshot,
    baseline: KPISnapshot,
    thresholds: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Return alert messages when metrics regress beyond thresholds."""
    th = thresholds or DEFAULT_THRESHOLDS
    alerts: list[str] = []
    for metric, cfg in th.items():
        cur_val = getattr(current, metric, None)
        base_val = getattr(baseline, metric, None)
        if cur_val is None or base_val is None:
            continue
        label = cfg.get("label", metric)

        # Percentage-based drop check
        if "max_drop_pct" in cfg and base_val != 0:
            drop_pct = (base_val - cur_val) / abs(base_val)
            if drop_pct > cfg["max_drop_pct"]:
                alerts.append(
                    f"REGRESSION: {label} dropped {drop_pct:.1%} "
                    f"({base_val} -> {cur_val}, threshold {cfg['max_drop_pct']:.0%})"
                )

        # Absolute drop check (for precision-like metrics)
        if "max_drop_abs" in cfg:
            drop_abs = base_val - cur_val
            if drop_abs > cfg["max_drop_abs"]:
                alerts.append(
                    f"REGRESSION: {label} dropped {drop_abs:.4f} "
                    f"({base_val:.4f} -> {cur_val:.4f}, threshold {cfg['max_drop_abs']:.4f})"
                )
    return alerts


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _snapshot_to_dict(s: KPISnapshot) -> dict[str, Any]:
    return asdict(s)


def _format_delta(delta: float | int, pct: float, is_precision: bool = False) -> str:
    """Format a delta value with color hint for HTML."""
    if delta == 0:
        return '<span style="color:#888">—</span>'
    color = "#4caf50" if delta > 0 else "#f44336"
    sign = "+" if delta > 0 else ""
    if is_precision:
        return f'<span style="color:{color}">{sign}{delta:.4f} ({sign}{pct:.1%})</span>'
    return f'<span style="color:{color}">{sign}{delta} ({sign}{pct:.1%})</span>'


def build_kpi_dashboard_html(
    history: list[KPISnapshot],
    alerts: list[str] | None = None,
) -> str:
    """Build a self-contained HTML KPI dashboard page.

    Parameters
    ----------
    history:
        KPI snapshots ordered newest-first.
    alerts:
        Optional regression alert messages.
    """
    alerts = alerts or []
    latest = history[0] if history else None
    previous = history[1] if len(history) >= 2 else None
    comparison = compare_snapshots(latest, previous) if latest and previous else {}

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Build summary cards HTML
    cards_html = ""
    if latest:
        card_defs = [
            ("Observed Prices", latest.observed_prices, "observed_prices", False),
            ("Variants", latest.variants, "variants", False),
            ("Canonical Items", latest.canonical_items, "canonical_items", False),
            ("High-Value Obs (≥300fg)", latest.high_value_observations, "high_value_observations", False),
            ("High-Value Variants", latest.high_value_variants, "high_value_variants", False),
            ("Resolved by Image (obs)", latest.resolved_by_image_obs, "resolved_by_image_obs", False),
            ("Resolved by Image (var)", latest.resolved_by_image_variants, "resolved_by_image_variants", False),
            ("OCR Precision", latest.ocr_precision, "ocr_precision", True),
            ("OCR Comparable Rows", latest.ocr_comparable_rows, "ocr_comparable_rows", False),
            ("OCR Exact Match", latest.ocr_exact_match, "ocr_exact_match", False),
            ("OCR Mismatches", latest.ocr_mismatch_count, "ocr_mismatch_count", False),
        ]
        for label, value, key, is_prec in card_defs:
            delta_html = ""
            if key in comparison:
                c = comparison[key]
                delta_html = _format_delta(c["delta"], c["pct_change"], is_precision=is_prec)
            val_str = f"{value:.4f}" if is_prec else str(value)
            cards_html += (
                f'<div class="card"><div class="card-label">{html.escape(label)}</div>'
                f'<div class="card-value">{val_str}</div>'
                f'<div class="card-delta">{delta_html}</div></div>\n'
            )

    # Alert banner
    alert_html = ""
    if alerts:
        items = "".join(f"<li>{html.escape(a)}</li>" for a in alerts)
        alert_html = f'<div class="alert-banner"><strong>⚠ Regression Alerts</strong><ul>{items}</ul></div>'

    # History table rows
    history_rows = ""
    for s in history:
        history_rows += (
            f"<tr><td>{html.escape(s.timestamp)}</td>"
            f"<td>{s.observed_prices}</td><td>{s.variants}</td>"
            f"<td>{s.canonical_items}</td>"
            f"<td>{s.high_value_observations}</td><td>{s.high_value_variants}</td>"
            f"<td>{s.resolved_by_image_obs}</td><td>{s.resolved_by_image_variants}</td>"
            f"<td>{s.ocr_precision:.4f}</td><td>{s.ocr_comparable_rows}</td>"
            f"<td>{s.ocr_exact_match}</td><td>{s.ocr_mismatch_count}</td></tr>\n"
        )

    history_json = json.dumps([_snapshot_to_dict(s) for s in history], indent=None)

    return _KPI_TEMPLATE.format(
        timestamp=html.escape(ts),
        alert_html=alert_html,
        cards_html=cards_html,
        history_rows=history_rows,
        history_json=history_json,
    )


_KPI_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>KPI Dashboard — Market Coverage &amp; OCR Quality</title>
<style>
:root {{
  --bg: #1e1e2e; --surface: #2a2a3d; --text: #cdd6f4;
  --accent: #89b4fa; --green: #4caf50; --red: #f44336;
  --border: #45475a; --muted: #6c7086;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); padding: 1.5rem; }}
h1 {{ color: var(--accent); margin-bottom: 0.25rem; font-size: 1.4rem; }}
.subtitle {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 1rem; }}
.alert-banner {{
  background: #3d1f1f; border: 1px solid var(--red); border-radius: 6px;
  padding: 0.75rem 1rem; margin-bottom: 1rem; color: #fca5a5;
}}
.alert-banner ul {{ margin: 0.5rem 0 0 1.2rem; }}
.alert-banner li {{ margin-bottom: 0.25rem; }}
.cards {{
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem; margin-bottom: 1.5rem;
}}
.card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
  padding: 0.75rem; text-align: center;
}}
.card-label {{ font-size: 0.75rem; color: var(--muted); margin-bottom: 0.25rem; }}
.card-value {{ font-size: 1.5rem; font-weight: 700; color: var(--accent); }}
.card-delta {{ font-size: 0.8rem; margin-top: 0.25rem; }}
table {{
  width: 100%; border-collapse: collapse; background: var(--surface);
  border: 1px solid var(--border); border-radius: 6px; overflow: hidden;
  font-size: 0.85rem;
}}
th, td {{ padding: 0.5rem 0.6rem; text-align: right; border-bottom: 1px solid var(--border); }}
th {{ background: #313244; color: var(--accent); font-weight: 600; position: sticky; top: 0; }}
td:first-child, th:first-child {{ text-align: left; }}
tr:hover {{ background: #313244; }}
</style>
</head>
<body>
<h1>KPI Dashboard — Market Coverage &amp; OCR Quality</h1>
<div class="subtitle">Generated {timestamp}</div>
{alert_html}
<div class="cards">{cards_html}</div>
<h2 style="color:var(--accent);font-size:1.1rem;margin-bottom:0.5rem;">Snapshot History</h2>
<table>
<thead><tr>
  <th>Timestamp</th><th>Obs Prices</th><th>Variants</th><th>Canon Items</th>
  <th>HV Obs</th><th>HV Var</th><th>Img Obs</th><th>Img Var</th>
  <th>OCR Prec</th><th>OCR Comp</th><th>OCR Exact</th><th>OCR Mismatch</th>
</tr></thead>
<tbody>{history_rows}</tbody>
</table>
<script>
// Embedded history data for potential JS extensions
var KPI_HISTORY = {history_json};
</script>
</body>
</html>
"""
