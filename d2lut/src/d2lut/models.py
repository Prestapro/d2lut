"""Data models for d2lut."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class MarketPost:
    """A parsed post from d2jsp marketplace."""
    post_id: int | None = None
    title: str = ""
    body_text: str = ""
    author: str = ""
    timestamp: datetime | None = None
    url: str = ""
    source: str = "d2jsp"
    forum_id: int = 0
    thread_id: int = 0
    thread_category_id: int | None = None


@dataclass(slots=True)
class ObservedPrice:
    """A price observation extracted from a post."""
    canonical_item_id: str
    variant_key: str
    price_fg: float
    signal_kind: str = "bin"  # bin, sold, ask, co
    confidence: float = 0.0
    source: str = "d2jsp"
    market_key: str = "d2r_sc_ladder"
    forum_id: int = 0
    thread_id: int = 0
    post_id: int = 0
    observed_at: datetime | None = None
    thread_category_id: int | None = None
    raw_text: str = ""


@dataclass(slots=True)
class PriceEstimate:
    """Aggregated price estimate for an item."""
    variant_key: str
    fg: float
    confidence: str = "low"  # low, medium, high
    n_observations: int = 0
    last_updated: datetime | None = None
    price_range: tuple[float, float] = (0.0, 0.0)


@dataclass(slots=True)
class PriceObservation:
    """Price observation from live collector."""
    item_name: str
    price_fg: float
    topic_id: int
    post_id: int
    author: str
    timestamp: datetime
    category_id: int = 0
    raw_text: str = ""
    confidence: float = 0.0
