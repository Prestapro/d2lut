"""D2Jsp Forum Collector."""

from __future__ import annotations

import asyncio
import atexit
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

from ..models import MarketPost, PriceObservation

logger = logging.getLogger(__name__)

# Module-level executor with proper cleanup
_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    """Get or create the thread pool executor."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=1)
        atexit.register(_shutdown_executor)
    return _executor


def _shutdown_executor() -> None:
    """Shutdown the thread pool executor on exit."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False)
        _executor = None


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

            # Run the async collector in a single event loop
            # This ensures Playwright browser instance persists across calls
            async def run_collector() -> list[PriceObservation]:
                """Run the full collection cycle in one async context."""
                observations = []
                async with LiveCollector(config) as collector:
                    result = await collector.scan_forum()
                    if result and hasattr(result, "observations"):
                        observations = result.observations
                return observations

            # Check if we're already in an async context
            try:
                asyncio.get_running_loop()  # Raises RuntimeError if no loop
                # We're in async context - run in thread pool with new loop
                logger.debug("Running in async context, using thread pool")
                executor = _get_executor()
                future = executor.submit(lambda: asyncio.run(run_collector()))
                observations = future.result(timeout=180)
            except RuntimeError:
                # No running loop - safe to use asyncio.run directly
                logger.debug("No async context, using asyncio.run")
                observations = asyncio.run(run_collector())

            # Convert observations to posts
            for obs in observations:
                post = self._observation_to_post(obs)
                if post:
                    yield post

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
