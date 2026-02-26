"""Tests for overlay label UX: compact labels, refresh status, fallbacks.

Validates: Requirements 3.1, 4.1, 4.2, 4.4, 4.6, 6.5
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from d2lut.overlay.label_ux import (
    CompactLabel,
    RefreshStatus,
    derive_refresh_status,
    format_compact_label,
    is_data_stale,
)


# ---------------------------------------------------------------------------
# RefreshStatus enum
# ---------------------------------------------------------------------------


class TestRefreshStatus:
    def test_values(self):
        assert RefreshStatus.LIVE.value == "LIVE"
        assert RefreshStatus.STALE.value == "STALE"
        assert RefreshStatus.REFRESHING.value == "REFRESHING"
        assert RefreshStatus.ERROR.value == "ERROR"

    def test_all_members(self):
        assert set(RefreshStatus) == {
            RefreshStatus.LIVE,
            RefreshStatus.STALE,
            RefreshStatus.REFRESHING,
            RefreshStatus.ERROR,
        }


# ---------------------------------------------------------------------------
# is_data_stale
# ---------------------------------------------------------------------------


class TestIsDataStale:
    def test_none_is_stale(self):
        assert is_data_stale(None) is True

    def test_recent_is_not_stale(self):
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        assert is_data_stale(recent, stale_threshold_hours=24.0) is False

    def test_old_is_stale(self):
        old = datetime.now(timezone.utc) - timedelta(hours=25)
        assert is_data_stale(old, stale_threshold_hours=24.0) is True

    def test_custom_threshold(self):
        ts = datetime.now(timezone.utc) - timedelta(hours=2)
        assert is_data_stale(ts, stale_threshold_hours=1.0) is True
        assert is_data_stale(ts, stale_threshold_hours=3.0) is False

    def test_naive_datetime_treated_as_utc(self):
        naive_recent = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        assert is_data_stale(naive_recent, stale_threshold_hours=24.0) is False


# ---------------------------------------------------------------------------
# derive_refresh_status
# ---------------------------------------------------------------------------


class TestDeriveRefreshStatus:
    def test_error_takes_priority(self):
        recent = datetime.now(timezone.utc)
        status = derive_refresh_status(
            last_refresh=recent,
            is_refreshing=True,
            last_error="connection failed",
        )
        assert status == RefreshStatus.ERROR

    def test_refreshing_over_stale(self):
        status = derive_refresh_status(
            last_refresh=None,
            is_refreshing=True,
        )
        assert status == RefreshStatus.REFRESHING

    def test_stale_when_no_refresh(self):
        status = derive_refresh_status(last_refresh=None)
        assert status == RefreshStatus.STALE

    def test_stale_when_old(self):
        old = datetime.now(timezone.utc) - timedelta(hours=25)
        status = derive_refresh_status(last_refresh=old)
        assert status == RefreshStatus.STALE

    def test_live_when_recent(self):
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        status = derive_refresh_status(last_refresh=recent)
        assert status == RefreshStatus.LIVE

    def test_custom_stale_threshold(self):
        ts = datetime.now(timezone.utc) - timedelta(hours=2)
        assert derive_refresh_status(ts, stale_threshold_hours=1.0) == RefreshStatus.STALE
        assert derive_refresh_status(ts, stale_threshold_hours=3.0) == RefreshStatus.LIVE


# ---------------------------------------------------------------------------
# format_compact_label — normal price labels
# ---------------------------------------------------------------------------


class TestFormatCompactLabelNormal:
    def test_basic_price_with_confidence(self):
        label = format_compact_label("Shako", 350.0, "high")
        assert label.text == "Shako - ~350fg (high)"
        assert label.color_bucket == "low"
        assert label.is_fallback is False

    def test_medium_confidence_tag(self):
        label = format_compact_label("Enigma", 5000.0, "medium")
        assert "(med)" in label.text
        assert label.color_bucket == "medium"

    def test_low_confidence_tag(self):
        label = format_compact_label("Rare Ring", 200.0, "low")
        assert "(low)" in label.text

    def test_unknown_confidence(self):
        label = format_compact_label("Amulet", 100.0, "unknown_value")
        assert "(?)" in label.text

    def test_none_confidence(self):
        label = format_compact_label("Amulet", 100.0, None)
        assert "(?)" in label.text

    def test_no_approx_prefix(self):
        label = format_compact_label("Shako", 350.0, "high", approx_prefix=False)
        assert label.text == "Shako - 350fg (high)"

    def test_stale_indicator(self):
        label = format_compact_label("Shako", 350.0, "high", stale=True)
        assert label.text == "Shako - ~350fg (high) [stale]"
        assert label.is_fallback is False

    def test_high_value_color(self):
        label = format_compact_label("Ber Rune", 15000.0, "high")
        assert label.color_bucket == "high"

    def test_price_rounding(self):
        label = format_compact_label("Item", 349.7, "high")
        assert "~350fg" in label.text


# ---------------------------------------------------------------------------
# format_compact_label — fallback labels
# ---------------------------------------------------------------------------


class TestFormatCompactLabelFallbacks:
    def test_no_data_default(self):
        label = format_compact_label("Shako", None)
        assert label.text == "Shako - no data"
        assert label.color_bucket == "no_data"
        assert label.is_fallback is True

    def test_no_data_custom_text(self):
        label = format_compact_label("Shako", None, no_data_text="N/A")
        assert label.text == "Shako - N/A"

    def test_error_text(self):
        label = format_compact_label("Shako", None, error_text="parse error")
        assert label.text == "Shako - parse error"
        assert label.color_bucket == "error"
        assert label.is_fallback is True

    def test_error_overrides_price(self):
        """error_text takes priority even if median_price is provided."""
        label = format_compact_label("Shako", 350.0, "high", error_text="OCR failed")
        assert label.text == "Shako - OCR failed"
        assert label.is_fallback is True

    def test_no_item_name_fallback(self):
        label = format_compact_label(None, None)
        assert label.text == "??? - no data"

    def test_no_item_name_with_error(self):
        label = format_compact_label(None, None, error_text="parse error")
        assert label.text == "??? - parse error"

    def test_no_item_name_with_price(self):
        label = format_compact_label(None, 100.0, "low")
        assert label.text.startswith("??? - ")
        assert label.is_fallback is False


# ---------------------------------------------------------------------------
# Label stability (no jitter)
# ---------------------------------------------------------------------------


class TestLabelStability:
    """Verify that repeated calls with the same input produce identical output."""

    def test_same_input_same_output(self):
        a = format_compact_label("Shako", 350.0, "high")
        b = format_compact_label("Shako", 350.0, "high")
        assert a.text == b.text
        assert a.color_bucket == b.color_bucket

    def test_fallback_stable(self):
        a = format_compact_label("Shako", None)
        b = format_compact_label("Shako", None)
        assert a.text == b.text

    def test_error_stable(self):
        a = format_compact_label("X", None, error_text="err")
        b = format_compact_label("X", None, error_text="err")
        assert a.text == b.text
