"""Item identification system for matching parsed tooltips to catalog entries."""

from dataclasses import dataclass, field
import sqlite3
from pathlib import Path
from difflib import SequenceMatcher

from .ocr_parser import ParsedItem
from .slang_normalizer import SlangNormalizer
from d2lut.normalize.modifier_lexicon import ocr_fold_text


@dataclass
class CatalogItem:
    """Represents an item from the catalog database."""
    canonical_item_id: str
    display_name: str
    category: str
    quality_class: str
    base_code: str | None = None
    tradeable: bool = True
    metadata: dict = field(default_factory=dict)


@dataclass
class MatchResult:
    """Result of item identification."""
    canonical_item_id: str | None
    confidence: float
    matched_name: str
    candidates: list[CatalogItem]  # For ambiguous cases
    match_type: str  # exact, fuzzy, slang, partial
    context_used: dict = field(default_factory=dict)


class ItemIdentifier:
    """
    Identifies items by matching parsed tooltips to catalog entries.
    
    Uses slang resolution, fuzzy matching, and catalog lookups to find
    the best match for a parsed item.
    """
    
    def __init__(self, db_path: Path | str, fuzzy_threshold: float = 0.8):
        """
        Initialize the item identifier.
        
        Args:
            db_path: Path to the database containing catalog and slang tables
            fuzzy_threshold: Minimum similarity score for fuzzy matches (0.0-1.0)
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        
        self.fuzzy_threshold = fuzzy_threshold
        self.slang_normalizer = SlangNormalizer(db_path)
        
        # Cache for catalog lookups
        self._catalog_cache: dict[str, list[CatalogItem]] = {}
        self._alias_cache: dict[str, list[tuple[str, int]]] = {}  # alias_norm -> [(canonical_id, priority)]
        self._load_catalog_cache()
    
    def _load_catalog_cache(self) -> None:
        """Load catalog items and aliases into memory cache."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            # Load catalog items
            cursor = conn.execute("""
                SELECT canonical_item_id, display_name, category, 
                       quality_class, base_code, tradeable, metadata_json
                FROM catalog_items
                WHERE enabled = 1
            """)
            
            for row in cursor:
                item = CatalogItem(
                    canonical_item_id=row["canonical_item_id"],
                    display_name=row["display_name"],
                    category=row["category"],
                    quality_class=row["quality_class"],
                    base_code=row["base_code"],
                    tradeable=bool(row["tradeable"]),
                    metadata={}
                )
                
                # Store by canonical_item_id
                if item.canonical_item_id not in self._catalog_cache:
                    self._catalog_cache[item.canonical_item_id] = []
                self._catalog_cache[item.canonical_item_id].append(item)
            
            # Load aliases
            cursor = conn.execute("""
                SELECT alias_norm, canonical_item_id, priority
                FROM catalog_aliases
                ORDER BY priority ASC
            """)
            
            for row in cursor:
                alias_norm = row["alias_norm"]
                if alias_norm not in self._alias_cache:
                    self._alias_cache[alias_norm] = []
                
                self._alias_cache[alias_norm].append((
                    row["canonical_item_id"],
                    row["priority"]
                ))
        finally:
            conn.close()
    
    def _normalize_name(self, name: str) -> str:
        """
        Normalize an item name for matching.
        
        Args:
            name: Item name to normalize
            
        Returns:
            Normalized name (lowercase, stripped, spaces collapsed)
        """
        import re
        name = name.lower()
        name = re.sub(r'\s+', ' ', name)
        name = name.strip()
        return name
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    def _best_name_similarity(self, query_norm: str, candidate_name: str) -> float:
        """Best-effort similarity against a candidate display name and its tokens."""
        candidate_norm = self._normalize_name(candidate_name)
        best = self._calculate_similarity(query_norm, candidate_norm)
        for token in candidate_norm.split():
            if token:
                best = max(best, self._calculate_similarity(query_norm, token))
        return best
    
    def resolve_slang(self, text: str) -> str:
        """
        Resolve slang terms in text to standard names.
        
        Args:
            text: Text containing potential slang terms
            
        Returns:
            Text with slang terms resolved
        """
        return self.slang_normalizer.normalize(text)
    
    def find_candidates(self, item_name: str, item_type: str | None = None) -> list[CatalogItem]:
        """
        Find potential catalog matches for an item name.
        
        Args:
            item_name: Item name to search for
            item_type: Optional item type to filter by
            
        Returns:
            List of candidate CatalogItem objects
        """
        candidates: list[CatalogItem] = []
        name_norm = self._normalize_name(item_name)
        
        # First, try exact match via aliases
        if name_norm in self._alias_cache:
            for canonical_id, priority in self._alias_cache[name_norm]:
                if canonical_id in self._catalog_cache:
                    for item in self._catalog_cache[canonical_id]:
                        if item_type is None or item.category == item_type:
                            candidates.append(item)
        
        # OCR-noise tolerant exact fallback against alias cache
        if not candidates:
            q_fold = ocr_fold_text(item_name)
            if q_fold:
                for alias_norm, canonical_ids in self._alias_cache.items():
                    if ocr_fold_text(alias_norm) != q_fold:
                        continue
                    for canonical_id, priority in canonical_ids:
                        if canonical_id in self._catalog_cache:
                            for item in self._catalog_cache[canonical_id]:
                                if item_type is None or item.category == item_type:
                                    candidates.append(item)
                    if candidates:
                        break

        # If no exact matches, try fuzzy matching
        if not candidates:
            seen_ids: set[str] = set()

            # Fuzzy against aliases first
            for alias_norm, canonical_ids in self._alias_cache.items():
                similarity = self._calculate_similarity(name_norm, alias_norm)
                
                if similarity >= self.fuzzy_threshold:
                    for canonical_id, priority in canonical_ids:
                        if canonical_id in self._catalog_cache:
                            for item in self._catalog_cache[canonical_id]:
                                if item_type is None or item.category == item_type:
                                    if item.canonical_item_id not in seen_ids:
                                        candidates.append(item)
                                        seen_ids.add(item.canonical_item_id)

            # Fallback fuzzy matching against catalog display names.
            # This catches typos when aliases are shorter/different (e.g. "Harlequn").
            if not candidates:
                for canonical_id, items in self._catalog_cache.items():
                    for item in items:
                        if item_type is not None and item.category != item_type:
                            continue
                        similarity = self._best_name_similarity(name_norm, item.display_name)
                        if similarity >= self.fuzzy_threshold and item.canonical_item_id not in seen_ids:
                            candidates.append(item)
                            seen_ids.add(item.canonical_item_id)
        
        return candidates
    
    def identify(self, parsed: ParsedItem) -> MatchResult:
        """
        Identify an item from parsed tooltip data.
        
        Uses slang resolution, exact matching, and fuzzy matching to find
        the best catalog match.
        
        Args:
            parsed: ParsedItem from OCR parser
            
        Returns:
            MatchResult with identification details
        """
        context = {
            "original_name": parsed.item_name,
            "item_type": parsed.item_type,
            "quality": parsed.quality,
            "ocr_confidence": parsed.confidence
        }
        
        # Handle parsing errors
        if parsed.error or not parsed.item_name:
            return MatchResult(
                canonical_item_id=None,
                confidence=0.0,
                matched_name="",
                candidates=[],
                match_type="error",
                context_used=context
            )
        
        item_name = parsed.item_name
        
        # Step 1: Try slang resolution
        slang_matches = self.slang_normalizer.find_slang_matches(item_name)
        if slang_matches:
            # Use the first (highest confidence) slang match
            best_slang = slang_matches[0]
            
            if best_slang.canonical_item_id:
                # Direct canonical ID from slang
                if best_slang.canonical_item_id in self._catalog_cache:
                    item = self._catalog_cache[best_slang.canonical_item_id][0]
                    return MatchResult(
                        canonical_item_id=item.canonical_item_id,
                        confidence=best_slang.confidence * parsed.confidence,
                        matched_name=item.display_name,
                        candidates=[item],
                        match_type="slang",
                        context_used={**context, "slang_term": best_slang.term_raw}
                    )
            
            # Use replacement text for further matching
            item_name = best_slang.replacement_text
            context["slang_resolved"] = True
            context["slang_term"] = best_slang.term_raw
        
        # Step 2: Normalize the name
        name_norm = self._normalize_name(item_name)
        
        # Step 3: Try exact match via aliases
        if name_norm in self._alias_cache:
            canonical_ids = self._alias_cache[name_norm]
            # Get the highest priority match
            best_canonical_id = canonical_ids[0][0]
            
            if best_canonical_id in self._catalog_cache:
                item = self._catalog_cache[best_canonical_id][0]
                
                # Get all candidates for this alias (for ambiguous cases)
                all_candidates = []
                for canonical_id, priority in canonical_ids:
                    if canonical_id in self._catalog_cache:
                        all_candidates.extend(self._catalog_cache[canonical_id])
                
                return MatchResult(
                    canonical_item_id=item.canonical_item_id,
                    confidence=parsed.confidence,
                    matched_name=item.display_name,
                    candidates=all_candidates,
                    match_type="exact",
                    context_used=context
                )
        
        # Step 4: Try fuzzy matching
        candidates = self.find_candidates(item_name, parsed.item_type)
        
        if candidates:
            # Calculate similarity scores for each candidate
            scored_candidates = []
            for candidate in candidates:
                # Try matching against display name and aliases
                best_similarity = 0.0
                
                # Check display name
                similarity = self._best_name_similarity(name_norm, candidate.display_name)
                best_similarity = max(best_similarity, similarity)
                
                # Check aliases
                for alias_norm, canonical_ids in self._alias_cache.items():
                    if any(cid == candidate.canonical_item_id for cid, _ in canonical_ids):
                        similarity = self._calculate_similarity(name_norm, alias_norm)
                        best_similarity = max(best_similarity, similarity)
                
                scored_candidates.append((candidate, best_similarity))
            
            # Sort by similarity score
            scored_candidates.sort(key=lambda x: x[1], reverse=True)
            
            best_candidate, best_score = scored_candidates[0]
            
            # Adjust confidence based on fuzzy match quality
            confidence = best_score * parsed.confidence
            
            return MatchResult(
                canonical_item_id=best_candidate.canonical_item_id,
                confidence=confidence,
                matched_name=best_candidate.display_name,
                candidates=[c for c, _ in scored_candidates[:5]],  # Top 5 candidates
                match_type="fuzzy",
                context_used={**context, "similarity_score": best_score}
            )
        
        # Step 5: No match found - return partial result
        return MatchResult(
            canonical_item_id=None,
            confidence=0.0,
            matched_name=item_name,
            candidates=[],
            match_type="no_match",
            context_used=context
        )
    
    def reload_cache(self) -> None:
        """Reload catalog and slang caches from the database."""
        self._catalog_cache.clear()
        self._alias_cache.clear()
        self._load_catalog_cache()
        self.slang_normalizer.reload_cache()
