from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from d2lut.models import MarketPost


@dataclass(slots=True)
class D2JspCollectorConfig:
    forum_id: int
    public_only: bool = True
    user_agent: str = "d2lut/0.1"


class D2JspCollector:
    """Collector interface for d2jsp forum data.

    Implementation intentionally left as a stub:
    - start with public pages only
    - keep HTML snapshots for parser regression tests
    - avoid storing credentials in code or config files
    """

    def __init__(self, config: D2JspCollectorConfig) -> None:
        self.config = config

    def fetch_recent(self) -> Iterable[MarketPost]:
        raise NotImplementedError("Collector not implemented yet")

