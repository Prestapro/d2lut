"""Tests for frame_throttle module: FrameRateThrottle and DirtyFrameDetector."""

import time
import pytest

from d2lut.overlay.frame_throttle import (
    FrameRateThrottle,
    FrameStats,
    DirtyFrameDetector,
)


# ---------------------------------------------------------------------------
# FrameRateThrottle
# ---------------------------------------------------------------------------

class TestFrameRateThrottle:
    def test_init_defaults(self):
        t = FrameRateThrottle()
        assert t.target_fps == 60.0
        assert t.frame_count == 0
        assert t.actual_fps == 0.0

    def test_init_custom_fps(self):
        t = FrameRateThrottle(target_fps=30.0)
        assert t.target_fps == 30.0
        assert t.frame_budget_ms == pytest.approx(1000.0 / 30.0, abs=0.1)

    def test_invalid_fps_raises(self):
        with pytest.raises(ValueError):
            FrameRateThrottle(target_fps=0)
        with pytest.raises(ValueError):
            FrameRateThrottle(target_fps=-10)

    def test_set_target_fps(self):
        t = FrameRateThrottle(target_fps=30.0)
        t.target_fps = 60.0
        assert t.target_fps == 60.0
        assert t.frame_budget_ms == pytest.approx(1000.0 / 60.0, abs=0.1)

    def test_set_target_fps_invalid(self):
        t = FrameRateThrottle()
        with pytest.raises(ValueError):
            t.target_fps = 0

    def test_frame_budget_ms(self):
        t = FrameRateThrottle(target_fps=60.0)
        assert t.frame_budget_ms == pytest.approx(1000.0 / 60.0, abs=0.1)

    def test_begin_wait_increments_count(self):
        t = FrameRateThrottle(target_fps=1000.0)  # fast target so test is quick
        t.begin_frame()
        t.wait()
        assert t.frame_count == 1
        t.begin_frame()
        t.wait()
        assert t.frame_count == 2

    def test_actual_fps_after_frames(self):
        t = FrameRateThrottle(target_fps=1000.0)
        for _ in range(5):
            t.begin_frame()
            t.wait()
        # With a 1000 FPS target the actual FPS should be high (>100)
        assert t.actual_fps > 0

    def test_stats_returns_frame_stats(self):
        t = FrameRateThrottle(target_fps=60.0)
        t.begin_frame()
        t.wait()
        s = t.stats()
        assert isinstance(s, FrameStats)
        assert s.target_fps == 60.0
        assert s.frame_count == 1
        assert s.frame_budget_ms == pytest.approx(1000.0 / 60.0, abs=0.1)
        assert s.frame_time_ms >= 0
        assert s.budget_remaining_ms >= 0

    def test_reset_clears_state(self):
        t = FrameRateThrottle(target_fps=1000.0)
        for _ in range(3):
            t.begin_frame()
            t.wait()
        assert t.frame_count == 3
        t.reset()
        assert t.frame_count == 0
        assert t.actual_fps == 0.0

    def test_throttle_actually_sleeps(self):
        """A low target FPS should cause measurable sleep time."""
        t = FrameRateThrottle(target_fps=20.0)  # 50 ms budget
        t.begin_frame()
        start = time.monotonic()
        t.wait()
        elapsed_ms = (time.monotonic() - start) * 1000
        # Should have slept roughly 50 ms (allow generous tolerance)
        assert elapsed_ms >= 30, f"Expected >=30ms sleep, got {elapsed_ms:.1f}ms"


# ---------------------------------------------------------------------------
# DirtyFrameDetector
# ---------------------------------------------------------------------------

class TestDirtyFrameDetector:
    def test_initial_state_not_dirty(self):
        d = DirtyFrameDetector(debounce_ms=0)
        assert d.needs_render() is False

    def test_force_dirty(self):
        d = DirtyFrameDetector(debounce_ms=0)
        d.force_dirty()
        assert d.needs_render() is True
        # Second call should be clean
        assert d.needs_render() is False

    def test_hover_change_marks_dirty(self):
        d = DirtyFrameDetector(debounce_ms=0)
        d.mark_hover_change(True, (10, 20, 100, 50))
        assert d.needs_render() is True

    def test_same_hover_not_dirty(self):
        d = DirtyFrameDetector(debounce_ms=0)
        d.mark_hover_change(True, (10, 20, 100, 50))
        d.needs_render()  # consume
        d.mark_hover_change(True, (10, 20, 100, 50))
        assert d.needs_render() is False

    def test_hover_end_marks_dirty(self):
        d = DirtyFrameDetector(debounce_ms=0)
        d.mark_hover_change(True, (10, 20, 100, 50))
        d.needs_render()  # consume
        d.mark_hover_change(False, None)
        assert d.needs_render() is True

    def test_screenshot_change_marks_dirty(self):
        d = DirtyFrameDetector(debounce_ms=0)
        d.mark_screenshot(1.0)
        assert d.needs_render() is True

    def test_same_screenshot_not_dirty(self):
        d = DirtyFrameDetector(debounce_ms=0)
        d.mark_screenshot(1.0)
        d.needs_render()  # consume
        d.mark_screenshot(1.0)
        assert d.needs_render() is False

    def test_data_update_marks_dirty(self):
        d = DirtyFrameDetector(debounce_ms=0)
        d.mark_data_update()
        assert d.needs_render() is True

    def test_debounce_delays_render(self):
        d = DirtyFrameDetector(debounce_ms=100)
        d.mark_hover_change(True, (1, 2, 3, 4))
        # Immediately after marking, debounce hasn't elapsed
        assert d.needs_render() is False
        time.sleep(0.12)
        assert d.needs_render() is True

    def test_reset_clears_state(self):
        d = DirtyFrameDetector(debounce_ms=0)
        d.mark_hover_change(True, (1, 2, 3, 4))
        d.reset()
        assert d.needs_render() is False


# ---------------------------------------------------------------------------
# Integration: throttle + dirty detector together
# ---------------------------------------------------------------------------

class TestThrottleDirtyIntegration:
    def test_skip_render_when_clean(self):
        """Simulates the overlay loop: no render when nothing changed."""
        throttle = FrameRateThrottle(target_fps=1000.0)
        dirty = DirtyFrameDetector(debounce_ms=0)
        renders = 0

        for i in range(5):
            throttle.begin_frame()
            if dirty.needs_render():
                renders += 1
            throttle.wait()

        assert renders == 0

    def test_render_on_hover_change(self):
        throttle = FrameRateThrottle(target_fps=1000.0)
        dirty = DirtyFrameDetector(debounce_ms=0)
        renders = 0

        dirty.mark_hover_change(True, (10, 20, 30, 40))
        for _ in range(3):
            throttle.begin_frame()
            if dirty.needs_render():
                renders += 1
            throttle.wait()

        # Only the first frame should render
        assert renders == 1
