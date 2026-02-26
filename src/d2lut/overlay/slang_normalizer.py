"""Slang normalization for item identification."""

from dataclasses import dataclass
import sqlite3
import re
from pathlib import Path


@dataclass
class SlangMatch:
    """Represents a slang term match in text."""
    term_raw: str
    term_norm: str
    canonical_item_id: str | None
    replacement_text: str
    confidence: float
    match_position: tuple[int, int]  # start, end indices


class SlangNormalizer:
    """
    Normalizes item names by resolving slang terms to standard names.
    
    Integrates with the slang_aliases database table to map slang terms
    to canonical item names.
    """
    
    def __init__(self, db_path: Path | str):
        """
        Initialize the slang normalizer.
        
        Args:
            db_path: Path to the database containing slang_aliases table
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        
        # Cache for slang lookups
        self._slang_cache: dict[str, list[dict]] = {}
        self._load_slang_cache()
    
    def _load_slang_cache(self) -> None:
        """Load slang aliases from database into memory cache."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            cursor = conn.execute("""
                SELECT term_norm, term_raw, canonical_item_id, 
                       replacement_text, confidence, term_type
                FROM slang_aliases
                WHERE enabled = 1
                ORDER BY confidence DESC, LENGTH(term_norm) DESC
            """)
            
            for row in cursor:
                term_norm = row["term_norm"]
                if term_norm not in self._slang_cache:
                    self._slang_cache[term_norm] = []
                
                self._slang_cache[term_norm].append({
                    "term_raw": row["term_raw"],
                    "canonical_item_id": row["canonical_item_id"],
                    "replacement_text": row["replacement_text"],
                    "confidence": row["confidence"],
                    "term_type": row["term_type"]
                })
        finally:
            conn.close()
    
    def _normalize_term(self, text: str) -> str:
        """
        Normalize a term for lookup.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text (lowercase, stripped, spaces collapsed)
        """
        # Convert to lowercase
        text = text.lower()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Strip leading/trailing whitespace
        text = text.strip()
        return text
    
    def find_slang_matches(self, text: str) -> list[SlangMatch]:
        """
        Find all slang terms in the given text.
        
        Args:
            text: Text to search for slang terms
            
        Returns:
            List of SlangMatch objects for all found slang terms
        """
        matches: list[SlangMatch] = []
        text_lower = text.lower()
        
        # Sort slang terms by length (longest first) to match longer phrases first
        sorted_terms = sorted(
            self._slang_cache.keys(),
            key=lambda x: len(x),
            reverse=True
        )
        
        # Track matched positions to avoid overlapping matches
        matched_positions: set[int] = set()
        
        for term_norm in sorted_terms:
            # Find all occurrences of this term in the text
            pattern = re.escape(term_norm)
            for match in re.finditer(pattern, text_lower):
                start, end = match.span()
                
                # Check if this position overlaps with an existing match
                if any(pos in matched_positions for pos in range(start, end)):
                    continue
                
                # Get the best match for this term (highest confidence)
                slang_entries = self._slang_cache[term_norm]
                best_entry = slang_entries[0]  # Already sorted by confidence
                
                # Extract the actual matched text from original (preserving case)
                matched_text = text[start:end]
                
                matches.append(SlangMatch(
                    term_raw=matched_text,
                    term_norm=term_norm,
                    canonical_item_id=best_entry["canonical_item_id"] or None,
                    replacement_text=best_entry["replacement_text"],
                    confidence=best_entry["confidence"],
                    match_position=(start, end)
                ))
                
                # Mark these positions as matched
                matched_positions.update(range(start, end))
        
        # Sort matches by position
        matches.sort(key=lambda m: m.match_position[0])
        return matches
    
    def normalize(self, text: str) -> str:
        """
        Normalize text by resolving slang terms to standard names.
        
        For ambiguous slang terms (multiple possible matches), uses the
        highest confidence match.
        
        Args:
            text: Text containing potential slang terms
            
        Returns:
            Normalized text with slang terms replaced
        """
        matches = self.find_slang_matches(text)
        
        if not matches:
            return text
        
        # Build the normalized text by replacing matches
        result_parts: list[str] = []
        last_end = 0
        
        for match in matches:
            start, end = match.match_position
            
            # Add text before this match
            result_parts.append(text[last_end:start])
            
            # Add replacement text
            result_parts.append(match.replacement_text)
            
            last_end = end
        
        # Add remaining text after last match
        result_parts.append(text[last_end:])
        
        return ''.join(result_parts)
    
    def get_all_matches(self, slang_term: str) -> list[dict]:
        """
        Get all possible matches for a slang term (for ambiguous cases).
        
        Args:
            slang_term: Slang term to look up
            
        Returns:
            List of dictionaries with canonical_item_id, replacement_text, 
            confidence, and term_type for all possible matches
        """
        term_norm = self._normalize_term(slang_term)
        return self._slang_cache.get(term_norm, [])
    
    def reload_cache(self) -> None:
        """Reload the slang cache from the database."""
        self._slang_cache.clear()
        self._load_slang_cache()
