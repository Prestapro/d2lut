from __future__ import annotations

from typing import Iterable

from d2lut.models import MarketPost, ObservedPrice


class MarketParser:
    """Parse forum posts into normalized item price observations."""

    def parse_posts(self, posts: Iterable[MarketPost]) -> list[ObservedPrice]:
        # Phase 1 target: obvious `bin X fg` / `iso` patterns for runes/uniques/bases.
        raise NotImplementedError("Parser not implemented yet")

