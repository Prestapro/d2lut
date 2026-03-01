"""Price lookup engine for overlay system.

Integrates with existing d2lut pricing engine to provide price estimates
for identified items in the overlay system.
"""

from __future__ import annotations

import copy
import sqlite3
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from d2lut.models import PriceEstimate


@dataclass
class FGListing:
    """Represents a recent market listing from snapshots."""
    price_fg: float
    listing_type: str  # bin, ask, co, sold
    thread_id: int
    post_id: int | None
    posted_at: datetime | None
    is_recent: bool
    thread_title: str | None = None
    source_url: str | None = None


class PriceLookupEngine:
    """
    Price lookup engine for the overlay system.
    
    Provides price estimates and recent market listings for identified items
    by querying the existing d2lut market database.
    """
    
    def __init__(self, db_path: str | Path, cache_size: int = 256):
        """
        Initialize the price lookup engine.

        Args:
            db_path: Path to the d2lut market database
            cache_size: Maximum number of price estimates to cache (LRU eviction)
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

        # LRU cache for get_price() results
        self._cache_size = max(1, cache_size)
        self._cache: OrderedDict[tuple[str, str | None], PriceEstimate | None] = OrderedDict()
        self._cache_hits = 0
        self._cache_misses = 0
    
    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()

    # -- LRU cache helpers --------------------------------------------------

    def _cache_put(self, key: tuple[str, str | None], value: PriceEstimate | None) -> None:
        """Insert *key* into the LRU cache, evicting the oldest entry if full."""
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)  # evict oldest

    def clear_cache(self) -> None:
        """Invalidate the price cache and reset stats (e.g. after snapshot refresh)."""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0

    def get_cache_stats(self) -> dict[str, int]:
        """Return cache performance counters."""
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "size": len(self._cache),
            "max_size": self._cache_size,
        }
    def estimate_memory_bytes(self) -> int:
        """Approximate memory used by the LRU cache."""
        from d2lut.overlay.memory_monitor import estimate_object_size
        return estimate_object_size(self._cache)

    # -- Price lookup -------------------------------------------------------

    def get_price(self, item_id: str, variant: str | None = None, demand_model=None) -> PriceEstimate | None:
        """
        Get price estimate for an item.

        Uses an LRU cache keyed on (item_id, variant). Demand enrichment
        happens after cache lookup so demand_model changes don't pollute
        the cache.

        Args:
            item_id: Canonical item ID
            variant: Optional variant key (e.g., "rune:jah", "charm:gheed")
                    If None, uses item_id as the variant key
            demand_model: Optional DemandModel to attach demand metrics

        Returns:
            PriceEstimate if data exists, None otherwise
        """
        cache_key = (item_id, variant)

        # Cache hit path
        if cache_key in self._cache:
            self._cache_hits += 1
            # Move to end (most-recently used)
            self._cache.move_to_end(cache_key)
            cached = self._cache[cache_key]
            if cached is None:
                return None
            # Return a copy so demand enrichment doesn't mutate the cached object
            estimate = copy.copy(cached)
            return self._enrich_with_demand(estimate, demand_model)

        # Cache miss — query DB
        self._cache_misses += 1
        variant_key = variant if variant is not None else item_id

        cursor = self.conn.execute(
            """
            SELECT 
                variant_key,
                estimate_fg,
                range_low_fg,
                range_high_fg,
                confidence,
                sample_count,
                updated_at
            FROM price_estimates
            WHERE variant_key = ?
            LIMIT 1
            """,
            (variant_key,)
        )

        row = cursor.fetchone()
        if not row:
            self._cache_put(cache_key, None)
            return None

        try:
            last_updated = datetime.fromisoformat(row["updated_at"])
        except (ValueError, TypeError):
            last_updated = datetime.now()

        estimate = PriceEstimate(
            variant_key=row["variant_key"],
            estimate_fg=float(row["estimate_fg"]),
            range_low_fg=float(row["range_low_fg"]),
            range_high_fg=float(row["range_high_fg"]),
            confidence=row["confidence"],
            sample_count=int(row["sample_count"]),
            last_updated=last_updated
        )

        # Store in cache (without demand enrichment)
        self._cache_put(cache_key, estimate)

        return self._enrich_with_demand(copy.copy(estimate), demand_model)
    
    def _enrich_with_demand(self, estimate: PriceEstimate, demand_model) -> PriceEstimate:
        """Attach demand metrics to a PriceEstimate if demand_model is available."""
        if demand_model is None:
            return estimate
        try:
            metrics = demand_model.calculate_demand(estimate.variant_key)
            estimate.demand_score = metrics.demand_score
            estimate.observed_velocity = metrics.observed_velocity
        except Exception:
            pass  # best-effort
        return estimate
    
    def get_prices_for_variants(self, item_id: str) -> dict[str, PriceEstimate]:
        """
        Get prices for all variants of an item.
        
        Args:
            item_id: Canonical item ID
        
        Returns:
            Dictionary mapping variant_key to PriceEstimate
        """
        # Query all variants that start with the item_id
        # This handles cases like "rune:jah", "rune:ber", etc.
        cursor = self.conn.execute(
            """
            SELECT 
                variant_key,
                estimate_fg,
                range_low_fg,
                range_high_fg,
                confidence,
                sample_count,
                updated_at
            FROM price_estimates
            WHERE variant_key LIKE ? OR variant_key = ?
            ORDER BY estimate_fg DESC
            """,
            (f"{item_id}:%", item_id)
        )
        
        results = {}
        for row in cursor.fetchall():
            try:
                last_updated = datetime.fromisoformat(row["updated_at"])
            except (ValueError, TypeError):
                last_updated = datetime.now()
            
            results[row["variant_key"]] = PriceEstimate(
                variant_key=row["variant_key"],
                estimate_fg=float(row["estimate_fg"]),
                range_low_fg=float(row["range_low_fg"]),
                range_high_fg=float(row["range_high_fg"]),
                confidence=row["confidence"],
                sample_count=int(row["sample_count"]),
                last_updated=last_updated
            )
        
        return results
    
    def get_fg_listings(
        self, 
        item_id: str, 
        variant: str | None = None,
        limit: int = 20,
        recent_days: int = 30
    ) -> list[FGListing]:
        """
        Get recent observed FG listings for an item from snapshots.
        
        Args:
            item_id: Canonical item ID
            variant: Optional variant key
            limit: Maximum number of listings to return
            recent_days: Consider listings from the last N days as "recent"
        
        Returns:
            List of FGListing objects, sorted by most recent first
        """
        variant_key = variant if variant is not None else item_id
        
        # Query observed_prices with thread information
        cursor = self.conn.execute(
            """
            SELECT 
                op.price_fg,
                op.signal_kind,
                op.thread_id,
                op.post_id,
                op.observed_at,
                op.source_url,
                t.title as thread_title,
                julianday('now') - julianday(op.observed_at) as days_ago
            FROM observed_prices op
            LEFT JOIN threads t ON op.thread_id = t.thread_id AND op.source = t.source
            WHERE op.variant_key = ?
            AND op.observed_at IS NOT NULL
            ORDER BY op.observed_at DESC
            LIMIT ?
            """,
            (variant_key, limit)
        )
        
        listings = []
        for row in cursor.fetchall():
            # Parse timestamp
            try:
                posted_at = datetime.fromisoformat(row["observed_at"])
            except (ValueError, TypeError):
                posted_at = None
            
            # Determine if listing is recent
            days_ago = row["days_ago"] if row["days_ago"] is not None else 999
            is_recent = days_ago <= recent_days
            
            listings.append(FGListing(
                price_fg=float(row["price_fg"]),
                listing_type=row["signal_kind"],
                thread_id=int(row["thread_id"]),
                post_id=int(row["post_id"]) if row["post_id"] is not None else None,
                posted_at=posted_at,
                is_recent=is_recent,
                thread_title=row["thread_title"],
                source_url=row["source_url"]
            ))
        
        return listings
    
    def get_market_summary(self, item_id: str, variant: str | None = None, demand_model=None) -> dict[str, Any]:
        """
        Get comprehensive market summary for an item.
        
        Combines price estimate with recent listings and market activity metrics.
        
        Args:
            item_id: Canonical item ID
            variant: Optional variant key
            demand_model: Optional DemandModel to attach demand metrics
        
        Returns:
            Dictionary with price estimate, listings, and market metrics
        """
        variant_key = variant if variant is not None else item_id
        
        # Get price estimate
        price_estimate = self.get_price(item_id, variant, demand_model=demand_model)
        
        # Get recent listings
        listings = self.get_fg_listings(item_id, variant, limit=20)
        
        # Calculate market metrics
        if listings:
            recent_listings = [l for l in listings if l.is_recent]
            bin_listings = [l for l in listings if l.listing_type == "bin"]
            sold_listings = [l for l in listings if l.listing_type == "sold"]
            
            market_activity = {
                "total_listings": len(listings),
                "recent_listings": len(recent_listings),
                "bin_count": len(bin_listings),
                "sold_count": len(sold_listings),
                "has_active_market": len(recent_listings) > 0
            }
        else:
            market_activity = {
                "total_listings": 0,
                "recent_listings": 0,
                "bin_count": 0,
                "sold_count": 0,
                "has_active_market": False
            }
        
        return {
            "item_id": item_id,
            "variant_key": variant_key,
            "price_estimate": price_estimate,
            "listings": listings,
            "market_activity": market_activity,
            "has_data": price_estimate is not None
        }
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
