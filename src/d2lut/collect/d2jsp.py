from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Iterable, Iterator

from d2lut.models import MarketPost

logger = logging.getLogger(__name__)

# Thread pool for running async code from sync context
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="d2lut-collector")


@dataclass(slots=True)
class D2JspCollectorConfig:
    forum_id: int
    public_only: bool = True
    user_agent: str = "d2lut/0.2.8"
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
        logger.info("Static mode: returning empty iterator (not implemented)")
        return iter([])  # Empty iterator for static mode

    def _fetch_via_live_collector(self) -> Iterator[MarketPost]:
        """Use LiveCollector to fetch posts asynchronously."""
        try:
            from d2lut.collect.live_collector import LiveCollector, CollectorConfig
            
            config = CollectorConfig(forum_id=self.config.forum_id)
            collector = LiveCollector(config)
            
            async def _run_collection():
                if not await collector.initialize():
                    logger.warning("LiveCollector failed to initialize")
                    return []
                result = await collector.scan_forum()
                await collector.shutdown()
                logger.info("LiveCollector scan complete: %d observations", len(result.observations))
                return result.observations
            
            # Check if we're already in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context - run in thread pool to avoid "loop already running"
                logger.debug("Running collector in thread pool (async context detected)")
                observations = _executor.submit(
                    lambda: asyncio.run(_run_collection())
                ).result(timeout=120)
            except RuntimeError:
                # No running loop - safe to use asyncio.run()
                observations = asyncio.run(_run_collection())
            
            # Convert PriceObservations to MarketPosts with correct field mapping
            for obs in observations:
                yield MarketPost(
                    source="d2jsp",
                    forum_id=self.config.forum_id,
                    thread_id=obs.topic_id,
                    post_id=obs.post_id,
                    timestamp=obs.timestamp,  # datetime, not isoformat string!
                    title=obs.item_name,
                    body_text=obs.raw_text,  # body_text, not body!
                    author=obs.author,
                    url=f"https://forums.d2jsp.org/topic.php?t={obs.topic_id}",
                    thread_category_id=obs.category_id,  # Pass category_id for weighting
                )
            
        except ImportError as e:
            # Playwright not installed - log clearly
            logger.warning("Playwright not installed, cannot use live collector: %s", e)
            logger.info("Install with: pip install playwright && playwright install")
            return  # Just return - generator stops
        except Exception as e:
            # Log actual error instead of silently returning empty
            logger.error("LiveCollector failed: %s", e, exc_info=True)
            return  # Just return - generator stops
