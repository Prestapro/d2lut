"""Main overlay application entry point for d2lut overlay system.

This module provides the main application that orchestrates the complete
OCR → Identification → Pricing → Overlay workflow. It initializes all
components, sets up screen capture, implements hover detection, and
manages the overlay display.
"""

from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import threading

from PIL import Image
import numpy as np

from d2lut.overlay.config import OverlayConfig, load_config
from d2lut.overlay.errors import (
    OverlayError,
    OCRError,
    IdentificationError,
    PriceLookupError,
    ConfigurationError,
    ScreenCaptureError,
)
from d2lut.overlay.ocr_parser import OCRTooltipParser, TooltipCoords, ParsedItem
from d2lut.overlay.category_aware_parser import CategoryAwareParser
from d2lut.overlay.item_identifier import ItemIdentifier, MatchResult
from d2lut.overlay.price_lookup import PriceLookupEngine
from d2lut.overlay.inventory_overlay import (
    InventoryOverlay,
    InventoryState,
    InventorySlot,
    OverlayRender,
    OverlayDetails
)
from d2lut.overlay.stash_scanner import StashScanner, StashScanResult
from d2lut.overlay.bundle_parser import BundleParser, BundleResult
from d2lut.overlay.rule_engine import RuleEngine, AdjustedPriceEstimate, load_default_rules
from d2lut.overlay.fg_display import FGDisplay, FGDisplayRender
from d2lut.overlay.demand_model import DemandModel, DemandMetrics
from d2lut.overlay.price_history import PriceHistoryTracker, PriceTrend
from d2lut.overlay.frame_throttle import FrameRateThrottle, DirtyFrameDetector
from d2lut.overlay.memory_monitor import MemoryMonitor, ComponentMemoryStats, estimate_object_size
from d2lut.overlay.label_ux import RefreshStatus, derive_refresh_status

logger = logging.getLogger(__name__)


@dataclass
class HoverState:
    """Represents the current hover state."""
    is_hovering: bool = False
    tooltip_coords: TooltipCoords | None = None
    last_hover_time: float = 0.0
    parsed_item: ParsedItem | None = None
    match_result: MatchResult | None = None
    overlay_details: OverlayDetails | None = None
    bundle_result: BundleResult | None = None
    adjusted_price: AdjustedPriceEstimate | None = None
    fg_display_render: FGDisplayRender | None = None
    demand_metrics: DemandMetrics | None = None
    price_trend: PriceTrend | None = None


@dataclass
class OverlayAppState:
    """Current state of the overlay application."""
    running: bool = False
    paused: bool = False
    hover_state: HoverState = field(default_factory=HoverState)
    last_screenshot: bytes | None = None
    last_screenshot_time: float = 0.0
    frame_count: int = 0
    fps: float = 0.0
    # Error tracking
    error_count: int = 0
    last_error: str | None = None
    last_error_time: float = 0.0
    errors_by_type: dict[str, int] = field(default_factory=dict)
    # Refresh status for overlay UX
    refresh_status: RefreshStatus = RefreshStatus.STALE


class OverlayApp:
    """
    Main overlay application that orchestrates the complete workflow.
    
    This application:
    - Initializes all components (OCR, identifier, pricing, overlay)
    - Sets up screen capture loop
    - Implements hover detection and tooltip parsing
    - Wires OCR → Identification → Pricing → Overlay flow
    - Manages overlay display and updates
    """
    
    def __init__(
        self,
        db_path: str | Path,
        config: OverlayConfig | None = None,
        config_path: str | Path | None = None
    ):
        """
        Initialize the overlay application.
        
        Args:
            db_path: Path to the d2lut database
            config: OverlayConfig instance (if None, loads from config_path or uses default)
            config_path: Path to configuration file (used if config is None)
        """
        self.db_path = Path(db_path)
        
        # Load configuration
        if config is None:
            self.config = load_config(config_path)
        else:
            self.config = config
        
        # Validate configuration
        errors = self.config.validate()
        if errors:
            raise ConfigurationError(
                "Configuration validation failed",
                detail="\n".join(f"  - {e}" for e in errors),
            )
        
        # Initialize components
        self._init_components()
        
        # Application state
        self.state = OverlayAppState()
        
        # Callbacks for external integration
        self._screenshot_callback: Callable[[], bytes] | None = None
        self._hover_callback: Callable[[TooltipCoords], None] | None = None
        self._render_callback: Callable[[OverlayRender], None] | None = None
        
        # Frame throttle and dirty-frame detection
        self._throttle = FrameRateThrottle(target_fps=60.0)
        self._dirty = DirtyFrameDetector(debounce_ms=50.0)

        # Hover-result cache: skip redundant OCR when tooltip hasn't moved
        self._last_hover_coords_hash: tuple[int, int, int, int] | None = None

        # Consecutive screenshot capture failures for auto-pause
        self._consecutive_capture_failures: int = 0
        self._max_capture_failures: int = 5

        # Threading
        self._update_thread: threading.Thread | None = None
        self._update_lock = threading.Lock()
    
    def _init_components(self) -> None:
        """Initialize all overlay components."""
        # OCR Parser
        self.ocr_parser = OCRTooltipParser(
            engine=self.config.ocr.engine,
            confidence_threshold=self.config.ocr.confidence_threshold,
            preprocess_config=self.config.ocr.preprocess
        )
        
        # Item Identifier
        self.category_parser = CategoryAwareParser()

        # Item Identifier
        self.item_identifier = ItemIdentifier(
            db_path=self.db_path,
            fuzzy_threshold=0.8  # Could be made configurable
        )
        
        # Price Lookup Engine
        self.price_lookup = PriceLookupEngine(db_path=self.db_path)
        
        # Inventory Overlay
        self.inventory_overlay = InventoryOverlay(
            low_value_threshold=self.config.overlay.color_thresholds["low"],
            medium_value_threshold=self.config.overlay.color_thresholds["medium"]
        )
        
        # Stash Scanner
        self.stash_scanner = StashScanner(
            ocr_parser=self.ocr_parser,
            item_identifier=self.item_identifier,
            price_lookup=self.price_lookup
        )
        
        # Bundle Parser (task 15.2)
        self.bundle_parser = BundleParser()
        
        # Rule Engine with default rules (task 15.3)
        self.rule_engine = RuleEngine()
        for rule in load_default_rules():
            self.rule_engine.add_rule(rule)
        
        # FG Display (task 15.4)
        self.fg_display = FGDisplay()

        # Demand Model (task 17.2)
        self.demand_model = DemandModel(db_path=self.db_path)

        # Price History Tracker (task 18.2)
        self.price_history = PriceHistoryTracker(db_path=self.db_path)

        # Memory Monitor (task 22.2)
        self.memory_monitor = MemoryMonitor(memory_limit_mb=500.0)
        self._register_memory_components()
    
    def _register_memory_components(self) -> None:
        """Register key caches/buffers with the memory monitor."""
        self.memory_monitor.register(
            "price_cache",
            estimator=lambda: ComponentMemoryStats(
                name="price_cache",
                bytes_used=self.price_lookup.estimate_memory_bytes(),
                detail=self.price_lookup.get_cache_stats(),
            ),
            evictor=self.price_lookup.clear_cache,
        )
        self.memory_monitor.register(
            "screenshot_buffer",
            estimator=lambda: ComponentMemoryStats(
                name="screenshot_buffer",
                bytes_used=len(self.state.last_screenshot) if self.state.last_screenshot else 0,
            ),
            evictor=self._evict_screenshot,
        )
        self.memory_monitor.register(
            "price_history",
            estimator=lambda: ComponentMemoryStats(
                name="price_history",
                bytes_used=self.price_history.estimate_memory_bytes(),
            ),
        )

    def _evict_screenshot(self) -> None:
        """Drop the cached screenshot to free memory."""
        self.state.last_screenshot = None

    def set_screenshot_callback(self, callback: Callable[[], bytes]) -> None:
        """
        Set callback for capturing screenshots.
        
        Args:
            callback: Function that returns screenshot as bytes
        """
        self._screenshot_callback = callback
    
    def set_hover_callback(self, callback: Callable[[TooltipCoords], None]) -> None:
        """
        Set callback for hover events.
        
        Args:
            callback: Function called when hover is detected with tooltip coordinates
        """
        self._hover_callback = callback
    
    def set_render_callback(self, callback: Callable[[OverlayRender], None]) -> None:
        """
        Set callback for rendering overlay.
        
        Args:
            callback: Function called with OverlayRender data to display
        """
        self._render_callback = callback
    
    def _record_error(self, error_type: str, message: str) -> None:
        """Record an error for diagnostics tracking."""
        self.state.error_count += 1
        self.state.last_error = message
        self.state.last_error_time = time.time()
        self.state.errors_by_type[error_type] = (
            self.state.errors_by_type.get(error_type, 0) + 1
        )

    def start(self) -> None:
        """Start the overlay application."""
        if self.state.running:
            return
        
        self.state.running = True
        self.state.paused = False
        logger.info("Overlay application starting")
        
        # Start update thread
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()
    
    def stop(self) -> None:
        """Stop the overlay application."""
        self.state.running = False
        logger.info("Overlay application stopping")
        
        if self._update_thread:
            self._update_thread.join(timeout=2.0)
            self._update_thread = None
    
    def pause(self) -> None:
        """Pause the overlay updates."""
        self.state.paused = True
        logger.info("Overlay application paused")
    
    def resume(self) -> None:
        """Resume the overlay updates."""
        self.state.paused = False
        logger.info("Overlay application resumed")
        self._throttle.reset()
        self._dirty.force_dirty()
    
    def toggle_pause(self) -> bool:
        """
        Toggle pause state.
        
        Returns:
            New pause state (True if paused, False if running)
        """
        self.state.paused = not self.state.paused
        return self.state.paused
    
    def _update_loop(self) -> None:
        """Main update loop for the overlay application.

        Uses FrameRateThrottle for sleep-based pacing (no busy-wait) and
        DirtyFrameDetector to skip rendering when nothing changed.
        """
        self._throttle.reset()
        self._dirty.reset()
        self._dirty.force_dirty()  # render at least once on start

        while self.state.running:
            try:
                self._throttle.begin_frame()

                # Skip work if paused – just sleep the frame budget
                if self.state.paused:
                    self._throttle.wait()
                    continue

                with self._update_lock:
                    # Capture screenshot (always, so dirty detector can react)
                    if self._screenshot_callback:
                        try:
                            screenshot = self._screenshot_callback()
                            self.state.last_screenshot = screenshot
                            self.state.last_screenshot_time = time.time()
                            self._dirty.mark_screenshot(self.state.last_screenshot_time)
                            self._consecutive_capture_failures = 0
                        except Exception as e:
                            self._consecutive_capture_failures += 1
                            self._record_error("ScreenCaptureError", str(e))
                            logger.warning(
                                "Screenshot capture failed (%d/%d): %s",
                                self._consecutive_capture_failures,
                                self._max_capture_failures,
                                e,
                            )
                            if self._consecutive_capture_failures >= self._max_capture_failures:
                                logger.error(
                                    "Screenshot capture failed %d times consecutively, auto-pausing",
                                    self._consecutive_capture_failures,
                                )
                                self.state.paused = True
                                self._consecutive_capture_failures = 0

                    # Feed current hover state into dirty detector
                    hs = self.state.hover_state
                    coords_tuple = (
                        (hs.tooltip_coords.x, hs.tooltip_coords.y,
                         hs.tooltip_coords.width, hs.tooltip_coords.height)
                        if hs.tooltip_coords else None
                    )
                    self._dirty.mark_hover_change(hs.is_hovering, coords_tuple)

                    # Only do expensive work when something changed
                    if self._dirty.needs_render():
                        if hs.is_hovering and hs.tooltip_coords:
                            self._process_hover()
                        self.state.frame_count += 1

                    # Periodic memory budget check (every 300 frames ≈ 5s at 60fps)
                    if self.state.frame_count > 0 and self.state.frame_count % 300 == 0:
                        self.memory_monitor.check_and_evict()

                # Sleep remainder of frame budget
                self._throttle.wait()

                # Publish FPS from throttle's rolling window
                self.state.fps = self._throttle.actual_fps

            except Exception as e:
                self._record_error("UpdateLoopError", str(e))
                logger.error("Error in update loop: %s", e, exc_info=True)
                time.sleep(0.1)
    
    def _process_hover(self) -> None:
        """Process the current hover state and update overlay.

        Caches the previous result and skips redundant OCR/identification
        when the tooltip coordinates haven't moved.  Degrades gracefully
        when individual pipeline stages fail.
        """
        if not self.state.last_screenshot:
            return
        
        coords = self.state.hover_state.tooltip_coords
        if not coords:
            return

        # Cache key: skip expensive OCR if same tooltip is still hovered
        coords_hash = (coords.x, coords.y, coords.width, coords.height)
        if coords_hash == self._last_hover_coords_hash and self.state.hover_state.parsed_item is not None:
            # Tooltip hasn't moved and we already have results – just re-trigger render
            if self._render_callback and self.state.hover_state.overlay_details:
                price_estimate = (
                    self.state.hover_state.overlay_details.price_estimate
                    if hasattr(self.state.hover_state.overlay_details, "price_estimate")
                    else None
                )
                slot = InventorySlot(
                    slot_id=0,
                    item_id=(self.state.hover_state.match_result.canonical_item_id
                             if self.state.hover_state.match_result else None),
                    variant_key=None,
                    parsed_item=self.state.hover_state.parsed_item,
                    price_estimate=None,
                )
                overlay_render = OverlayRender(
                    slots={0: self.inventory_overlay._create_slot_overlay(slot)},
                    total_value_fg=None,
                    enabled=True,
                )
                self._render_callback(overlay_render)
            return

        self._last_hover_coords_hash = coords_hash
        coords = self.state.hover_state.tooltip_coords
        if not coords:
            return

        # --- OCR stage ---
        parsed_item: ParsedItem | None = None
        try:
            parsed_item = self.ocr_parser.parse_tooltip(
                self.state.last_screenshot,
                coords
            )
            parsed_item = self.category_parser.parse_with_category(parsed_item)
            self.state.hover_state.parsed_item = parsed_item
        except Exception as e:
            self._record_error("OCRError", str(e))
            logger.warning("OCR parsing failed (tooltip will show 'OCR unavailable'): %s", e)
            # Graceful degradation: create a stub ParsedItem so overlay can still render
            parsed_item = ParsedItem(
                raw_text="",
                item_name=None,
                item_type=None,
                quality=None,
                rarity=None,
                affixes=[],
                base_properties=[],
                error="OCR unavailable",
                confidence=0.0,
            )
            self.state.hover_state.parsed_item = parsed_item

        # --- Identification stage ---
        match_result: MatchResult | None = None
        try:
            match_result = self.item_identifier.identify(parsed_item)
            self.state.hover_state.match_result = match_result
        except Exception as e:
            self._record_error("IdentificationError", str(e))
            logger.warning("Item identification failed: %s", e)

        # --- Price lookup stage ---
        price_estimate = None
        if match_result and match_result.canonical_item_id:
            try:
                price_estimate = self.price_lookup.get_price(
                    match_result.canonical_item_id,
                    variant=None
                )
            except Exception as e:
                self._record_error("PriceLookupError", str(e))
                logger.warning("Price lookup failed (will show 'price unavailable'): %s", e)

        # --- Bundle detection (task 15.2) ---
        bundle_result = None
        if parsed_item.item_name:
            try:
                bundle_result = self.bundle_parser.detect_bundles([parsed_item.item_name])
                self.state.hover_state.bundle_result = bundle_result
            except Exception as e:
                logger.debug("Bundle detection failed: %s", e)

        # --- Rule engine adjustments (task 15.3) ---
        adjusted_price = None
        if price_estimate is not None and price_estimate.estimate_fg is not None:
            try:
                adjusted_price = self.rule_engine.apply_rules(
                    parsed_item, price_estimate.estimate_fg
                )
                self.state.hover_state.adjusted_price = adjusted_price
            except Exception as e:
                logger.debug("Rule engine failed: %s", e)

        # --- FG display (task 15.4) ---
        fg_render = None
        if match_result and match_result.canonical_item_id:
            try:
                fg_render = self.fg_display.show_listings(
                    match_result.canonical_item_id,
                    variant=None,
                    price_engine=self.price_lookup,
                )
                self.state.hover_state.fg_display_render = fg_render
            except Exception as e:
                logger.debug("FG display failed: %s", e)

        # --- Demand metrics (task 17.2) ---
        demand_metrics = None
        variant_key = (
            price_estimate.variant_key
            if price_estimate is not None
            else (match_result.canonical_item_id if match_result else None)
        )
        if variant_key:
            try:
                demand_metrics = self.demand_model.calculate_demand(variant_key)
                self.state.hover_state.demand_metrics = demand_metrics
                if price_estimate is not None:
                    price_estimate.demand_score = demand_metrics.demand_score
                    price_estimate.observed_velocity = demand_metrics.observed_velocity
            except Exception as e:
                logger.debug("Demand metrics calculation skipped: %s", e)

        # --- Price trend (task 18.2) ---
        if variant_key:
            try:
                price_trend = self.price_history.get_trend(variant_key)
                self.state.hover_state.price_trend = price_trend
            except Exception as e:
                logger.debug("Price trend lookup skipped: %s", e)

        # --- Overlay rendering ---
        slot = InventorySlot(
            slot_id=0,
            item_id=match_result.canonical_item_id if match_result else None,
            variant_key=None,
            parsed_item=parsed_item,
            price_estimate=price_estimate
        )

        overlay_details = self.inventory_overlay.get_hover_details(slot)
        self.state.hover_state.overlay_details = overlay_details

        if self._render_callback:
            overlay_render = OverlayRender(
                slots={0: self.inventory_overlay._create_slot_overlay(slot)},
                total_value_fg=price_estimate.estimate_fg if price_estimate else None,
                enabled=True
            )
            self._render_callback(overlay_render)
    
    def on_hover_start(self, tooltip_coords: TooltipCoords) -> None:
        """
        Handle hover start event.
        
        Args:
            tooltip_coords: Coordinates of the tooltip being hovered
        """
        with self._update_lock:
            self.state.hover_state.is_hovering = True
            self.state.hover_state.tooltip_coords = tooltip_coords
            self.state.hover_state.last_hover_time = time.time()
            
            # Trigger hover callback if set
            if self._hover_callback:
                self._hover_callback(tooltip_coords)
    
    def on_hover_end(self) -> None:
        """Handle hover end event."""
        with self._update_lock:
            self.state.hover_state.is_hovering = False
            self.state.hover_state.tooltip_coords = None
            self.state.hover_state.parsed_item = None
            self.state.hover_state.match_result = None
            self.state.hover_state.overlay_details = None
            self.state.hover_state.bundle_result = None
            self.state.hover_state.adjusted_price = None
            self.state.hover_state.fg_display_render = None
            self.state.hover_state.demand_metrics = None
            self.state.hover_state.price_trend = None
            self._last_hover_coords_hash = None
    
    def scan_stash_tab(
        self,
        screenshot: bytes | None = None,
        tooltip_coords_list: list[TooltipCoords] | None = None
    ) -> StashScanResult:
        """
        Perform a manual stash tab scan.
        
        Args:
            screenshot: Screenshot bytes (uses last screenshot if None)
            tooltip_coords_list: List of tooltip coordinates (must be provided)
        
        Returns:
            StashScanResult with scanned items and value summary
        """
        if tooltip_coords_list is None:
            raise ValueError("tooltip_coords_list must be provided for stash scanning")
        
        # Use provided screenshot or last captured screenshot
        scan_screenshot = screenshot if screenshot is not None else self.state.last_screenshot
        
        if scan_screenshot is None:
            raise ValueError("No screenshot available for scanning")
        
        # Perform scan
        result = self.stash_scanner.scan_stash_tab(scan_screenshot, tooltip_coords_list)
        
        return result
    
    def get_last_stash_scan(self) -> StashScanResult | None:
        """
        Get the last stash scan result.
        
        Returns:
            Last StashScanResult or None if no scan has been performed
        """
        return self.stash_scanner.get_last_scan_result()
    
    def clear_stash_scan(self) -> None:
        """Clear the cached stash scan result."""
        self.stash_scanner.clear_last_scan()
    
    def get_hover_details(self) -> OverlayDetails | None:
        """
        Get current hover details.
        
        Returns enriched OverlayDetails including rule-adjusted prices,
        bundle info, and market comparison when available.
        
        Returns:
            OverlayDetails if hovering, None otherwise
        """
        with self._update_lock:
            details = self.state.hover_state.overlay_details
            if details is None:
                return None
            
            # Enrich with rule-adjusted price (task 15.3)
            adjusted = self.state.hover_state.adjusted_price
            if adjusted is not None and adjusted.rules_applied:
                details.market_activity = details.market_activity or {}
                details.market_activity["adjusted_price_fg"] = adjusted.adjusted_estimate_fg
                details.market_activity["rules_applied"] = adjusted.rules_applied
                details.market_activity["adjustment_reason"] = adjusted.adjustment_reason
            
            # Enrich with bundle info (task 15.2)
            bundle_result = self.state.hover_state.bundle_result
            if bundle_result is not None and bundle_result.bundles:
                details.market_activity = details.market_activity or {}
                details.market_activity["bundle_names"] = [
                    b.bundle_name for b in bundle_result.bundles
                ]
            
            # Enrich with market comparison (task 15.4)
            fg_render = self.state.hover_state.fg_display_render
            if fg_render is not None:
                details.market_activity = details.market_activity or {}
                details.market_activity["recent_listing_count"] = len(fg_render.recent_listings)
                if fg_render.market_comparison is not None:
                    mc = fg_render.market_comparison
                    details.market_activity["market_status"] = mc.status
                    details.market_activity["market_deviation_pct"] = mc.deviation_pct

            # Enrich with demand metrics (task 17.2)
            dm = self.state.hover_state.demand_metrics
            if dm is not None:
                details.market_activity = details.market_activity or {}
                details.market_activity["market_heat"] = dm.market_heat
                details.market_activity["demand_score"] = dm.demand_score
                details.market_activity["observed_velocity"] = dm.observed_velocity

            # Enrich with price trend (task 18.2)
            trend = self.state.hover_state.price_trend
            if trend is not None and trend.snapshots:
                details.market_activity = details.market_activity or {}
                details.market_activity["price_stability"] = trend.stability
                details.market_activity["price_direction"] = trend.direction
                details.market_activity["price_change_pct"] = trend.price_change_pct
                details.market_activity["price_history_count"] = len(trend.snapshots)
            
            return details
    
    def get_state(self) -> dict[str, Any]:
        """
        Get current application state.
        
        Returns:
            Dictionary with application state information including
            frame timing stats from the throttle.
        """
        with self._update_lock:
            frame_stats = self._throttle.stats()
            mem_report = self.memory_monitor.get_memory_stats()
            return {
                "running": self.state.running,
                "paused": self.state.paused,
                "is_hovering": self.state.hover_state.is_hovering,
                "frame_count": self.state.frame_count,
                "fps": self.state.fps,
                "last_screenshot_time": self.state.last_screenshot_time,
                "has_screenshot": self.state.last_screenshot is not None,
                "target_fps": frame_stats.target_fps,
                "actual_fps": frame_stats.actual_fps,
                "frame_budget_ms": frame_stats.frame_budget_ms,
                "frame_time_ms": frame_stats.frame_time_ms,
                "budget_remaining_ms": frame_stats.budget_remaining_ms,
                "memory_total_mb": round(mem_report.total_mb, 2),
                "memory_limit_mb": round(mem_report.limit_mb, 2),
                "memory_within_budget": mem_report.within_budget,
                "memory_usage_pct": round(mem_report.usage_pct, 2),
                "error_count": self.state.error_count,
                "last_error": self.state.last_error,
                "errors_by_type": dict(self.state.errors_by_type),
                "refresh_status": self.state.refresh_status.value,
            }
    
    def reload_config(self, config_path: str | Path | None = None) -> None:
        """
        Reload configuration from file.
        
        Args:
            config_path: Path to configuration file (uses original if None)
        """
        new_config = load_config(config_path)
        errors = new_config.validate()
        
        if errors:
            raise ConfigurationError(
                "Configuration validation failed",
                detail="\n".join(f"  - {e}" for e in errors),
            )
        
        # Update configuration
        self.config = new_config
        
        # Reinitialize components with new config
        self._init_components()
    
    def reload_catalog(self) -> None:
        """Reload catalog and slang data from database."""
        self.item_identifier.reload_cache()

    def update_refresh_status(
        self,
        last_refresh: "datetime | None" = None,
        is_refreshing: bool = False,
        last_refresh_error: str | None = None,
        stale_threshold_hours: float = 24.0,
    ) -> RefreshStatus:
        """Derive and store the current market-data refresh status.

        Call this from the runner after a refresh attempt or periodically
        so the overlay UX can display LIVE/STALE/REFRESHING/ERROR.

        Returns the newly computed :class:`RefreshStatus`.
        """
        status = derive_refresh_status(
            last_refresh=last_refresh,
            is_refreshing=is_refreshing,
            last_error=last_refresh_error,
            stale_threshold_hours=stale_threshold_hours,
        )
        with self._update_lock:
            self.state.refresh_status = status
        return status
    
    def close(self) -> None:
        """Close the overlay application and clean up resources."""
        self.stop()
        self.price_lookup.close()
        self.demand_model.close()
        self.price_history.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def create_app(
    db_path: str | Path,
    config_path: str | Path | None = None
) -> OverlayApp:
    """
    Create and initialize an overlay application.
    
    Args:
        db_path: Path to the d2lut database
        config_path: Optional path to configuration file
    
    Returns:
        Initialized OverlayApp instance
    """
    return OverlayApp(db_path=db_path, config_path=config_path)
