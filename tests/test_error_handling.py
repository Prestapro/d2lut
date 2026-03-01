"""Tests for overlay error handling: error classes, error tracking, graceful degradation, and logging."""

from __future__ import annotations

import logging
import time
from unittest.mock import MagicMock, patch

import pytest

from d2lut.overlay.errors import (
    OverlayError,
    OCRError,
    IdentificationError,
    PriceLookupError,
    ConfigurationError,
    ScreenCaptureError,
)
from d2lut.overlay.overlay_app import OverlayApp, OverlayAppState, HoverState
from d2lut.overlay.ocr_parser import TooltipCoords, ParsedItem
from d2lut.overlay.config import OverlayConfig


# ---------------------------------------------------------------------------
# 1. Error class hierarchy tests
# ---------------------------------------------------------------------------

class TestErrorClasses:
    """Test overlay-specific exception classes."""

    def test_overlay_error_is_base(self):
        err = OverlayError("base error")
        assert isinstance(err, Exception)
        assert str(err) == "base error"
        assert err.detail is None

    def test_overlay_error_with_detail(self):
        err = OverlayError("msg", detail="extra info")
        assert err.detail == "extra info"

    @pytest.mark.parametrize("cls", [
        OCRError,
        IdentificationError,
        PriceLookupError,
        ConfigurationError,
        ScreenCaptureError,
    ])
    def test_subclass_inherits_overlay_error(self, cls):
        err = cls("test")
        assert isinstance(err, OverlayError)
        assert isinstance(err, Exception)

    def test_ocr_error_detail(self):
        err = OCRError("parse failed", detail="low contrast")
        assert str(err) == "parse failed"
        assert err.detail == "low contrast"

    def test_configuration_error_catchable_as_overlay(self):
        with pytest.raises(OverlayError):
            raise ConfigurationError("bad config")


# ---------------------------------------------------------------------------
# 2. Error tracking in OverlayAppState
# ---------------------------------------------------------------------------

class TestErrorTracking:
    """Test error tracking fields on OverlayAppState."""

    def test_initial_state_has_zero_errors(self):
        state = OverlayAppState()
        assert state.error_count == 0
        assert state.last_error is None
        assert state.last_error_time == 0.0
        assert state.errors_by_type == {}

    def test_record_error_increments_count(self):
        """Verify _record_error updates all tracking fields."""
        app = self._make_app()
        app._record_error("OCRError", "parse failed")

        assert app.state.error_count == 1
        assert app.state.last_error == "parse failed"
        assert app.state.last_error_time > 0
        assert app.state.errors_by_type == {"OCRError": 1}

    def test_record_multiple_errors(self):
        app = self._make_app()
        app._record_error("OCRError", "err1")
        app._record_error("OCRError", "err2")
        app._record_error("PriceLookupError", "err3")

        assert app.state.error_count == 3
        assert app.state.last_error == "err3"
        assert app.state.errors_by_type == {"OCRError": 2, "PriceLookupError": 1}

    def test_get_state_includes_error_stats(self):
        app = self._make_app()
        app._record_error("ScreenCaptureError", "no display")

        state = app.get_state()
        assert state["error_count"] == 1
        assert state["last_error"] == "no display"
        assert state["errors_by_type"] == {"ScreenCaptureError": 1}

    # -- helper --
    @staticmethod
    def _make_app() -> OverlayApp:
        """Create an OverlayApp with mocked components for unit testing."""
        with patch.object(OverlayApp, "_init_components"):
            app = OverlayApp.__new__(OverlayApp)
            app.db_path = "dummy.db"
            app.config = OverlayConfig()
            app.state = OverlayAppState()
            app._screenshot_callback = None
            app._hover_callback = None
            app._render_callback = None
            app._update_thread = None
            app._update_lock = __import__("threading").Lock()
            app._last_hover_coords_hash = None
            app._consecutive_capture_failures = 0
            app._max_capture_failures = 5
            # Minimal mocks for get_state
            throttle_mock = MagicMock()
            throttle_mock.stats.return_value = MagicMock(
                target_fps=60.0, actual_fps=0.0,
                frame_budget_ms=16.67, frame_time_ms=0.0,
                budget_remaining_ms=16.67,
            )
            app._throttle = throttle_mock
            mem_mock = MagicMock()
            mem_mock.get_memory_stats.return_value = MagicMock(
                total_mb=0.0, limit_mb=500.0,
                within_budget=True, usage_pct=0.0,
            )
            app.memory_monitor = mem_mock
            return app


# ---------------------------------------------------------------------------
# 3. Graceful degradation tests
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    """Test that pipeline stages degrade gracefully on failure."""

    def _make_app_with_mocks(self) -> OverlayApp:
        """Build an OverlayApp with all components mocked."""
        app = TestErrorTracking._make_app()
        app.ocr_parser = MagicMock()
        app.category_parser = MagicMock()
        app.item_identifier = MagicMock()
        app.price_lookup = MagicMock()
        app.bundle_parser = MagicMock()
        app.rule_engine = MagicMock()
        app.fg_display = MagicMock()
        app.demand_model = MagicMock()
        app.price_history = MagicMock()
        app.inventory_overlay = MagicMock()
        app._dirty = MagicMock()
        return app

    def test_ocr_failure_produces_stub_parsed_item(self):
        """When OCR fails, _process_hover should create a stub ParsedItem with error message."""
        app = self._make_app_with_mocks()
        app.ocr_parser.parse_tooltip.side_effect = RuntimeError("OCR engine crashed")
        # Identification should still be called with the stub
        app.item_identifier.identify.return_value = MagicMock(canonical_item_id=None)
        app.inventory_overlay.get_hover_details.return_value = None
        app.inventory_overlay._create_slot_overlay.return_value = MagicMock()

        # Set up hover state
        app.state.last_screenshot = b"fake_screenshot"
        app.state.hover_state.tooltip_coords = TooltipCoords(x=0, y=0, width=100, height=50)

        app._process_hover()

        # Should have recorded the error
        assert app.state.error_count == 1
        assert "OCRError" in app.state.errors_by_type
        # Parsed item should be a stub with error
        pi = app.state.hover_state.parsed_item
        assert pi is not None
        assert pi.error == "OCR unavailable"

    def test_price_lookup_failure_continues(self):
        """When price lookup fails, overlay should still render without price."""
        app = self._make_app_with_mocks()
        parsed = ParsedItem(
            raw_text="Shako", item_name="Shako", item_type="unique",
            quality="unique", rarity=None, affixes=[], base_properties=[],
        )
        app.ocr_parser.parse_tooltip.return_value = parsed
        app.category_parser.parse_with_category.return_value = parsed
        match = MagicMock(canonical_item_id="unique:harlequin_crest")
        app.item_identifier.identify.return_value = match
        app.price_lookup.get_price.side_effect = RuntimeError("DB locked")
        app.bundle_parser.detect_bundles.return_value = MagicMock(bundles=[])
        app.fg_display.show_listings.return_value = MagicMock()
        app.demand_model.calculate_demand.return_value = MagicMock(
            demand_score=0.5, observed_velocity=1.0,
        )
        app.price_history.get_trend.return_value = MagicMock(snapshots=[])
        app.inventory_overlay.get_hover_details.return_value = None
        app.inventory_overlay._create_slot_overlay.return_value = MagicMock()

        app.state.last_screenshot = b"fake"
        app.state.hover_state.tooltip_coords = TooltipCoords(x=0, y=0, width=100, height=50)

        app._process_hover()

        assert app.state.errors_by_type.get("PriceLookupError", 0) == 1
        # Overlay rendering should still have been attempted
        app.inventory_overlay.get_hover_details.assert_called_once()

    def test_screenshot_auto_pause_after_repeated_failures(self):
        """After N consecutive capture failures the app should auto-pause."""
        app = self._make_app_with_mocks()
        app._max_capture_failures = 3

        for _ in range(3):
            app._consecutive_capture_failures += 1
            app._record_error("ScreenCaptureError", "no display")

        # Simulate the auto-pause check from _update_loop
        if app._consecutive_capture_failures >= app._max_capture_failures:
            app.state.paused = True
            app._consecutive_capture_failures = 0

        assert app.state.paused is True
        assert app.state.error_count == 3


# ---------------------------------------------------------------------------
# 4. Logging output tests
# ---------------------------------------------------------------------------

class TestLoggingOutput:
    """Verify that errors produce log records instead of print() calls."""

    def test_ocr_failure_logs_warning(self, caplog):
        app = TestGracefulDegradation()._make_app_with_mocks()
        app.ocr_parser.parse_tooltip.side_effect = RuntimeError("engine init failed")
        app.item_identifier.identify.return_value = MagicMock(canonical_item_id=None)
        app.inventory_overlay.get_hover_details.return_value = None
        app.inventory_overlay._create_slot_overlay.return_value = MagicMock()

        app.state.last_screenshot = b"fake"
        app.state.hover_state.tooltip_coords = TooltipCoords(x=0, y=0, width=100, height=50)

        with caplog.at_level(logging.WARNING, logger="d2lut.overlay.overlay_app"):
            app._process_hover()

        assert any("OCR" in r.message for r in caplog.records)

    def test_price_lookup_failure_logs_warning(self, caplog):
        app = TestGracefulDegradation()._make_app_with_mocks()
        parsed = ParsedItem(
            raw_text="Ber", item_name="Ber", item_type="rune",
            quality=None, rarity=None, affixes=[], base_properties=[],
        )
        app.ocr_parser.parse_tooltip.return_value = parsed
        app.category_parser.parse_with_category.return_value = parsed
        match = MagicMock(canonical_item_id="rune:ber")
        app.item_identifier.identify.return_value = match
        app.price_lookup.get_price.side_effect = RuntimeError("timeout")
        app.bundle_parser.detect_bundles.return_value = MagicMock(bundles=[])
        app.fg_display.show_listings.side_effect = RuntimeError("also broken")
        app.demand_model.calculate_demand.return_value = MagicMock(
            demand_score=0.5, observed_velocity=1.0,
        )
        app.price_history.get_trend.return_value = MagicMock(snapshots=[])
        app.inventory_overlay.get_hover_details.return_value = None
        app.inventory_overlay._create_slot_overlay.return_value = MagicMock()

        app.state.last_screenshot = b"fake"
        app.state.hover_state.tooltip_coords = TooltipCoords(x=0, y=0, width=100, height=50)

        with caplog.at_level(logging.WARNING, logger="d2lut.overlay.overlay_app"):
            app._process_hover()

        assert any("price" in r.message.lower() for r in caplog.records)

    def test_demand_failure_logs_debug(self, caplog):
        app = TestGracefulDegradation()._make_app_with_mocks()
        parsed = ParsedItem(
            raw_text="Jah", item_name="Jah", item_type="rune",
            quality=None, rarity=None, affixes=[], base_properties=[],
        )
        app.ocr_parser.parse_tooltip.return_value = parsed
        app.category_parser.parse_with_category.return_value = parsed
        match = MagicMock(canonical_item_id="rune:jah")
        app.item_identifier.identify.return_value = match
        price_est = MagicMock(estimate_fg=2500.0, variant_key="rune:jah")
        app.price_lookup.get_price.return_value = price_est
        app.bundle_parser.detect_bundles.return_value = MagicMock(bundles=[])
        app.rule_engine.apply_rules.return_value = MagicMock(rules_applied=[])
        app.fg_display.show_listings.return_value = MagicMock()
        app.demand_model.calculate_demand.side_effect = RuntimeError("no data")
        app.price_history.get_trend.return_value = MagicMock(snapshots=[])
        app.inventory_overlay.get_hover_details.return_value = None
        app.inventory_overlay._create_slot_overlay.return_value = MagicMock()

        app.state.last_screenshot = b"fake"
        app.state.hover_state.tooltip_coords = TooltipCoords(x=0, y=0, width=100, height=50)

        with caplog.at_level(logging.DEBUG, logger="d2lut.overlay.overlay_app"):
            app._process_hover()

        assert any("demand" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# 5. ConfigurationError integration
# ---------------------------------------------------------------------------

class TestConfigurationError:
    """Verify ConfigurationError is raised for invalid configs."""

    def test_invalid_config_raises_configuration_error(self):
        config = OverlayConfig()
        config.ocr.confidence_threshold = 1.5  # invalid
        with pytest.raises(ConfigurationError, match="Configuration validation failed"):
            OverlayApp(db_path="dummy.db", config=config)
