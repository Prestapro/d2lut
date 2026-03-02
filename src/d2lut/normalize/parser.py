"""Market post parser for extracting price signals."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable

from ..models import MarketPost, ObservedPrice
from ..patterns import PRICE_PATTERNS, get_signal_confidence

logger = logging.getLogger(__name__)

# Item patterns for identification
_ITEM_PATTERNS = {
    # Runes
    "rune:jah": r"\bjah\b",
    "rune:ber": r"\bber\b",
    "rune:sur": r"\bsur\b",
    "rune:lo": r"\blo\s*(?:rune)?\b",
    "rune:ohm": r"\bohm\b",
    "rune:vex": r"\bvex\b",
    "rune:gul": r"\bgul\b",
    "rune:ist": r"\bist\b",
    "rune:mal": r"\bmal\s*(?:rune)?\b",
    "rune:um": r"\bum\s*(?:rune)?\b",
    "rune:ko": r"\bko\s*(?:rune)?\b",

    # Uniques
    "unique:shako": r"\bshako\b|\bharlequin\s*crest\b",
    "unique:arachnid": r"\barachnid\b|\bspider\s*web\s*belt\b",
    "unique:mara": r"\bmara'?s?\b|\bkaleidoscope\b",
    "unique:tyraels": r"\btyrael'?s?\s*might\b",

    # Runewords
    "runeword:enigma": r"\benigma\b",
    "runeword:infinity": r"\binfinity\b",
    "runeword:cta": r"\bcta\b|\bcall\s*to\s*arms\b",
    "runeword:grief": r"\bgrief\b",
    "runeword:fortitude": r"\bfortitude\b",
    "runeword:spirit": r"\bspirit\b",

    # Torches and Annis
    "unique:torch": r"\btorch\b|\bhellfire\s*torch\b",
    "unique:anni": r"\banni(?:hilus)?\b",
}

# Compile patterns at module load
_COMPILED_ITEM_PATTERNS = {
    key: __import__("re").compile(pattern, __import__("re").I)
    for key, pattern in _ITEM_PATTERNS.items()
}


class MarketParser:
    """Parser for extracting price signals from forum posts."""

    def __init__(self):
        self.item_patterns = _COMPILED_ITEM_PATTERNS
        self.price_patterns = PRICE_PATTERNS

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

        # Find items mentioned
        items_found = []
        for variant_key, pattern in self.item_patterns.items():
            if pattern.search(text):
                items_found.append(variant_key)

        if not items_found:
            return []

        # Find prices with signal kinds
        prices_found: list[dict] = []
        for pattern, signal_kind in self.price_patterns:
            for match in pattern.finditer(text):
                try:
                    price = float(match.group(1))
                    confidence = get_signal_confidence(signal_kind)
                    prices_found.append({
                        "price": price,
                        "confidence": confidence,
                        "signal_kind": signal_kind,
                    })
                except (ValueError, IndexError):
                    continue

        if not prices_found:
            return []

        # Take best price (highest confidence)
        best_price = max(prices_found, key=lambda x: x["confidence"])

        # Create observations for first 2 items (limit)
        observations = []
        for variant_key in items_found[:2]:
            obs = ObservedPrice(
                canonical_item_id=variant_key.split(":")[-1],
                variant_key=variant_key,
                price_fg=best_price["price"],
                signal_kind=best_price["signal_kind"],
                confidence=best_price["confidence"],
                forum_id=post.forum_id,
                thread_id=post.thread_id,
                post_id=post.post_id or 0,
                thread_category_id=post.thread_category_id,
                observed_at=post.timestamp or datetime.now(),
                raw_text=text[:500],
            )
            observations.append(obs)

        return observations
