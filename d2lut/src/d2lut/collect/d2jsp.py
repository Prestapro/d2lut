"""D2Jsp Forum Collector."""

from __future__ import annotations

import asyncio
import atexit
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, Any
from datetime import datetime

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
    """Collector for d2jsp forum posts.

    Supports two modes:
    - Live mode (use_live_collector=True): Uses Playwright for JS-rendered pages
    - Static mode (use_live_collector=False): Uses requests for basic HTML parsing
    """

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
            yield from self._fetch_via_static()

    def _fetch_via_static(self) -> Iterable[MarketPost]:
        """Fetch posts using requests-based static scraper.

        This method provides basic functionality without Playwright.
        It can parse simple HTML responses but may miss JS-rendered content.
        """
        try:
            import requests
        except ImportError:
            logger.error(
                "Static mode requires 'requests'. Install with: pip install requests"
            )
            logger.info("Or use live mode: pip install d2lut[scraper]")
            return

        forum_url = f"https://forums.d2jsp.org/forum.php?f={self.forum_id}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        try:
            logger.info(f"Fetching forum page: {forum_url}")
            response = requests.get(forum_url, headers=headers, timeout=30)
            response.raise_for_status()

            # Extract topic links from HTML
            topic_pattern = re.compile(r'topic\.php\?t=(\d+)', re.I)
            topic_ids = set(topic_pattern.findall(response.text))

            logger.info(f"Found {len(topic_ids)} topics in forum listing")

            # Fetch first few topics
            for topic_id in list(topic_ids)[:10]:
                try:
                    post = self._fetch_topic_static(int(topic_id), headers)
                    if post:
                        yield post
                except Exception as e:
                    logger.debug(f"Error fetching topic {topic_id}: {e}")
                    continue

        except requests.RequestException as e:
            logger.error(f"Failed to fetch forum page: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error in static fetch: {e}")

    def _fetch_topic_static(
        self, topic_id: int, headers: dict[str, str]
    ) -> MarketPost | None:
        """Fetch and parse a single topic page.

        Args:
            topic_id: Topic ID to fetch
            headers: HTTP headers for the request

        Returns:
            MarketPost or None if parsing fails
        """
        import requests

        url = f"https://forums.d2jsp.org/topic.php?t={topic_id}"

        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            # Extract basic info from HTML
            title_match = re.search(r'<title>([^<]+)</title>', response.text, re.I)
            title = title_match.group(1).strip() if title_match else f"Topic {topic_id}"

            # Extract post content (simplified - first post)
            # Look for post content divs
            content_match = re.search(
                r'<div[^>]*class="[^"]*post[^"]*"[^>]*>(.*?)</div>',
                response.text,
                re.I | re.DOTALL
            )
            body_text = ""
            if content_match:
                # Strip HTML tags
                body_text = re.sub(r'<[^>]+>', ' ', content_match.group(1))
                body_text = re.sub(r'\s+', ' ', body_text).strip()[:1000]

            return MarketPost(
                post_id=topic_id,
                title=title,
                body_text=body_text,
                author="unknown",
                timestamp=datetime.now(),
                url=url,
                source="d2jsp_static",
                forum_id=self.forum_id,
                thread_id=topic_id,
            )

        except requests.RequestException as e:
            logger.debug(f"Failed to fetch topic {topic_id}: {e}")
            return None

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
