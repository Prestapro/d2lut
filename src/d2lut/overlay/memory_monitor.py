"""Memory monitoring and budget enforcement for the overlay system.

Tracks approximate memory usage of key caches and data structures,
provides per-component breakdowns, and triggers eviction when the
configurable budget is exceeded.

Requirements: 12.5, Performance Constraints (≤500MB)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MemoryTracked(Protocol):
    """Protocol for components that report their memory usage."""

    def estimate_memory_bytes(self) -> int:
        """Return approximate memory usage in bytes."""
        ...


@dataclass(slots=True)
class ComponentMemoryStats:
    """Memory stats for a single tracked component."""

    name: str
    bytes_used: int
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def mb_used(self) -> float:
        return self.bytes_used / (1024 * 1024)


@dataclass(slots=True)
class MemoryReport:
    """Aggregate memory report across all tracked components."""

    components: list[ComponentMemoryStats]
    total_bytes: int
    limit_bytes: int

    @property
    def total_mb(self) -> float:
        return self.total_bytes / (1024 * 1024)

    @property
    def limit_mb(self) -> float:
        return self.limit_bytes / (1024 * 1024)

    @property
    def usage_pct(self) -> float:
        if self.limit_bytes <= 0:
            return 0.0
        return (self.total_bytes / self.limit_bytes) * 100.0

    @property
    def within_budget(self) -> bool:
        return self.total_bytes <= self.limit_bytes


class MemoryMonitor:
    """Monitors memory usage of registered overlay components.

    Components are registered by name with a callable that returns
    ``ComponentMemoryStats``.  The monitor aggregates stats and can
    trigger eviction callbacks when the budget is exceeded.
    """

    def __init__(self, memory_limit_mb: float = 500.0) -> None:
        self._limit_bytes = int(memory_limit_mb * 1024 * 1024)
        self._components: dict[str, _ComponentEntry] = {}

    # -- registration --------------------------------------------------------

    def register(
        self,
        name: str,
        estimator: callable,
        evictor: callable | None = None,
    ) -> None:
        """Register a component for memory tracking.

        Args:
            name: Human-readable component name.
            estimator: Callable returning ``ComponentMemoryStats``.
            evictor: Optional callable invoked to free memory when over budget.
        """
        self._components[name] = _ComponentEntry(
            name=name, estimator=estimator, evictor=evictor,
        )

    def unregister(self, name: str) -> None:
        self._components.pop(name, None)

    # -- querying ------------------------------------------------------------

    def get_memory_stats(self) -> MemoryReport:
        """Collect stats from all registered components."""
        stats: list[ComponentMemoryStats] = []
        total = 0
        for entry in self._components.values():
            try:
                cs = entry.estimator()
                stats.append(cs)
                total += cs.bytes_used
            except Exception:
                stats.append(ComponentMemoryStats(name=entry.name, bytes_used=0))
        return MemoryReport(
            components=stats,
            total_bytes=total,
            limit_bytes=self._limit_bytes,
        )

    def is_within_budget(self) -> bool:
        """Quick check: are we under the memory limit?"""
        return self.get_memory_stats().within_budget

    # -- eviction ------------------------------------------------------------

    def check_and_evict(self) -> MemoryReport:
        """If over budget, invoke evictors (largest first) until within budget.

        Returns the final ``MemoryReport`` after any evictions.
        """
        report = self.get_memory_stats()
        if report.within_budget:
            return report

        # Sort components by bytes_used descending so we evict the biggest first
        evictable = sorted(
            ((name, entry) for name, entry in self._components.items() if entry.evictor),
            key=lambda pair: _find_bytes(pair[0], report),
            reverse=True,
        )

        for _name, entry in evictable:
            try:
                entry.evictor()
            except Exception:
                pass
            report = self.get_memory_stats()
            if report.within_budget:
                break

        return report

    # -- config --------------------------------------------------------------

    @property
    def memory_limit_mb(self) -> float:
        return self._limit_bytes / (1024 * 1024)

    @memory_limit_mb.setter
    def memory_limit_mb(self, value: float) -> None:
        self._limit_bytes = int(value * 1024 * 1024)


# -- helpers -----------------------------------------------------------------

@dataclass(slots=True)
class _ComponentEntry:
    name: str
    estimator: callable
    evictor: callable | None


def _find_bytes(name: str, report: MemoryReport) -> int:
    for c in report.components:
        if c.name == name:
            return c.bytes_used
    return 0


# -- size estimation utilities -----------------------------------------------

def estimate_object_size(obj: Any, seen: set | None = None) -> int:
    """Rough recursive size estimate for common Python objects.

    Not perfectly accurate but good enough for cache budgeting.
    Handles dicts, lists, tuples, sets, strings, bytes, dataclasses,
    and OrderedDicts.
    """
    if seen is None:
        seen = set()

    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)

    size = sys.getsizeof(obj)

    if isinstance(obj, dict):
        for k, v in obj.items():
            size += estimate_object_size(k, seen)
            size += estimate_object_size(v, seen)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for item in obj:
            size += estimate_object_size(item, seen)
    elif hasattr(obj, "__dict__"):
        size += estimate_object_size(obj.__dict__, seen)
    elif hasattr(obj, "__slots__"):
        for slot in obj.__slots__:
            try:
                size += estimate_object_size(getattr(obj, slot), seen)
            except AttributeError:
                pass

    return size
