"""Presentation layer for stash scan results.

Provides user-friendly display formatting for stash scan results,
including per-item summaries, total value display, and interactive
controls for re-scan and clear operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from datetime import datetime

from d2lut.overlay.stash_scanner import StashScanResult, ScannedItem


@dataclass
class PresentationConfig:
    """Configuration for scan result presentation."""
    show_confidence: bool = True
    show_sample_count: bool = True
    show_price_range: bool = True
    show_scan_duration: bool = True
    show_errors: bool = True
    max_errors_displayed: int = 5
    sort_by: str = "value"  # value, name, slot
    currency_symbol: str = "FG"
    value_thresholds: dict[str, float] | None = None  # low, medium, high
    
    def __post_init__(self):
        """Set default value thresholds if not provided."""
        if self.value_thresholds is None:
            self.value_thresholds = {
                "low": 100.0,
                "medium": 1000.0,
                "high": 5000.0
            }


class StashScanPresenter:
    """
    Presentation layer for stash scan results.
    
    Formats scan results for display with various output formats
    and interactive controls for re-scan and clear operations.
    """
    
    def __init__(self, config: PresentationConfig | None = None):
        """
        Initialize the presenter.
        
        Args:
            config: Presentation configuration
        """
        self.config = config or PresentationConfig()
    
    def format_detailed_summary(self, result: StashScanResult) -> str:
        """
        Format a detailed text summary of scan results.
        
        Args:
            result: StashScanResult to format
        
        Returns:
            Formatted detailed summary string
        """
        lines = []
        
        # Header
        lines.append("╔" + "═" * 58 + "╗")
        lines.append("║" + " " * 18 + "STASH SCAN RESULTS" + " " * 22 + "║")
        lines.append("╚" + "═" * 58 + "╝")
        lines.append("")
        
        # Summary statistics
        lines.append("┌─ Summary " + "─" * 47 + "┐")
        lines.append(f"│ Total Items Scanned:     {len(result.items):>3}                        │")
        lines.append(f"│ Items with Prices:       {result.items_with_prices:>3}                        │")
        lines.append(f"│ Items without Prices:    {result.items_without_prices:>3}                        │")
        lines.append(f"│ Total Stash Value:       {result.total_value_fg:>10,.0f} {self.config.currency_symbol:<10}│")
        
        if self.config.show_scan_duration:
            lines.append(f"│ Scan Duration:           {result.scan_duration_ms:>6.0f}ms                    │")
        
        scan_time = datetime.fromtimestamp(result.scan_timestamp).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"│ Scan Time:               {scan_time:<25}│")
        lines.append("└" + "─" * 58 + "┘")
        lines.append("")
        
        # Errors section
        if self.config.show_errors and result.scan_errors:
            lines.append("┌─ Errors " + "─" * 48 + "┐")
            lines.append(f"│ {len(result.scan_errors)} error(s) encountered during scan" + " " * 23 + "│")
            
            for i, error in enumerate(result.scan_errors[:self.config.max_errors_displayed]):
                error_short = error[:54] if len(error) > 54 else error
                lines.append(f"│ {i+1}. {error_short:<54}│")
            
            if len(result.scan_errors) > self.config.max_errors_displayed:
                remaining = len(result.scan_errors) - self.config.max_errors_displayed
                lines.append(f"│ ... and {remaining} more error(s)" + " " * 36 + "│")
            
            lines.append("└" + "─" * 58 + "┘")
            lines.append("")
        
        # Item details
        lines.append("┌─ Item Details " + "─" * 42 + "┐")
        
        # Sort items
        sorted_items = self._sort_items(result.items)
        
        if not sorted_items:
            lines.append("│ No items found" + " " * 44 + "│")
        else:
            for item in sorted_items:
                item_lines = self._format_item_detail(item)
                lines.extend(item_lines)
        
        lines.append("└" + "─" * 58 + "┘")
        
        return "\n".join(lines)
    
    def format_compact_summary(self, result: StashScanResult) -> str:
        """
        Format a compact one-line summary.
        
        Args:
            result: StashScanResult to format
        
        Returns:
            Compact summary string
        """
        return (
            f"Stash Scan: {len(result.items)} items | "
            f"{result.items_with_prices} priced | "
            f"Total: {result.total_value_fg:,.0f} {self.config.currency_symbol} | "
            f"Duration: {result.scan_duration_ms:.0f}ms"
        )
    
    def format_item_table(self, result: StashScanResult) -> str:
        """
        Format items as a table.
        
        Args:
            result: StashScanResult to format
        
        Returns:
            Formatted table string
        """
        lines = []
        
        # Table header
        lines.append("┌" + "─" * 4 + "┬" + "─" * 25 + "┬" + "─" * 15 + "┬" + "─" * 12 + "┐")
        lines.append("│ #  │ Item Name               │ Price (FG)    │ Confidence │")
        lines.append("├" + "─" * 4 + "┼" + "─" * 25 + "┼" + "─" * 15 + "┼" + "─" * 12 + "┤")
        
        # Sort items
        sorted_items = self._sort_items(result.items)
        
        # Table rows
        for item in sorted_items:
            slot_num = f"{item.slot_index + 1:>2}"
            item_name = item.match_result.matched_name or item.parsed_item.item_name or "Unknown"
            item_name = item_name[:23] if len(item_name) > 23 else item_name
            
            if item.price_estimate:
                price_str = f"{item.price_estimate.estimate_fg:>12,.0f}"
                conf_str = f"{item.price_estimate.confidence:>10}"
            else:
                price_str = "No data".rjust(12)
                conf_str = "N/A".rjust(10)
            
            lines.append(f"│ {slot_num} │ {item_name:<23} │ {price_str} │ {conf_str} │")
        
        # Table footer
        lines.append("├" + "─" * 4 + "┴" + "─" * 25 + "┴" + "─" * 15 + "┴" + "─" * 12 + "┤")
        lines.append(f"│ Total Value: {result.total_value_fg:>12,.0f} {self.config.currency_symbol:<32}│")
        lines.append("└" + "─" * 58 + "┘")
        
        return "\n".join(lines)
    
    def get_item_summaries(self, result: StashScanResult) -> list[dict[str, Any]]:
        """
        Get per-item summaries as structured data.
        
        Args:
            result: StashScanResult to extract from
        
        Returns:
            List of item summary dictionaries
        """
        summaries = []
        
        sorted_items = self._sort_items(result.items)
        for item in sorted_items:
            summary = {
                "slot_index": item.slot_index,
                "slot_number": item.slot_index + 1,
                "item_name": item.match_result.matched_name or item.parsed_item.item_name,
                "canonical_item_id": item.match_result.canonical_item_id,
                "match_confidence": item.match_result.confidence,
                "match_type": item.match_result.match_type,
                "value_tier": self._get_value_tier(item),
            }
            
            if item.price_estimate:
                summary.update({
                    "price_fg": item.price_estimate.estimate_fg,
                    "price_low_fg": item.price_estimate.range_low_fg,
                    "price_high_fg": item.price_estimate.range_high_fg,
                    "price_confidence": item.price_estimate.confidence,
                    "sample_count": item.price_estimate.sample_count,
                    "has_price": True,
                    "price_display": f"{item.price_estimate.estimate_fg:,.0f} {self.config.currency_symbol}",
                })
                
                if self.config.show_price_range:
                    summary["price_range_display"] = (
                        f"{item.price_estimate.range_low_fg:,.0f} - "
                        f"{item.price_estimate.range_high_fg:,.0f} {self.config.currency_symbol}"
                    )
            else:
                summary.update({
                    "price_fg": None,
                    "price_low_fg": None,
                    "price_high_fg": None,
                    "price_confidence": None,
                    "sample_count": None,
                    "has_price": False,
                    "price_display": "No data",
                    "price_range_display": "N/A",
                })
            
            summaries.append(summary)
        
        return summaries
    
    def get_value_breakdown(self, result: StashScanResult) -> dict[str, Any]:
        """
        Get value breakdown by tier.
        
        Args:
            result: StashScanResult to analyze
        
        Returns:
            Dictionary with value breakdown by tier
        """
        breakdown = {
            "total_value": result.total_value_fg,
            "total_items": len(result.items),
            "items_with_prices": result.items_with_prices,
            "items_without_prices": result.items_without_prices,
            "by_tier": {
                "low": {"count": 0, "total_value": 0.0, "items": []},
                "medium": {"count": 0, "total_value": 0.0, "items": []},
                "high": {"count": 0, "total_value": 0.0, "items": []},
                "no_data": {"count": 0, "items": []},
            }
        }
        
        for item in result.items:
            tier = self._get_value_tier(item)
            item_name = item.match_result.matched_name or item.parsed_item.item_name
            
            if tier == "no_data":
                breakdown["by_tier"]["no_data"]["count"] += 1
                breakdown["by_tier"]["no_data"]["items"].append(item_name)
            else:
                breakdown["by_tier"][tier]["count"] += 1
                if item.price_estimate:
                    breakdown["by_tier"][tier]["total_value"] += item.price_estimate.estimate_fg
                    breakdown["by_tier"][tier]["items"].append({
                        "name": item_name,
                        "value": item.price_estimate.estimate_fg
                    })
        
        return breakdown
    
    def format_controls_help(self) -> str:
        """
        Format help text for interactive controls.
        
        Returns:
            Help text string
        """
        lines = []
        lines.append("╔" + "═" * 58 + "╗")
        lines.append("║" + " " * 22 + "CONTROLS" + " " * 28 + "║")
        lines.append("╚" + "═" * 58 + "╝")
        lines.append("")
        lines.append("  Re-scan:  Trigger a new scan of the current stash tab")
        lines.append("  Clear:    Clear cached scan results")
        lines.append("  Export:   Export results to file (future)")
        lines.append("")
        lines.append("  Note: Re-scanning will update all item prices and")
        lines.append("        recalculate the total stash value.")
        lines.append("")
        
        return "\n".join(lines)
    
    def _format_item_detail(self, item: ScannedItem) -> list[str]:
        """Format a single item's details."""
        lines = []
        
        item_name = item.match_result.matched_name or item.parsed_item.item_name or "Unknown"
        slot_num = item.slot_index + 1
        
        # Item header with value tier indicator
        tier = self._get_value_tier(item)
        tier_symbol = self._get_tier_symbol(tier)
        
        lines.append(f"│ {tier_symbol} [{slot_num:>2}] {item_name:<48}│")
        
        # Price information
        if item.price_estimate:
            price_str = f"{item.price_estimate.estimate_fg:,.0f} {self.config.currency_symbol}"
            lines.append(f"│     Price: {price_str:<48}│")
            
            if self.config.show_price_range:
                range_str = (
                    f"{item.price_estimate.range_low_fg:,.0f} - "
                    f"{item.price_estimate.range_high_fg:,.0f} {self.config.currency_symbol}"
                )
                lines.append(f"│     Range: {range_str:<48}│")
            
            if self.config.show_confidence:
                conf_str = f"{item.price_estimate.confidence}"
                lines.append(f"│     Confidence: {conf_str:<43}│")
            
            if self.config.show_sample_count:
                sample_str = f"{item.price_estimate.sample_count} observations"
                lines.append(f"│     Samples: {sample_str:<45}│")
        else:
            lines.append(f"│     Price: No data available{' ' * 28}│")
        
        return lines
    
    def _sort_items(self, items: list[ScannedItem]) -> list[ScannedItem]:
        """Sort items based on configuration."""
        if self.config.sort_by == "value":
            return sorted(
                items,
                key=lambda x: x.price_estimate.estimate_fg if x.price_estimate else 0.0,
                reverse=True
            )
        elif self.config.sort_by == "name":
            return sorted(
                items,
                key=lambda x: x.match_result.matched_name or x.parsed_item.item_name or ""
            )
        else:  # slot
            return sorted(items, key=lambda x: x.slot_index)
    
    def _get_value_tier(self, item: ScannedItem) -> str:
        """Get value tier for an item.

        Thresholds represent reference values for each tier.  The actual
        boundaries sit at the midpoints between adjacent reference values
        so that an item is assigned to the tier whose reference value it
        is closest to (on a linear scale).
        """
        if item.price_estimate is None:
            return "no_data"

        value = item.price_estimate.estimate_fg
        thresholds = self.config.value_thresholds

        high_cutoff = (thresholds["medium"] + thresholds["high"]) / 2
        med_cutoff = (thresholds["low"] + thresholds["medium"]) / 2

        if value >= high_cutoff:
            return "high"
        elif value >= med_cutoff:
            return "medium"
        else:
            return "low"
    
    def _get_tier_symbol(self, tier: str) -> str:
        """Get display symbol for value tier."""
        symbols = {
            "high": "★",
            "medium": "◆",
            "low": "○",
            "no_data": "?",
        }
        return symbols.get(tier, "·")
