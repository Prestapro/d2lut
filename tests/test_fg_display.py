"""Tests for FGDisplay class — market comparison, rendering, formatting, subscriptions."""

from __future__ import annotations

from datetime import datetime

import pytest

from d2lut.models import PriceEstimate
from d2lut.overlay.fg_display import (
    FGDisplay,
    FGDisplayRender,
    MarketComparison,
    _median,
)
from d2lut.overlay.price_lookup import FGListing


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _listing(
    price: float,
    kind: str = "bin",
    recent: bool = True,
) -> FGListing:
    return FGListing(
        price_fg=price,
        listing_type=kind,
        thread_id=1,
        post_id=1,
        posted_at=datetime(2025, 1, 1),
        is_recent=recent,
        thread_title="test",
        source_url=None,
    )


def _estimate(
    fg: float = 100.0,
    low: float = 80.0,
    high: float = 120.0,
    confidence: str = "medium",
    samples: int = 5,
) -> PriceEstimate:
    return PriceEstimate(
        variant_key="unique:shako",
        estimate_fg=fg,
        range_low_fg=low,
        range_high_fg=high,
        confidence=confidence,
        sample_count=samples,
        last_updated=datetime(2025, 1, 15, 12, 0),
    )


# ---------------------------------------------------------------------------
# Stub price engine for show_listings tests
# ---------------------------------------------------------------------------

class StubPriceEngine:
    """Minimal duck-typed stand-in for PriceLookupEngine."""

    def __init__(
        self,
        price: PriceEstimate | None = None,
        listings: list[FGListing] | None = None,
    ):
        self._price = price
        self._listings = listings or []

    def get_price(self, item_id: str, variant: str | None = None):
        return self._price

    def get_fg_listings(self, item_id: str, variant: str | None = None):
        return self._listings


# ---------------------------------------------------------------------------
# _median utility
# ---------------------------------------------------------------------------

class TestMedian:
    def test_empty(self):
        assert _median([]) == 0.0

    def test_single(self):
        assert _median([42.0]) == 42.0

    def test_odd(self):
        assert _median([1.0, 3.0, 5.0]) == 3.0

    def test_even(self):
        assert _median([1.0, 2.0, 3.0, 4.0]) == 2.5


# ---------------------------------------------------------------------------
# MarketComparison calculation
# ---------------------------------------------------------------------------

class TestCalculateMarketComparison:
    def setup_method(self):
        self.display = FGDisplay()

    def test_under_valued(self):
        """Estimate well below BIN/sold median -> under_valued."""
        listings = [_listing(200), _listing(220, "sold")]
        mc = self.display.calculate_market_comparison(100.0, listings)
        assert mc.status == "under_valued"
        assert mc.deviation_pct < 0
        assert mc.reference_price_fg == 210.0

    def test_over_valued(self):
        """Estimate well above BIN/sold median -> over_valued."""
        listings = [_listing(100, "bin"), _listing(100, "sold")]
        mc = self.display.calculate_market_comparison(200.0, listings)
        assert mc.status == "over_valued"
        assert mc.deviation_pct > 0

    def test_fair(self):
        """Estimate close to BIN/sold median -> fair."""
        listings = [_listing(100, "bin"), _listing(110, "sold")]
        mc = self.display.calculate_market_comparison(105.0, listings)
        assert mc.status == "fair"

    def test_no_listings(self):
        """No listings at all -> fair with note."""
        mc = self.display.calculate_market_comparison(100.0, [])
        assert mc.status == "fair"
        assert mc.reference_price_fg is None
        assert "No recent listings" in mc.comparison_note

    def test_fallback_to_all_listings(self):
        """No BIN/sold -> falls back to ask/co listings."""
        listings = [_listing(90, "ask"), _listing(110, "co")]
        mc = self.display.calculate_market_comparison(100.0, listings)
        assert mc.status == "fair"
        assert "all listings" in mc.comparison_note

    def test_zero_reference(self):
        """Reference price of zero -> fair, no division error."""
        listings = [_listing(0.0, "bin")]
        mc = self.display.calculate_market_comparison(50.0, listings)
        assert mc.status == "fair"
        assert mc.reference_price_fg == 0.0


# ---------------------------------------------------------------------------
# FGDisplayRender construction via show_listings
# ---------------------------------------------------------------------------

class TestShowListings:
    def setup_method(self):
        self.display = FGDisplay()

    def test_with_estimate_and_listings(self):
        engine = StubPriceEngine(
            price=_estimate(fg=120),
            listings=[_listing(110), _listing(130, "sold")],
        )
        render = self.display.show_listings("unique:shako", None, engine)

        assert render.item_name == "unique:shako"
        assert render.estimate_fg == 120.0
        assert render.sample_count == 5
        assert len(render.recent_listings) == 2
        assert render.market_comparison is not None
        assert render.last_updated is not None

    def test_no_estimate(self):
        engine = StubPriceEngine(price=None, listings=[_listing(100)])
        render = self.display.show_listings("unknown:item", None, engine)

        assert render.estimate_fg is None
        assert render.market_comparison is None
        assert render.sample_count == 0

    def test_no_listings(self):
        engine = StubPriceEngine(price=_estimate(), listings=[])
        render = self.display.show_listings("unique:shako", None, engine)

        assert render.recent_listings == []
        assert render.market_comparison is not None
        assert render.market_comparison.reference_price_fg is None

    def test_variant_used_as_name(self):
        engine = StubPriceEngine(price=_estimate(), listings=[])
        render = self.display.show_listings("unique:shako", "unique:shako:eth", engine)
        assert render.item_name == "unique:shako:eth"

    def test_only_non_recent_listings_filtered(self):
        """show_listings filters to recent-only listings."""
        engine = StubPriceEngine(
            price=_estimate(),
            listings=[
                _listing(100, recent=True),
                _listing(200, recent=False),
            ],
        )
        render = self.display.show_listings("x", None, engine)
        assert len(render.recent_listings) == 1
        assert render.recent_listings[0].price_fg == 100.0


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

class TestFormatCompact:
    def setup_method(self):
        self.display = FGDisplay()

    def test_with_data(self):
        render = FGDisplayRender(
            item_name="Shako",
            estimate_fg=120.0,
            range_low_fg=100.0,
            range_high_fg=140.0,
            confidence="high",
            sample_count=10,
            recent_listings=[],
            market_comparison=MarketComparison(
                status="fair", deviation_pct=2.0,
                reference_price_fg=118.0, comparison_note="ok",
            ),
            last_updated=datetime(2025, 1, 1),
        )
        text = self.display.format_compact(render)
        assert "Shako" in text
        assert "120fg" in text
        assert "fair" in text

    def test_no_data(self):
        render = FGDisplayRender(
            item_name="Mystery",
            estimate_fg=None,
            range_low_fg=None,
            range_high_fg=None,
            confidence=None,
            sample_count=0,
            recent_listings=[],
            market_comparison=None,
            last_updated=None,
        )
        assert "no data" in self.display.format_compact(render)


class TestFormatDetailed:
    def setup_method(self):
        self.display = FGDisplay()

    def test_full_render(self):
        render = FGDisplayRender(
            item_name="Shako",
            estimate_fg=120.0,
            range_low_fg=100.0,
            range_high_fg=140.0,
            confidence="high",
            sample_count=10,
            recent_listings=[_listing(115), _listing(125, "sold")],
            market_comparison=MarketComparison(
                status="under valued",
                deviation_pct=-5.0,
                reference_price_fg=126.0,
                comparison_note="Based on 2 BIN/sold listing(s)",
            ),
            last_updated=datetime(2025, 1, 15, 12, 0),
        )
        text = self.display.format_detailed(render)
        assert "Shako" in text
        assert "120fg" in text
        assert "100-140fg" in text
        assert "Confidence: high" in text
        assert "Samples: 10" in text
        assert "BIN 115fg" in text
        assert "SOLD 125fg" in text
        assert "2025-01-15" in text

    def test_no_data_render(self):
        render = FGDisplayRender(
            item_name="Unknown",
            estimate_fg=None,
            range_low_fg=None,
            range_high_fg=None,
            confidence=None,
            sample_count=0,
            recent_listings=[],
            market_comparison=None,
            last_updated=None,
        )
        text = self.display.format_detailed(render)
        assert "No price data" in text
        assert "No recent listings" in text


# ---------------------------------------------------------------------------
# Update subscription
# ---------------------------------------------------------------------------

class TestUpdateSubscription:
    def test_subscribe_and_notify(self):
        display = FGDisplay()
        calls: list[str] = []
        display.subscribe_to_updates(lambda: calls.append("a"))
        display.subscribe_to_updates(lambda: calls.append("b"))

        display.notify_update()
        assert calls == ["a", "b"]

    def test_no_subscribers(self):
        """notify_update with no subscribers should not raise."""
        FGDisplay().notify_update()
