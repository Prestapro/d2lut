"""Tests for scan trigger functionality."""

import pytest
import time
from unittest.mock import Mock

from d2lut.overlay.scan_trigger import ScanTrigger, ScanTriggerConfig


@pytest.fixture
def trigger_config():
    """Create a basic trigger configuration."""
    return ScanTriggerConfig(
        hotkey="ctrl+shift+s",
        enabled=True,
        cooldown_ms=1000
    )


@pytest.fixture
def scan_trigger(trigger_config):
    """Create a scan trigger with default config."""
    return ScanTrigger(config=trigger_config)


def test_scan_trigger_initialization(scan_trigger, trigger_config):
    """Test scan trigger initializes correctly."""
    assert scan_trigger.config == trigger_config
    assert scan_trigger._scan_callback is None
    assert scan_trigger._last_trigger_time == 0.0


def test_scan_trigger_default_config():
    """Test scan trigger with default configuration."""
    trigger = ScanTrigger()
    
    assert trigger.config.hotkey is None
    assert trigger.config.enabled is True
    assert trigger.config.cooldown_ms == 1000


def test_set_scan_callback(scan_trigger):
    """Test setting scan callback."""
    callback = Mock()
    scan_trigger.set_scan_callback(callback)
    
    assert scan_trigger._scan_callback == callback


def test_trigger_executes_callback(scan_trigger):
    """Test that trigger executes the callback."""
    callback = Mock()
    scan_trigger.set_scan_callback(callback)
    
    result = scan_trigger.trigger()
    
    assert result is True
    callback.assert_called_once()


def test_trigger_without_callback(scan_trigger):
    """Test triggering without a callback set."""
    result = scan_trigger.trigger()
    
    # Should return True even without callback
    assert result is True


def test_trigger_respects_cooldown(scan_trigger):
    """Test that trigger respects cooldown period."""
    callback = Mock()
    scan_trigger.set_scan_callback(callback)
    
    # First trigger should succeed
    result1 = scan_trigger.trigger()
    assert result1 is True
    assert callback.call_count == 1
    
    # Immediate second trigger should fail (cooldown)
    result2 = scan_trigger.trigger()
    assert result2 is False
    assert callback.call_count == 1  # Not called again
    
    # Wait for cooldown to expire
    time.sleep(1.1)  # Wait slightly longer than 1000ms cooldown
    
    # Third trigger should succeed
    result3 = scan_trigger.trigger()
    assert result3 is True
    assert callback.call_count == 2


def test_trigger_when_disabled(scan_trigger):
    """Test that trigger doesn't work when disabled."""
    callback = Mock()
    scan_trigger.set_scan_callback(callback)
    
    # Disable trigger
    scan_trigger.disable()
    
    result = scan_trigger.trigger()
    
    assert result is False
    callback.assert_not_called()


def test_enable_disable(scan_trigger):
    """Test enable/disable functionality."""
    assert scan_trigger.is_enabled() is True
    
    scan_trigger.disable()
    assert scan_trigger.is_enabled() is False
    
    scan_trigger.enable()
    assert scan_trigger.is_enabled() is True


def test_set_cooldown(scan_trigger):
    """Test setting cooldown period."""
    scan_trigger.set_cooldown(2000)
    assert scan_trigger.config.cooldown_ms == 2000


def test_get_time_until_ready(scan_trigger):
    """Test getting time until next trigger is ready."""
    callback = Mock()
    scan_trigger.set_scan_callback(callback)
    
    # Initially should be ready
    assert scan_trigger.get_time_until_ready() == 0.0
    
    # Trigger once
    scan_trigger.trigger()
    
    # Should have some cooldown remaining
    remaining = scan_trigger.get_time_until_ready()
    assert 0 < remaining <= 1000
    
    # Wait for cooldown
    time.sleep(1.1)
    
    # Should be ready again
    assert scan_trigger.get_time_until_ready() == 0.0


def test_trigger_with_callback_error(scan_trigger):
    """Test that trigger handles callback errors gracefully."""
    def error_callback():
        raise ValueError("Test error")
    
    scan_trigger.set_scan_callback(error_callback)
    
    # Should not raise, but return False
    result = scan_trigger.trigger()
    assert result is False


def test_trigger_with_short_cooldown():
    """Test trigger with very short cooldown."""
    config = ScanTriggerConfig(cooldown_ms=10)
    trigger = ScanTrigger(config=config)
    
    callback = Mock()
    trigger.set_scan_callback(callback)
    
    # First trigger
    trigger.trigger()
    assert callback.call_count == 1
    
    # Wait for short cooldown
    time.sleep(0.02)  # 20ms
    
    # Second trigger should succeed
    trigger.trigger()
    assert callback.call_count == 2


def test_trigger_with_zero_cooldown():
    """Test trigger with zero cooldown."""
    config = ScanTriggerConfig(cooldown_ms=0)
    trigger = ScanTrigger(config=config)
    
    callback = Mock()
    trigger.set_scan_callback(callback)
    
    # Multiple triggers should all succeed
    for i in range(5):
        result = trigger.trigger()
        assert result is True
    
    assert callback.call_count == 5
