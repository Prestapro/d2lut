"""Frame rate throttling and dirty-frame detection for overlay rendering.

Provides CPU-efficient frame pacing (sleep-based, not busy-wait) and
change-detection helpers so the overlay loop only re-renders when
something actually changed.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class FrameStats:
    """Snapshot of frame timing statistics."""
    target_fps: float
    actual_fps: float
    frame_budget_ms: float
    frame_time_ms: float
    budget_remaining_ms: float
    frame_count: int


class FrameRateThrottle:
    """Sleep-based frame-rate limiter with rolling FPS tracking.

    Instead of a tight ``time.sleep(0.001)`` busy-wait the caller does::

        throttle = FrameRateThrottle(target_fps=60)
        while running:
            do_work()
            throttle.wait()          # sleeps the right amount
            stats = throttle.stats() # actual FPS / budget info
    """

    def __init__(self, target_fps: float = 60.0, window_size: int = 60):
        if target_fps <= 0:
            raise ValueError("target_fps must be positive")
        self._target_fps = target_fps
        self._frame_budget = 1.0 / target_fps  # seconds
        self._window_size = max(1, window_size)

        # Rolling window of recent frame durations (seconds)
        self._frame_times: deque[float] = deque(maxlen=self._window_size)
        self._last_frame_start: float = 0.0
        self._last_frame_duration: float = 0.0
        self._frame_count: int = 0

    # -- public API ----------------------------------------------------------

    @property
    def target_fps(self) -> float:
        return self._target_fps

    @target_fps.setter
    def target_fps(self, value: float) -> None:
        if value <= 0:
            raise ValueError("target_fps must be positive")
        self._target_fps = value
        self._frame_budget = 1.0 / value

    @property
    def frame_budget_ms(self) -> float:
        """Per-frame time budget in milliseconds."""
        return self._frame_budget * 1000.0

    def begin_frame(self) -> None:
        """Mark the start of a new frame.  Call before doing work."""
        self._last_frame_start = time.monotonic()

    def wait(self) -> None:
        """Sleep until the frame budget is consumed, then record timing."""
        now = time.monotonic()
        elapsed = now - self._last_frame_start if self._last_frame_start else 0.0
        remaining = self._frame_budget - elapsed
        if remaining > 0.001:          # only sleep if > 1 ms remains
            time.sleep(remaining)
        elif remaining > 0:
            # Sub-millisecond remainder: yield once to avoid busy-spin
            time.sleep(0)

        end = time.monotonic()
        self._last_frame_duration = end - self._last_frame_start if self._last_frame_start else 0.0
        self._frame_times.append(self._last_frame_duration)
        self._frame_count += 1

    @property
    def actual_fps(self) -> float:
        """Rolling average FPS over the last *window_size* frames."""
        if not self._frame_times:
            return 0.0
        avg = sum(self._frame_times) / len(self._frame_times)
        return 1.0 / avg if avg > 0 else 0.0

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def stats(self) -> FrameStats:
        """Return a snapshot of current frame timing statistics."""
        ft_ms = self._last_frame_duration * 1000.0
        budget_ms = self.frame_budget_ms
        return FrameStats(
            target_fps=self._target_fps,
            actual_fps=self.actual_fps,
            frame_budget_ms=budget_ms,
            frame_time_ms=ft_ms,
            budget_remaining_ms=max(0.0, budget_ms - ft_ms),
            frame_count=self._frame_count,
        )

    def reset(self) -> None:
        """Reset all counters (e.g. after a pause/resume)."""
        self._frame_times.clear()
        self._last_frame_start = 0.0
        self._last_frame_duration = 0.0
        self._frame_count = 0


class DirtyFrameDetector:
    """Tracks whether the overlay actually needs to re-render.

    The update loop sets dirty flags via ``mark_*`` helpers.  The loop
    then checks ``needs_render()`` and skips the expensive OCR /
    identification / render path when nothing changed.
    """

    def __init__(self, debounce_ms: float = 50.0):
        self._dirty = False
        self._last_hover_coords: tuple[int, int, int, int] | None = None
        self._last_hover_is_active: bool = False
        self._last_screenshot_time: float = 0.0
        self._debounce_s = debounce_ms / 1000.0
        self._last_change_time: float = 0.0

    def mark_hover_change(
        self, is_hovering: bool, coords: tuple[int, int, int, int] | None
    ) -> None:
        """Call when hover state may have changed."""
        if is_hovering != self._last_hover_is_active or coords != self._last_hover_coords:
            self._dirty = True
            self._last_hover_is_active = is_hovering
            self._last_hover_coords = coords
            self._last_change_time = time.monotonic()

    def mark_screenshot(self, screenshot_time: float) -> None:
        """Call when a new screenshot has been captured."""
        if screenshot_time != self._last_screenshot_time:
            self._dirty = True
            self._last_screenshot_time = screenshot_time
            self._last_change_time = time.monotonic()

    def mark_data_update(self) -> None:
        """Call when external data changed (price refresh, config reload)."""
        self._dirty = True
        self._last_change_time = time.monotonic()

    def force_dirty(self) -> None:
        """Unconditionally mark the next frame as needing render."""
        self._dirty = True
        self._last_change_time = time.monotonic()

    def needs_render(self) -> bool:
        """Return True if the frame should be rendered, then clear the flag.

        Applies a small debounce so rapid hover jitter doesn't cause
        excessive re-renders.
        """
        if not self._dirty:
            return False
        now = time.monotonic()
        if now - self._last_change_time < self._debounce_s:
            return False  # wait for debounce window to pass
        self._dirty = False
        return True

    def reset(self) -> None:
        """Reset all tracking state."""
        self._dirty = False
        self._last_hover_coords = None
        self._last_hover_is_active = False
        self._last_screenshot_time = 0.0
        self._last_change_time = 0.0
