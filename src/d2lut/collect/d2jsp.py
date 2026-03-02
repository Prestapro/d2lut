from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

from d2lut.models import MarketPost


@dataclass(slots=True)
class D2JspCollectorConfig:
    forum_id: int
    public_only: bool = True
    user_agent: str = "d2lut/0.2.3"
    use_live_collector: bool = True  # Use Playwright-based collector


class D2JspCollector:
    """Collector interface for d2jsp forum data.
    
    Supports two modes:
    - Live collection via Playwright (default)
    - Static HTML snapshot parsing (future)
    """

    def __init__(self, config: D2JspCollectorConfig) -> None:
        self.config = config

    def fetch_recent(self) -> Iterable[MarketPost]:
        """Fetch recent posts from d2jsp forum.
        
        If use_live_collector is True, uses Playwright-based LiveCollector.
        Otherwise returns empty iterator (for static snapshot mode).
        """
        if self.config.use_live_collector:
            return self._fetch_via_live_collector()
        return iter([])  # Empty iterator for static mode

    def _fetch_via_live_collector(self) -> Iterator[MarketPost]:
        """Use LiveCollector to fetch posts asynchronously."""
        try:
            from d2lut.collect.live_collector import LiveCollector, CollectorConfig
            
            config = CollectorConfig(forum_id=self.config.forum_id)
            collector = LiveCollector(config)
            
            # Run single scan synchronously
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if not loop.run_until_complete(collector.initialize()):
                return iter([])
            
            result = loop.run_until_complete(collector.scan_forum())
            
            # Convert PriceObservations to MarketPosts
            for obs in result.observations:
                yield MarketPost(
                    post_id=f"{obs.topic_id}_{obs.post_id}",
                    title=obs.item_name,
                    body=obs.raw_text,
                    author=obs.author,
                    timestamp=obs.timestamp.isoformat(),
                    url=f"https://forums.d2jsp.org/topic.php?t={obs.topic_id}",
                    category_id=obs.category_id,
                )
            
            loop.run_until_complete(collector.shutdown())
            
        except ImportError:
            # Playwright not installed, return empty
            return iter([])
        except Exception:
            return iter([])
