"""Tests for the memory monitor module."""

import sys

import pytest

from d2lut.overlay.memory_monitor import (
    ComponentMemoryStats,
    MemoryMonitor,
    MemoryReport,
    estimate_object_size,
)


# -- ComponentMemoryStats ---------------------------------------------------

class TestComponentMemoryStats:
    def test_mb_conversion(self):
        cs = ComponentMemoryStats(name="test", bytes_used=1024 * 1024)
        assert cs.mb_used == pytest.approx(1.0)

    def test_zero_bytes(self):
        cs = ComponentMemoryStats(name="empty", bytes_used=0)
        assert cs.mb_used == 0.0


# -- MemoryReport -----------------------------------------------------------

class TestMemoryReport:
    def test_within_budget(self):
        report = MemoryReport(
            components=[], total_bytes=100, limit_bytes=500,
        )
        assert report.within_budget is True

    def test_over_budget(self):
        report = MemoryReport(
            components=[], total_bytes=600, limit_bytes=500,
        )
        assert report.within_budget is False

    def test_usage_pct(self):
        report = MemoryReport(
            components=[], total_bytes=250, limit_bytes=1000,
        )
        assert report.usage_pct == pytest.approx(25.0)

    def test_zero_limit(self):
        report = MemoryReport(
            components=[], total_bytes=100, limit_bytes=0,
        )
        assert report.usage_pct == 0.0


# -- MemoryMonitor ----------------------------------------------------------

class TestMemoryMonitor:
    def test_default_limit(self):
        mon = MemoryMonitor()
        assert mon.memory_limit_mb == pytest.approx(500.0)

    def test_custom_limit(self):
        mon = MemoryMonitor(memory_limit_mb=128.0)
        assert mon.memory_limit_mb == pytest.approx(128.0)

    def test_set_limit(self):
        mon = MemoryMonitor()
        mon.memory_limit_mb = 256.0
        assert mon.memory_limit_mb == pytest.approx(256.0)

    def test_empty_stats(self):
        mon = MemoryMonitor()
        report = mon.get_memory_stats()
        assert report.total_bytes == 0
        assert report.within_budget is True
        assert report.components == []

    def test_register_and_stats(self):
        mon = MemoryMonitor(memory_limit_mb=1.0)
        mon.register(
            "cache_a",
            estimator=lambda: ComponentMemoryStats(
                name="cache_a", bytes_used=1024,
            ),
        )
        report = mon.get_memory_stats()
        assert len(report.components) == 1
        assert report.components[0].name == "cache_a"
        assert report.total_bytes == 1024

    def test_multiple_components(self):
        mon = MemoryMonitor()
        mon.register(
            "a",
            estimator=lambda: ComponentMemoryStats(name="a", bytes_used=100),
        )
        mon.register(
            "b",
            estimator=lambda: ComponentMemoryStats(name="b", bytes_used=200),
        )
        report = mon.get_memory_stats()
        assert report.total_bytes == 300
        assert len(report.components) == 2

    def test_unregister(self):
        mon = MemoryMonitor()
        mon.register(
            "x",
            estimator=lambda: ComponentMemoryStats(name="x", bytes_used=50),
        )
        mon.unregister("x")
        report = mon.get_memory_stats()
        assert report.total_bytes == 0

    def test_is_within_budget(self):
        mon = MemoryMonitor(memory_limit_mb=0.001)  # ~1 KB
        mon.register(
            "small",
            estimator=lambda: ComponentMemoryStats(name="small", bytes_used=500),
        )
        assert mon.is_within_budget() is True

    def test_is_over_budget(self):
        mon = MemoryMonitor(memory_limit_mb=0.001)  # ~1048 bytes
        mon.register(
            "big",
            estimator=lambda: ComponentMemoryStats(name="big", bytes_used=2000),
        )
        assert mon.is_within_budget() is False

    def test_check_and_evict_within_budget(self):
        """No eviction when within budget."""
        evicted = []
        mon = MemoryMonitor(memory_limit_mb=1.0)
        mon.register(
            "c",
            estimator=lambda: ComponentMemoryStats(name="c", bytes_used=100),
            evictor=lambda: evicted.append("c"),
        )
        report = mon.check_and_evict()
        assert report.within_budget is True
        assert evicted == []

    def test_check_and_evict_triggers(self):
        """Eviction fires when over budget."""
        state = {"size": 2000}

        def estimator():
            return ComponentMemoryStats(name="big", bytes_used=state["size"])

        def evictor():
            state["size"] = 0  # simulate freeing memory

        mon = MemoryMonitor(memory_limit_mb=0.001)  # ~1 KB limit
        mon.register("big", estimator=estimator, evictor=evictor)

        report = mon.check_and_evict()
        assert report.within_budget is True
        assert state["size"] == 0

    def test_eviction_order_largest_first(self):
        """Largest component is evicted first."""
        order = []

        def make(name, size_holder):
            return (
                lambda: ComponentMemoryStats(name=name, bytes_used=size_holder[0]),
                lambda: (order.append(name), size_holder.__setitem__(0, 0)),
            )

        small_size = [100]
        big_size = [5000]
        est_s, evict_s = make("small", small_size)
        est_b, evict_b = make("big", big_size)

        mon = MemoryMonitor(memory_limit_mb=0.001)
        mon.register("small", estimator=est_s, evictor=evict_s)
        mon.register("big", estimator=est_b, evictor=evict_b)

        mon.check_and_evict()
        # "big" should be evicted first
        assert order[0] == "big"

    def test_estimator_exception_handled(self):
        """A broken estimator doesn't crash the monitor."""
        def bad_estimator():
            raise RuntimeError("boom")

        mon = MemoryMonitor()
        mon.register("broken", estimator=bad_estimator)
        report = mon.get_memory_stats()
        assert len(report.components) == 1
        assert report.components[0].bytes_used == 0


# -- estimate_object_size ---------------------------------------------------

class TestEstimateObjectSize:
    def test_string(self):
        size = estimate_object_size("hello")
        assert size >= sys.getsizeof("hello")

    def test_dict(self):
        d = {"a": 1, "b": "two"}
        size = estimate_object_size(d)
        assert size > sys.getsizeof(d)  # includes keys + values

    def test_list(self):
        lst = [1, 2, 3, "four"]
        size = estimate_object_size(lst)
        assert size > sys.getsizeof(lst)

    def test_bytes(self):
        b = b"\x00" * 1024
        size = estimate_object_size(b)
        assert size >= 1024

    def test_circular_reference(self):
        """Should not infinite-loop on circular refs."""
        a: dict = {}
        a["self"] = a
        size = estimate_object_size(a)
        assert size > 0

    def test_none(self):
        size = estimate_object_size(None)
        assert size >= 0
