from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class MarketPost:
    source: str
    forum_id: int
    thread_id: int
    post_id: Optional[int]
    timestamp: datetime
    title: str
    body_text: str
    author: str
    url: str


@dataclass(slots=True)
class ObservedPrice:
    canonical_item_id: str
    variant_key: str
    ask_fg: Optional[float] = None
    bin_fg: Optional[float] = None
    sold_fg: Optional[float] = None
    confidence: float = 0.0
    source_url: str = ""
    thread_category_id: Optional[int] = None


@dataclass(slots=True)
class PriceEstimate:
    variant_key: str
    estimate_fg: float
    range_low_fg: float
    range_high_fg: float
    confidence: str
    sample_count: int
    last_updated: datetime
    demand_score: Optional[float] = None  # 0.0-1.0
    observed_velocity: Optional[float] = None  # observations per day

