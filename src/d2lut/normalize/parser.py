"""Market post parser for extracting price signals."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable

from ..models import MarketPost, ObservedPrice
from ..patterns import find_items_in_text, find_best_price_in_text

logger = logging.getLogger(__name__)


class MarketParser:
    """Parser for extracting price signals from forum posts."""

    def parse_posts(self, posts: Iterable[MarketPost]) -> list[ObservedPrice]:
        """Parse posts and extract price observations.

        Args:
            posts: Iterable of MarketPost objects

        Returns:
            List of ObservedPrice objects
        """
        observations = []

        for post in posts:
            try:
                post_obs = self._parse_single_post(post)
                observations.extend(post_obs)
            except Exception as e:
                logger.error(f"Error parsing post {post.post_id}: {e}")

        return observations

    def _parse_single_post(self, post: MarketPost) -> list[ObservedPrice]:
        """Parse a single post and extract observations.

        Args:
            post: MarketPost to parse

        Returns:
            List of ObservedPrice objects from this post
        """
        # Combine title and body text
        text = f"{post.title} {post.body_text}"

        # Find items using shared patterns
        items_found = find_items_in_text(text)

        if not items_found:
            return []

        # Find best price using shared patterns
        price_info = find_best_price_in_text(text)

        if not price_info:
            return []

        # Create observations for first 2 items (limit)
        observations = []
        for variant_key in items_found[:2]:
            obs = ObservedPrice(
                canonical_item_id=variant_key.split(":")[-1],
                variant_key=variant_key,
                price_fg=price_info["price"],
                signal_kind=price_info["signal_kind"],
                confidence=price_info["confidence"],
                forum_id=post.forum_id,
                thread_id=post.thread_id,
                post_id=post.post_id or 0,
                thread_category_id=post.thread_category_id,
                observed_at=post.timestamp or datetime.now(),
                raw_text=text[:500],
            )
            observations.append(obs)

        return observations
