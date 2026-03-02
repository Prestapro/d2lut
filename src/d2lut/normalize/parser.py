from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from d2lut.models import MarketPost, ObservedPrice


@dataclass
class ParseResult:
    """Result of parsing a single post."""
    observations: list[ObservedPrice] = field(default_factory=list)
    confidence: float = 0.5
    raw_signals: list[dict] = field(default_factory=list)


# Price patterns compiled once
_PRICE_PATTERNS = [
    (re.compile(r"(?:bin|b/o|buyout)[:\s]*(\d+(?:\.\d+)?)\s*(?:fg|forum\s*gold)", re.I), "bin", 0.9),
    (re.compile(r"(\d+(?:\.\d+)?)\s*fg\s*(?:bin|b/o)", re.I), "bin", 0.85),
    (re.compile(r"sold[:\s]*(?:@?\s*)?(\d+(?:\.\d+)?)\s*(?:fg)?", re.I), "sold", 0.95),
    (re.compile(r"(\d+(?:\.\d+)?)\s*fg\s*sold", re.I), "sold", 0.95),
    (re.compile(r"(?:asking|c/o)[:\s]*(\d+(?:\.\d+)?)\s*(?:fg)?", re.I), "ask", 0.6),
    (re.compile(r"(\d+(?:\.\d+)?)\s*fg(?!\s*bin)", re.I), "ask", 0.5),
]

# Item patterns with canonical keys
_ITEM_PATTERNS = {
    # Runes
    "rune:jah": re.compile(r"\bjah\b", re.I),
    "rune:ber": re.compile(r"\bber\b", re.I),
    "rune:sur": re.compile(r"\bsur\b", re.I),
    "rune:lo": re.compile(r"\blo\b", re.I),
    "rune:ohm": re.compile(r"\bohm\b", re.I),
    "rune:vex": re.compile(r"\bvex\b", re.I),
    "rune:cham": re.compile(r"\bcham\b", re.I),
    "rune:zod": re.compile(r"\bzod\b", re.I),
    "rune:gul": re.compile(r"\bgul\b", re.I),
    "rune:ist": re.compile(r"\bist\b", re.I),
    "rune:mal": re.compile(r"\bmal\b", re.I),
    "rune:um": re.compile(r"\bum\b", re.I),
    "rune:pul": re.compile(r"\bpul\b", re.I),
    "rune:lem": re.compile(r"\blem\b", re.I),
    "rune:fal": re.compile(r"\bfal\b", re.I),
    "rune:ko": re.compile(r"\bko\b", re.I),
    "rune:lum": re.compile(r"\blum\b", re.I),
    
    # High-value uniques
    "unique:shako": re.compile(r"\bshakos?\b|\bharlequin\s*crest\b", re.I),
    "unique:arachnid_mesh": re.compile(r"\barachs?\b|\barachnid\b", re.I),
    "unique:griffons_eye": re.compile(r"\bgriffons?\b", re.I),
    "unique:deaths_fathom": re.compile(r"\bfathoms?\b|\bdeaths?\s*fathom\b", re.I),
    "unique:hoz": re.compile(r"\bhoz\b|\bherald\s*of\s*zakarum\b", re.I),
    "unique:soj": re.compile(r"\bsoj\b|\bstone\s*of\s*jordan\b", re.I),
    "unique:bk": re.compile(r"\bbk\s*(?:ring|wedding)?\b|\bbul[\'\-]?kathos\b", re.I),
    "unique:maras": re.compile(r"\bmaras?\b|\bmara\b", re.I),
    "unique:highlords": re.compile(r"\bhighlords?\b", re.I),
    "unique:tyraels": re.compile(r"\btyraels?\b|\bmight\b", re.I),
    
    # Runewords
    "runeword:enigma": re.compile(r"\benigma\b|\bnigma\b", re.I),
    "runeword:infinity": re.compile(r"\binfinity\b|\binfi\b", re.I),
    "runeword:grief": re.compile(r"\bgrief\b", re.I),
    "runeword:cta": re.compile(r"\bcta\b|\bcall\s*to\s*arms\b", re.I),
    "runeword:fortitude": re.compile(r"\bforti?\b|\bfortitude\b", re.I),
    
    # Torches/Annihilus
    "unique:torch": re.compile(r"\btorch(?:es)?\b|\bhellfire\b", re.I),
    "unique:anni": re.compile(r"\banni(?:hilus)?\b", re.I),
}


class MarketParser:
    """Parse forum posts into normalized item price observations.
    
    This implementation handles common d2jsp patterns:
    - BIN prices: "bin 50fg", "50fg bin"
    - Sold prices: "sold @ 30fg", "30fg sold"
    - Asking prices: "c/o 20fg", "asking 25fg"
    """

    def __init__(self):
        self._price_patterns = _PRICE_PATTERNS
        self._item_patterns = _ITEM_PATTERNS

    def parse_posts(self, posts: Iterable[MarketPost]) -> list[ObservedPrice]:
        """Parse a batch of posts into price observations."""
        observations = []
        
        for post in posts:
            result = self._parse_single_post(post)
            observations.extend(result.observations)
        
        return observations

    def _parse_single_post(self, post: MarketPost) -> ParseResult:
        """Parse a single post."""
        result = ParseResult()
        
        text = post.body or ""
        title = post.title or ""
        combined = f"{title} {text}"
        
        # Find all items mentioned
        items_found = []
        for variant_key, pattern in self._item_patterns.items():
            if pattern.search(combined):
                items_found.append(variant_key)
        
        if not items_found:
            return result
        
        # Find all prices
        prices_found = []
        for pattern, price_type, base_conf in self._price_patterns:
            for match in pattern.finditer(combined):
                price_val = float(match.group(1))
                if 0.1 <= price_val <= 100000:  # Sanity check
                    prices_found.append({
                        "price": price_val,
                        "type": price_type,
                        "confidence": base_conf,
                    })
        
        # Match items to prices
        if items_found and prices_found:
            # Use highest confidence price
            best_price = max(prices_found, key=lambda x: x["confidence"])
            
            for item_key in items_found[:2]:  # Max 2 items per post
                obs = ObservedPrice(
                    canonical_item_id=item_key.split(":")[1] if ":" in item_key else item_key,
                    variant_key=item_key,
                    ask_fg=best_price["price"] if best_price["type"] == "ask" else None,
                    bin_fg=best_price["price"] if best_price["type"] == "bin" else None,
                    sold_fg=best_price["price"] if best_price["type"] == "sold" else None,
                    confidence=best_price["confidence"],
                    source_url=post.url,
                )
                result.observations.append(obs)
        
        return result
