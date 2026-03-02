"""D2Jsp Forum Collector."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Iterable

from ..models import MarketPost, PriceObservation

logger = logging.getLogger(__name__)

# Global executor for async fallback
_executor = ThreadPoolExecutor(max_workers=1)


class D2JspCollector:
    """Collector for d2jsp forum posts."""
    
    def __init__(self, forum_id: int = 271, use_live_collector: bool = False):
        self.forum_id = forum_id
        self.use_live_collector = use_live_collector
    
    def fetch_recent(self) -> Iterable[MarketPost]:
        """Fetch recent posts from d2jsp forum.
        
        Yields:
            MarketPost: Parsed forum posts
        """
        if self.use_live_collector:
            yield from self._fetch_via_live_collector()
        else:
            # Static snapshot mode - return empty iterator
            logger.info("Static snapshot mode - no live collection")
            return
    
    def _fetch_via_live_collector(self) -> Iterable[MarketPost]:
        """Fetch posts using Playwright-based live collector."""
        try:
            from .live_collector import LiveCollector, CollectorConfig
            
            config = CollectorConfig(forum_id=self.forum_id)
            collector = LiveCollector(config)
            
            # Handle async context properly
            try:
                # Check if we're in an async context
                loop = asyncio.get_running_loop()
                # We're in async context - use thread pool
                logger.debug("Running in async context, using thread pool")
                future = _executor.submit(
                    lambda: asyncio.run(collector.initialize())
                )
                future.result(timeout=30)
                
                future = _executor.submit(
                    lambda: asyncio.run(collector.scan_forum())
                )
                result = future.result(timeout=120)
            except RuntimeError:
                # No running loop - safe to use asyncio.run
                logger.debug("No async context, using asyncio.run")
                asyncio.run(collector.initialize())
                result = asyncio.run(collector.scan_forum())
            
            if result and hasattr(result, 'observations'):
                for obs in result.observations:
                    post = self._observation_to_post(obs)
                    if post:
                        yield post
            else:
                logger.warning("No observations collected")
                
        except ImportError as e:
            logger.error(f"Live collector dependencies not installed: {e}")
            logger.info("Install with: pip install d2lut[scraper]")
        except Exception as e:
            logger.exception(f"Error during live collection: {e}")
    
    def _observation_to_post(self, obs: PriceObservation) -> MarketPost | None:
        """Convert PriceObservation to MarketPost.
        
        Args:
            obs: PriceObservation from live collector
            
        Returns:
            MarketPost or None if conversion fails
        """
        try:
            return MarketPost(
                post_id=obs.post_id,
                title=obs.item_name,
                body_text=obs.raw_text,
                author=obs.author,
                timestamp=obs.timestamp,
                url=f"https://forums.d2jsp.org/topic.php?t={obs.topic_id}",
                source="d2jsp",
                forum_id=self.forum_id,
                thread_id=obs.topic_id,
                thread_category_id=obs.category_id,
            )
        except Exception as e:
            logger.error(f"Failed to convert observation to post: {e}")
            return None
