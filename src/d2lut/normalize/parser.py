"""Market post parser for extracting price signals."""

from __future__ import annotations

import re
import logging
from datetime import datetime
from typing import Iterable

from ..models import MarketPost, ObservedPrice

logger = logging.getLogger(__name__)

# Item patterns for identification
_ITEM_PATTERNS = {
    # Runes
    "rune:jah": re.compile(r"\bjah\b", re.I),
    "rune:ber": re.compile(r"\bber\b", re.I),
    "rune:sur": re.compile(r"\bsur\b", re.I),
    "rune:lo": re.compile(r"\blo\s*(?:rune)?\b", re.I),
    "rune:ohm": re.compile(r"\bohm\b", re.I),
    "rune:vex": re.compile(r"\bvex\b", re.I),
    "rune:gul": re.compile(r"\bgul\b", re.I),
    "rune:ist": re.compile(r"\bist\b", re.I),
    "rune:mal": re.compile(r"\bmal\s*(?:rune)?\b", re.I),
    "rune:um": re.compile(r"\bum\s*(?:rune)?\b", re.I),
    "rune:ko": re.compile(r"\bko\s*(?:rune)?\b", re.I),
    
    # Uniques
    "unique:shako": re.compile(r"\bshako\b|\bharlequin\s*crest\b", re.I),
    "unique:arachnid": re.compile(r"\barachnid\b|\bspider\s*web\s*belt\b", re.I),
    "unique:mara": re.compile(r"\bmara'?s?\b|\bkaleidoscope\b", re.I),
    "unique:tyraels": re.compile(r"\btyrael'?s?\s*might\b", re.I),
    
    # Runewords
    "runeword:enigma": re.compile(r"\benigma\b", re.I),
    "runeword:infinity": re.compile(r"\binfinity\b", re.I),
    "runeword:cta": re.compile(r"\bcta\b|\bcall\s*to\s*arms\b", re.I),
    "runeword:grief": re.compile(r"\bgrief\b", re.I),
    "runeword:fortitude": re.compile(r"\bfortitude\b", re.I),
    "runeword:spirit": re.compile(r"\bspirit\b", re.I),
    
    # Torches and Annis
    "unique:torch": re.compile(r"\btorch\b|\bhellfire\s*torch\b", re.I),
    "unique:anni": re.compile(r"\banni(?:hilus)?\b", re.I),
}

# Price patterns
_PRICE_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*fg", re.I),
    re.compile(r"(\d+(?:\.\d+)?)\s*forum\s*gold", re.I),
    re.compile(r"bin\s*:?\s*(\d+)", re.I),
    re.compile(r"sold\s*(\d+)", re.I),
]


class MarketParser:
    """Parser for extracting price signals from forum posts."""
    
    def __init__(self):
        self.item_patterns = _ITEM_PATTERNS
        self.price_patterns = _PRICE_PATTERNS
    
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
        
        # Find prices
        prices_found = []
        for pattern in self.price_patterns:
            for match in pattern.finditer(text):
                try:
                    price = float(match.group(1))
                    prices_found.append({
                        "price": price,
                        "confidence": self._calc_confidence(match.group(0)),
                    })
                except (ValueError, IndexError):
                    continue
        
        if not prices_found:
            return []
        
        # Take best price
        best_price = max(prices_found, key=lambda x: x["confidence"])
        
        # Create observations for first 2 items (limit)
        observations = []
        for variant_key in items_found[:2]:
            obs = ObservedPrice(
                canonical_item_id=variant_key.split(":")[-1],
                variant_key=variant_key,
                price_fg=best_price["price"],
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
    
    def _calc_confidence(self, match_text: str) -> float:
        """Calculate confidence score for a price match.
        
        Higher confidence for explicit BIN/SOLD mentions.
        """
        text_lower = match_text.lower()
        if "sold" in text_lower:
            return 0.9
        if "bin" in text_lower:
            return 0.8
        if "fg" in text_lower or "forum gold" in text_lower:
            return 0.7
        return 0.5
