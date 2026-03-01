"""FG display with market comparison for overlay system.

Shows recent market listings and compares item estimates to observed
BIN/sold prices to indicate under/over/fair valuation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from d2lut.models import PriceEstimate
from d2lut.overlay.price_lookup import FGListing


@dataclass
class MarketComparison:
    """Comparison of an item's estimate against recent market activity."""
    status: str  # under_valued, fair, over_valued
    deviation_pct: float  # signed: negative = under, positive = over
    reference_price_fg: float | None  # median of reference listings
    comparison_note: str


@dataclass
class FGDisplayRender:
    """All data needed to render an FG display panel for one item."""
    item_name: str
    estimate_fg: float | None
    range_low_fg: float | None
    range_high_fg: float | None
    confidence: str | None
    sample_count: int
    recent_listings: list[FGListing]
    market_comparison: MarketComparison | None
    last_updated: datetime | None


class FGDisplay:
    """
    FG display component for the overlay.

    Builds display data for an item by combining price estimates with
    recent market listings, and provides a simple observer mechanism
    for snapshot-refresh notifications.
    """

    # Deviation thresholds for valuation status
    UNDER_VALUED_PCT = -15.0
    OVER_VALUED_PCT = 15.0

    def __init__(self) -> None:
        self._update_callbacks: list[Callable[[], None]] = []

    # ------------------------------------------------------------------
    # Core display builder
    # ------------------------------------------------------------------

    def show_listings(
        self,
        item_id: str,
        variant: str | None,
        price_engine,
    ) -> FGDisplayRender:
        """
        Build display data for an item using the PriceLookupEngine.

        Args:
            item_id: Canonical item ID.
            variant: Optional variant key.
            price_engine: A PriceLookupEngine instance (duck-typed).

        Returns:
            FGDisplayRender ready for formatting / overlay rendering.
        """
        estimate: PriceEstimate | None = price_engine.get_price(item_id, variant)
        listings: list[FGListing] = price_engine.get_fg_listings(item_id, variant)

        recent = [l for l in listings if l.is_recent]

        comparison: MarketComparison | None = None
        if estimate is not None:
            comparison = self.calculate_market_comparison(
                estimate.estimate_fg, recent
            )

        return FGDisplayRender(
            item_name=variant or item_id,
            estimate_fg=estimate.estimate_fg if estimate else None,
            range_low_fg=estimate.range_low_fg if estimate else None,
            range_high_fg=estimate.range_high_fg if estimate else None,
            confidence=estimate.confidence if estimate else None,
            sample_count=estimate.sample_count if estimate else 0,
            recent_listings=recent,
            market_comparison=comparison,
            last_updated=estimate.last_updated if estimate else None,
        )

    # ------------------------------------------------------------------
    # Market comparison
    # ------------------------------------------------------------------

    def calculate_market_comparison(
        self,
        estimate_fg: float,
        listings: list[FGListing],
    ) -> MarketComparison:
        """
        Compare an estimate to recent BIN/sold listings.

        Uses the median of BIN and sold prices as the reference.
        Falls back to all listing types if no BIN/sold exist.

        Args:
            estimate_fg: The item's current price estimate in FG.
            listings: Recent FGListing objects.

        Returns:
            MarketComparison with status, deviation, and note.
        """
        # Prefer BIN and sold prices as reference
        ref_prices = [
            l.price_fg
            for l in listings
            if l.listing_type in ("bin", "sold")
        ]
        note_source = "BIN/sold"

        # Fall back to all listing prices
        if not ref_prices:
            ref_prices = [l.price_fg for l in listings]
            note_source = "all listings"

        if not ref_prices:
            return MarketComparison(
                status="fair",
                deviation_pct=0.0,
                reference_price_fg=None,
                comparison_note="No recent listings for comparison",
            )

        ref_median = _median(ref_prices)

        if ref_median == 0:
            return MarketComparison(
                status="fair",
                deviation_pct=0.0,
                reference_price_fg=0.0,
                comparison_note="Reference price is zero",
            )

        deviation_pct = ((estimate_fg - ref_median) / ref_median) * 100.0

        if deviation_pct <= self.UNDER_VALUED_PCT:
            status = "under_valued"
        elif deviation_pct >= self.OVER_VALUED_PCT:
            status = "over_valued"
        else:
            status = "fair"

        return MarketComparison(
            status=status,
            deviation_pct=round(deviation_pct, 1),
            reference_price_fg=ref_median,
            comparison_note=f"Based on {len(ref_prices)} {note_source} listing(s)",
        )

    # ------------------------------------------------------------------
    # Observer / update subscription
    # ------------------------------------------------------------------

    def subscribe_to_updates(self, callback: Callable[[], None]) -> None:
        """Register a callback for snapshot-refresh notifications."""
        self._update_callbacks.append(callback)

    def notify_update(self) -> None:
        """Notify all subscribers that market data has been refreshed."""
        for cb in self._update_callbacks:
            cb()

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def format_compact(self, render: FGDisplayRender) -> str:
        """
        One-line compact representation for overlay tooltip suffix.

        Example: "Shako - ~120fg (fair)"
        """
        if render.estimate_fg is None:
            return f"{render.item_name} - no data"

        status_tag = ""
        if render.market_comparison is not None:
            status_tag = f" ({render.market_comparison.status.replace('_', ' ')})"

        return f"{render.item_name} - ~{render.estimate_fg:.0f}fg{status_tag}"

    def format_detailed(self, render: FGDisplayRender) -> str:
        """
        Multi-line detailed representation for expanded display.
        """
        lines: list[str] = [render.item_name]

        if render.estimate_fg is not None:
            lines.append(
                f"  Estimate: {render.estimate_fg:.0f}fg "
                f"({render.range_low_fg:.0f}-{render.range_high_fg:.0f}fg)"
            )
            lines.append(
                f"  Confidence: {render.confidence}  Samples: {render.sample_count}"
            )
        else:
            lines.append("  No price data")

        if render.market_comparison is not None and render.market_comparison.reference_price_fg is not None:
            mc = render.market_comparison
            lines.append(
                f"  Market: {mc.status.replace('_', ' ')} "
                f"({mc.deviation_pct:+.1f}% vs {mc.reference_price_fg:.0f}fg ref)"
            )
            lines.append(f"  {mc.comparison_note}")

        if render.recent_listings:
            lines.append(f"  Recent listings: {len(render.recent_listings)}")
            for listing in render.recent_listings[:5]:
                lines.append(
                    f"    {listing.listing_type.upper()} {listing.price_fg:.0f}fg"
                )
        else:
            lines.append("  No recent listings")

        if render.last_updated is not None:
            lines.append(f"  Updated: {render.last_updated:%Y-%m-%d %H:%M}")

        return "\n".join(lines)


# ------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------

def _median(values: list[float]) -> float:
    """Simple median without numpy dependency."""
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0
