"""Manual scan trigger interface for stash scanning.

Provides a simple interface for triggering stash scans manually,
with support for hotkey binding and button-based triggers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any
import threading
import time


@dataclass
class ScanTriggerConfig:
    """Configuration for scan trigger."""
    hotkey: str | None = None  # e.g., "ctrl+shift+s"
    enabled: bool = True
    cooldown_ms: int = 1000  # Minimum time between scans


class ScanTrigger:
    """
    Manual scan trigger for initiating stash scans.
    
    Provides a simple interface for triggering scans via:
    - Manual trigger() method call
    - Hotkey binding (future enhancement)
    - Button/UI integration
    """
    
    def __init__(self, config: ScanTriggerConfig | None = None):
        """
        Initialize the scan trigger.
        
        Args:
            config: Trigger configuration (hotkey, cooldown, etc.)
        """
        self.config = config or ScanTriggerConfig()
        
        # Callback to execute when scan is triggered
        self._scan_callback: Callable[[], Any] | None = None
        
        # Cooldown tracking
        self._last_trigger_time: float = 0.0
        self._trigger_lock = threading.Lock()
    
    def set_scan_callback(self, callback: Callable[[], Any]) -> None:
        """
        Set the callback function to execute when scan is triggered.
        
        Args:
            callback: Function to call when scan is triggered
        """
        self._scan_callback = callback
    
    def trigger(self) -> bool:
        """
        Manually trigger a scan.
        
        Returns:
            True if scan was triggered, False if cooldown prevented trigger
        """
        if not self.config.enabled:
            return False
        
        with self._trigger_lock:
            current_time = time.time() * 1000  # Convert to milliseconds
            time_since_last = current_time - self._last_trigger_time
            
            # Check cooldown
            if time_since_last < self.config.cooldown_ms:
                return False
            
            # Update last trigger time
            self._last_trigger_time = current_time
            
            # Execute callback if set
            if self._scan_callback:
                try:
                    self._scan_callback()
                    return True
                except Exception as e:
                    # Log error but don't crash
                    print(f"Error executing scan callback: {e}")
                    return False
            
            return True
    
    def enable(self) -> None:
        """Enable the scan trigger."""
        self.config.enabled = True
    
    def disable(self) -> None:
        """Disable the scan trigger."""
        self.config.enabled = False
    
    def is_enabled(self) -> bool:
        """Check if trigger is enabled."""
        return self.config.enabled
    
    def set_cooldown(self, cooldown_ms: int) -> None:
        """
        Set the cooldown period between scans.
        
        Args:
            cooldown_ms: Cooldown period in milliseconds
        """
        self.config.cooldown_ms = cooldown_ms
    
    def get_time_until_ready(self) -> float:
        """
        Get time until next scan can be triggered.
        
        Returns:
            Time in milliseconds until cooldown expires (0 if ready)
        """
        with self._trigger_lock:
            current_time = time.time() * 1000
            time_since_last = current_time - self._last_trigger_time
            remaining = self.config.cooldown_ms - time_since_last
            return max(0.0, remaining)
