"""Compact inline label formatting for the in-game overlay.

Provides stable, jitter-free label rendering for D2R tooltip-adjacent
price display.  Handles confidence indicators, stale-data markers,
and runtime-safe fallbacks (no data, low confidence, parser error).

Requirements: 3.1, 4.1, 4.2, 4.4, 4.6, 6.5
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Refresh status enum
# ---------------------------------------------------------------------------

class RefreshStatus(enum.Enum):
    """Market data refresh status shown in the overlay runner."""

    LIVE = "LIVE"
    STALE = "STALE"
    REFRESHING = "REFRESHING"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Label data carrier
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CompactLabel:
    """Rendered compact label ready for display.

    All fields are pre-formatted strings so the UI layer never needs
    to do price arithmetic or confidence mapping.
    """

    text: str          # e.g. "Shako - ~350fg (high)"  or  "Shako - no data"
    color_bucket: str  # "low" | "medium" | "high" | "no_data" | "error"
    is_fallback: bool  # True when label is a fallback (no data / error)



# ---------------------------------------------------------------------------
# Stale-data detection
# ---------------------------------------------------------------------------

def is_data_stale(
    last_refresh: datetime | None,
    stale_threshold_hours: float = 24.0,
) -> bool:
    """Return True when market data is older than *stale_threshold_hours*.

    If *last_refresh* is ``None`` (never refreshed), data is considered stale.
    """
    if last_refresh is None:
        return True
    now = datetime.now(timezone.utc)
    # Ensure tz-aware comparison
    if last_refresh.tzinfo is None:
        last_refresh = last_refresh.replace(tzinfo=timezone.utc)
    age_hours = (now - last_refresh).total_seconds() / 3600.0
    return age_hours > stale_threshold_hours


# ---------------------------------------------------------------------------
# Confidence tag helper
# ---------------------------------------------------------------------------

_CONFIDENCE_TAGS = {"high": "high", "medium": "med", "low": "low"}


def _confidence_tag(confidence: str | None) -> str:
    """Map a confidence string to a short display tag."""
    if confidence is None:
        return "?"
    return _CONFIDENCE_TAGS.get(confidence.lower(), "?")


# ---------------------------------------------------------------------------
# Core label formatter
# ---------------------------------------------------------------------------

def format_compact_label(
    item_name: str | None,
    median_price: float | None,
    confidence: str | None = None,
    *,
    stale: bool = False,
    approx_prefix: bool = True,
    no_data_text: str = "no data",
    error_text: str | None = None,
) -> CompactLabel:
    """Build a compact inline label string for the overlay.

    Produces stable-width output to avoid UI jitter when the label
    updates each frame.

    Examples::

        format_compact_label("Shako", 350.0, "high")
        # CompactLabel(text="Shako - ~350fg (high)", ...)

        format_compact_label("Shako", 350.0, "high", stale=True)
        # CompactLabel(text="Shako - ~350fg (high) [stale]", ...)

        format_compact_label("Shako", None)
        # CompactLabel(text="Shako - no data", ..., is_fallback=True)

        format_compact_label(None, None, error_text="parse error")
        # CompactLabel(text="??? - parse error", ..., is_fallback=True)
    """
    name = item_name or "???"

    # --- error path (parser failure, OCR error, etc.) ---
    if error_text is not None:
        return CompactLabel(
            text=f"{name} - {error_text}",
            color_bucket="error",
            is_fallback=True,
        )

    # --- no price data ---
    if median_price is None:
        return CompactLabel(
            text=f"{name} - {no_data_text}",
            color_bucket="no_data",
            is_fallback=True,
        )

    # --- normal price label ---
    prefix = "~" if approx_prefix else ""
    price_str = f"{prefix}{median_price:.0f}fg"

    tag = _confidence_tag(confidence)
    parts = [f"{name} - {price_str} ({tag})"]

    if stale:
        parts.append("[stale]")

    return CompactLabel(
        text=" ".join(parts),
        color_bucket=_color_bucket_for_price(median_price),
        is_fallback=False,
    )


# ---------------------------------------------------------------------------
# Color bucket (mirrors InventoryOverlay thresholds but standalone)
# ---------------------------------------------------------------------------

_DEFAULT_LOW = 1000.0
_DEFAULT_MEDIUM = 10000.0


def _color_bucket_for_price(
    price: float,
    low_threshold: float = _DEFAULT_LOW,
    medium_threshold: float = _DEFAULT_MEDIUM,
) -> str:
    if price < low_threshold:
        return "low"
    elif price < medium_threshold:
        return "medium"
    return "high"


# ---------------------------------------------------------------------------
# Refresh status derivation
# ---------------------------------------------------------------------------

def derive_refresh_status(
    last_refresh: datetime | None,
    is_refreshing: bool = False,
    last_error: str | None = None,
    stale_threshold_hours: float = 24.0,
) -> RefreshStatus:
    """Derive the current :class:`RefreshStatus` from runtime state.

    Priority: ERROR > REFRESHING > STALE > LIVE.
    """
    if last_error is not None:
        return RefreshStatus.ERROR
    if is_refreshing:
        return RefreshStatus.REFRESHING
    if is_data_stale(last_refresh, stale_threshold_hours):
        return RefreshStatus.STALE
    return RefreshStatus.LIVE
