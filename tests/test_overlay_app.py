"""Tests for the main overlay application."""

import io
import time
from pathlib import Path
from PIL import Image
import pytest

from d2lut.overlay.overlay_app import OverlayApp, create_app, OverlayAppState, HoverState
from d2lut.overlay.config import OverlayConfig
from d2lut.overlay.ocr_parser import TooltipCoords


@pytest.fixture
def demo_screenshot():
    """Create a demo screenshot for testing."""
    img = Image.new('RGB', (1024, 768), color='black')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    return img_bytes.getvalue()


@pytest.fixture
def test_db_path(tmp_path):
    """Create a temporary test database path."""
    # Note: This would need a real database for full testing
    # For now, we'll use a path that may not exist
    return tmp_path / "test.db"


def test_overlay_app_initialization(test_db_path):
    """Test that OverlayApp can be initialized with default config."""
    # Skip if database doesn't exist
    if not test_db_path.exists():
        pytest.skip("Test database not available")
    
    config = OverlayConfig()
    app = OverlayApp(db_path=test_db_path, config=config)
    
    assert app.db_path == test_db_path
    assert app.config == config
    assert app.state.running is False
    assert app.state.paused is False
    assert app.ocr_parser is not None
    assert app.item_identifier is not None
    assert app.price_lookup is not None
    assert app.inventory_overlay is not None
    assert app.stash_scanner is not None
    
    app.close()


def test_overlay_app_state_initialization():
    """Test that OverlayAppState initializes correctly."""
    state = OverlayAppState()
    
    assert state.running is False
    assert state.paused is False
    assert isinstance(state.hover_state, HoverState)
    assert state.last_screenshot is None
    assert state.frame_count == 0
    assert state.fps == 0.0


def test_hover_state_initialization():
    """Test that HoverState initializes correctly."""
    hover_state = HoverState()
    
    assert hover_state.is_hovering is False
    assert hover_state.tooltip_coords is None
    assert hover_state.last_hover_time == 0.0
    assert hover_state.parsed_item is None
    assert hover_state.match_result is None
    assert hover_state.overlay_details is None


def test_overlay_app_callbacks(test_db_path):
    """Test that callbacks can be set and stored."""
    if not test_db_path.exists():
        pytest.skip("Test database not available")
    
    app = OverlayApp(db_path=test_db_path)
    
    # Set callbacks
    screenshot_called = []
    hover_called = []
    render_called = []
    
    def screenshot_callback():
        screenshot_called.append(True)
        return b"screenshot"
    
    def hover_callback(coords):
        hover_called.append(coords)
    
    def render_callback(overlay_render):
        render_called.append(overlay_render)
    
    app.set_screenshot_callback(screenshot_callback)
    app.set_hover_callback(hover_callback)
    app.set_render_callback(render_callback)
    
    assert app._screenshot_callback is not None
    assert app._hover_callback is not None
    assert app._render_callback is not None
    
    app.close()


def test_overlay_app_lifecycle(test_db_path):
    """Test app lifecycle: start, pause, resume, stop."""
    if not test_db_path.exists():
        pytest.skip("Test database not available")
    
    app = OverlayApp(db_path=test_db_path)
    
    # Initial state
    assert app.state.running is False
    assert app.state.paused is False
    
    # Start
    app.start()
    assert app.state.running is True
    assert app.state.paused is False
    
    # Pause
    app.pause()
    assert app.state.paused is True
    
    # Resume
    app.resume()
    assert app.state.paused is False
    
    # Toggle pause
    paused = app.toggle_pause()
    assert paused is True
    assert app.state.paused is True
    
    paused = app.toggle_pause()
    assert paused is False
    assert app.state.paused is False
    
    # Stop
    app.stop()
    # Note: running may still be True briefly during shutdown
    
    app.close()


def test_overlay_app_hover_events(test_db_path, demo_screenshot):
    """Test hover event handling."""
    if not test_db_path.exists():
        pytest.skip("Test database not available")
    
    app = OverlayApp(db_path=test_db_path)
    
    # Set screenshot
    app.state.last_screenshot = demo_screenshot
    
    # Start hover
    coords = TooltipCoords(x=100, y=100, width=200, height=150)
    app.on_hover_start(coords)
    
    assert app.state.hover_state.is_hovering is True
    assert app.state.hover_state.tooltip_coords == coords
    assert app.state.hover_state.last_hover_time > 0
    
    # End hover
    app.on_hover_end()
    
    assert app.state.hover_state.is_hovering is False
    assert app.state.hover_state.tooltip_coords is None
    
    app.close()


def test_overlay_app_stash_scan(test_db_path, demo_screenshot):
    """Test stash scanning functionality."""
    if not test_db_path.exists():
        pytest.skip("Test database not available")
    
    app = OverlayApp(db_path=test_db_path)
    
    # Define tooltip coordinates
    coords_list = [
        TooltipCoords(x=100, y=100, width=200, height=150),
        TooltipCoords(x=350, y=100, width=200, height=150),
    ]
    
    # Perform scan
    result = app.scan_stash_tab(demo_screenshot, coords_list)
    
    assert result is not None
    assert len(result.items) == len(coords_list)
    assert result.total_value_fg >= 0
    assert result.scan_duration_ms > 0
    
    # Get last scan
    last_scan = app.get_last_stash_scan()
    assert last_scan == result
    
    # Clear scan
    app.clear_stash_scan()
    last_scan = app.get_last_stash_scan()
    assert last_scan is None
    
    app.close()


def test_overlay_app_get_state(test_db_path):
    """Test getting app state."""
    if not test_db_path.exists():
        pytest.skip("Test database not available")
    
    app = OverlayApp(db_path=test_db_path)
    
    state = app.get_state()
    
    assert isinstance(state, dict)
    assert "running" in state
    assert "paused" in state
    assert "is_hovering" in state
    assert "frame_count" in state
    assert "fps" in state
    assert "last_screenshot_time" in state
    assert "has_screenshot" in state
    
    assert state["running"] is False
    assert state["paused"] is False
    assert state["is_hovering"] is False
    assert state["frame_count"] == 0
    assert state["has_screenshot"] is False
    
    app.close()


def test_overlay_app_context_manager(test_db_path):
    """Test that OverlayApp works as a context manager."""
    if not test_db_path.exists():
        pytest.skip("Test database not available")
    
    with OverlayApp(db_path=test_db_path) as app:
        assert app is not None
        assert app.state.running is False
    
    # App should be closed after context exit


def test_create_app_helper(test_db_path):
    """Test the create_app helper function."""
    if not test_db_path.exists():
        pytest.skip("Test database not available")
    
    app = create_app(test_db_path)
    
    assert isinstance(app, OverlayApp)
    assert app.db_path == test_db_path
    
    app.close()


def test_overlay_app_config_validation():
    """Test that invalid config raises error."""
    # Create invalid config
    config = OverlayConfig()
    config.ocr.confidence_threshold = 1.5  # Invalid: > 1.0
    
    with pytest.raises(Exception, match="Configuration validation failed"):
        app = OverlayApp(db_path="dummy.db", config=config)


def test_overlay_app_stash_scan_requires_coords(test_db_path, demo_screenshot):
    """Test that stash scan requires tooltip coordinates."""
    if not test_db_path.exists():
        pytest.skip("Test database not available")
    
    app = OverlayApp(db_path=test_db_path)
    
    with pytest.raises(ValueError, match="tooltip_coords_list must be provided"):
        app.scan_stash_tab(demo_screenshot, None)
    
    app.close()


def test_overlay_app_stash_scan_requires_screenshot(test_db_path):
    """Test that stash scan requires a screenshot."""
    if not test_db_path.exists():
        pytest.skip("Test database not available")
    
    app = OverlayApp(db_path=test_db_path)
    
    coords_list = [TooltipCoords(x=100, y=100, width=200, height=150)]
    
    with pytest.raises(ValueError, match="No screenshot available"):
        app.scan_stash_tab(None, coords_list)
    
    app.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
