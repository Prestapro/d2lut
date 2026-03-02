"""Live Collector for D2JSP Forum.

Uses Playwright to scrape live price data from d2jsp.org forum.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

from ..models import PriceObservation
from ..patterns import find_items_in_text, find_best_price_in_text

logger = logging.getLogger(__name__)


@dataclass
class CollectorConfig:
    """Configuration for the live collector."""

    forum_id: int = 271  # D2R Ladder trading forum
    max_pages: int = 5
    timeout: int = 30
    headless: bool = True
    browser_type: str = "chromium"


@dataclass
class ScanResult:
    """Result of a forum scan."""

    observations: list[PriceObservation] = field(default_factory=list)
    pages_scanned: int = 0
    posts_processed: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class LiveCollector:
    """Playwright-based live collector for d2jsp forum.

    This collector uses Playwright to browse d2jsp forum pages and extract
    price observations from trading posts. It maintains a single browser
    instance throughout its lifecycle.

    Uses shared patterns from patterns.py for consistent item and price
    detection across the entire pipeline.
    """

    def __init__(self, config: CollectorConfig):
        self.config = config
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None

    async def initialize(self) -> None:
        """Initialize the Playwright browser.

        Must be called before scan_forum().
        """
        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()

            # Select browser type
            browser_launcher = getattr(self._playwright, self.config.browser_type)
            self._browser = await browser_launcher.launch(
                headless=self.config.headless
            )

            self._context = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

            self._page = await self._context.new_page()
            self._page.set_default_timeout(self.config.timeout * 1000)

            logger.info(
                f"LiveCollector initialized with {self.config.browser_type}"
            )

        except ImportError:
            logger.error(
                "Playwright not installed. Install with: pip install playwright"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to initialize LiveCollector: {e}")
            raise

    async def scan_forum(self) -> ScanResult:
        """Scan the forum and collect price observations.

        Returns:
            ScanResult with all collected observations
        """
        result = ScanResult(started_at=datetime.now())

        if not self._page:
            result.errors.append("Collector not initialized - call initialize() first")
            return result

        base_url = f"https://forums.d2jsp.org/forum.php?f={self.config.forum_id}"

        try:
            for page_num in range(self.config.max_pages):
                try:
                    # Navigate to forum page
                    url = base_url if page_num == 0 else f"{base_url}&p={page_num + 1}"
                    await self._page.goto(url, wait_until="networkidle")

                    # Extract topic links
                    topic_links = await self._extract_topic_links()

                    for topic_url in topic_links[:20]:  # Limit topics per page
                        try:
                            observations = await self._scan_topic(topic_url)
                            result.observations.extend(observations)
                            result.posts_processed += len(observations)
                        except Exception as e:
                            logger.debug(f"Error scanning topic: {e}")
                            continue

                    result.pages_scanned += 1

                except Exception as e:
                    result.errors.append(f"Error on page {page_num + 1}: {str(e)}")
                    continue

        except Exception as e:
            result.errors.append(f"Scan failed: {str(e)}")
            logger.exception("Forum scan failed")

        result.finished_at = datetime.now()
        logger.info(
            f"Scan complete: {len(result.observations)} observations, "
            f"{result.pages_scanned} pages, {len(result.errors)} errors"
        )

        return result

    async def _extract_topic_links(self) -> list[str]:
        """Extract topic links from the current forum page."""
        links = []

        try:
            # Wait for topic list to load
            await self._page.wait_for_selector('a[href*="topic.php"]', timeout=5000)

            # Find all topic links
            elements = await self._page.query_selector_all('a[href*="topic.php"]')

            for elem in elements[:30]:  # Limit links
                href = await elem.get_attribute("href")
                if href and "topic.php" in href:
                    # Build full URL
                    if href.startswith("/"):
                        href = f"https://forums.d2jsp.org{href}"
                    elif not href.startswith("http"):
                        href = f"https://forums.d2jsp.org/{href}"
                    links.append(href)

        except Exception as e:
            logger.debug(f"Error extracting topic links: {e}")

        return links

    async def _scan_topic(self, url: str) -> list[PriceObservation]:
        """Scan a single topic for price observations.

        Args:
            url: Topic URL to scan

        Returns:
            List of PriceObservation objects (empty list on error)
        """
        try:
            await self._page.goto(url, wait_until="networkidle", timeout=15000)

            # Extract topic ID from URL
            topic_id = 0
            match = re.search(r"t=(\d+)", url)
            if match:
                topic_id = int(match.group(1))

            # Get page content and parse
            content = await self._page.content()
            return self._parse_topic_content(content, topic_id)

        except TimeoutError:
            logger.debug(f"Timeout scanning topic {url}")
            return []
        except Exception as e:
            logger.debug(f"Error scanning topic {url}: {type(e).__name__}: {e}")
            return []

    def _parse_topic_content(
        self, content: str, topic_id: int
    ) -> list[PriceObservation]:
        """Parse topic HTML content for price observations.

        Uses shared patterns from patterns.py for consistent detection.

        Args:
            content: HTML content of the topic page
            topic_id: Topic ID for observations

        Returns:
            List of PriceObservation objects
        """
        # Find items using shared patterns (now includes 100+ items!)
        items_found = find_items_in_text(content)

        if not items_found:
            return []

        # Find best price using shared patterns
        price_info = find_best_price_in_text(content)

        if not price_info:
            return []

        # Create observations
        observations: list[PriceObservation] = []
        for variant_key in items_found[:5]:  # Limit items per topic
            obs = PriceObservation(
                item_name=variant_key.split(":")[-1],
                price_fg=price_info["price"],
                topic_id=topic_id,
                post_id=0,
                author="unknown",
                timestamp=datetime.now(),
                raw_text=content[:500],
                confidence=price_info["confidence"],
            )
            observations.append(obs)

        return observations

    async def close(self) -> None:
        """Close the browser and cleanup resources."""
        try:
            if self._page:
                await self._page.close()
                self._page = None

            if self._context:
                await self._context.close()
                self._context = None

            if self._browser:
                await self._browser.close()
                self._browser = None

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

            logger.info("LiveCollector closed")

        except Exception as e:
            logger.error(f"Error closing LiveCollector: {e}")

    async def __aenter__(self) -> "LiveCollector":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
