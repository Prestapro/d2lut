"""Tests for PriceLookupEngine LRU cache (task 19.2)."""

import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from d2lut.models import PriceEstimate
from d2lut.overlay.price_lookup import PriceLookupEngine


@pytest.fixture
def cache_db():
    """Minimal test DB with a few price_estimates rows."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE price_estimates (
            id INTEGER PRIMARY KEY,
            market_key TEXT NOT NULL,
            variant_key TEXT NOT NULL,
            estimate_fg REAL NOT NULL,
            range_low_fg REAL NOT NULL,
            range_high_fg REAL NOT NULL,
            confidence TEXT NOT NULL,
            sample_count INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(market_key, variant_key)
        );
    """)

    now = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        """INSERT INTO price_estimates
           (market_key, variant_key, estimate_fg, range_low_fg, range_high_fg,
            confidence, sample_count, updated_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        [
            ("d2jsp", "rune:jah", 5000, 4500, 5500, "high", 25, now),
            ("d2jsp", "rune:ber", 3500, 3200, 3800, "high", 30, now),
            ("d2jsp", "unique:shako", 800, 700, 900, "high", 50, now),
        ],
    )
    conn.commit()
    conn.close()

    yield db_path
    db_path.unlink(missing_ok=True)


# ── Cache hit / miss ──────────────────────────────────────────────────────


def test_cache_miss_queries_db(cache_db):
    """First call for a key should be a cache miss and hit the DB."""
    engine = PriceLookupEngine(cache_db)
    result = engine.get_price("rune:jah")
    assert result is not None
    assert result.estimate_fg == 5000
    stats = engine.get_cache_stats()
    assert stats["misses"] == 1
    assert stats["hits"] == 0
    assert stats["size"] == 1
    engine.close()


def test_cache_hit_returns_same_result(cache_db):
    """Second call for the same key should be a cache hit, no extra DB query."""
    engine = PriceLookupEngine(cache_db)
    first = engine.get_price("rune:jah")
    second = engine.get_price("rune:jah")
    assert first is not None and second is not None
    assert first.estimate_fg == second.estimate_fg
    assert first.variant_key == second.variant_key
    stats = engine.get_cache_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    engine.close()


def test_cache_hit_does_not_query_db(cache_db):
    """After caching, closing the real connection should still allow cached lookups."""
    engine = PriceLookupEngine(cache_db)
    # Prime the cache
    engine.get_price("rune:jah")
    # Sabotage the DB connection so any real query would fail
    engine.conn.close()
    # Cached lookup should still work
    result = engine.get_price("rune:jah")
    assert result is not None
    assert result.estimate_fg == 5000


def test_cache_miss_for_nonexistent_item(cache_db):
    """Querying a missing item caches None and counts as a miss."""
    engine = PriceLookupEngine(cache_db)
    assert engine.get_price("nonexistent") is None
    assert engine.get_price("nonexistent") is None  # second call is a hit
    stats = engine.get_cache_stats()
    assert stats["misses"] == 1
    assert stats["hits"] == 1
    assert stats["size"] == 1
    engine.close()


# ── clear_cache ───────────────────────────────────────────────────────────


def test_clear_cache_resets_everything(cache_db):
    """After clear_cache, next call should miss and re-query DB."""
    engine = PriceLookupEngine(cache_db)
    engine.get_price("rune:jah")
    engine.clear_cache()
    stats = engine.get_cache_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["size"] == 0
    # Next call should be a miss again
    engine.get_price("rune:jah")
    stats = engine.get_cache_stats()
    assert stats["misses"] == 1
    engine.close()


# ── Cache size limit / LRU eviction ──────────────────────────────────────


def test_cache_evicts_oldest_when_full(cache_db):
    """With cache_size=2, inserting a 3rd key evicts the oldest."""
    engine = PriceLookupEngine(cache_db, cache_size=2)
    engine.get_price("rune:jah")
    engine.get_price("rune:ber")
    assert engine.get_cache_stats()["size"] == 2
    # Insert a third — should evict rune:jah (oldest)
    engine.get_price("unique:shako")
    assert engine.get_cache_stats()["size"] == 2
    # rune:jah should now be a miss (evicted)
    engine.get_price("rune:jah")
    stats = engine.get_cache_stats()
    # misses: jah(1) + ber(2) + shako(3) + jah-again(4) = 4
    assert stats["misses"] == 4
    engine.close()


def test_cache_lru_order_updated_on_hit(cache_db):
    """Accessing a cached key moves it to most-recent, protecting it from eviction."""
    engine = PriceLookupEngine(cache_db, cache_size=2)
    engine.get_price("rune:jah")   # miss → cache: [jah]
    engine.get_price("rune:ber")   # miss → cache: [jah, ber]
    # Touch jah again — moves it to most-recent
    engine.get_price("rune:jah")   # hit  → cache: [ber, jah]
    # Insert shako — should evict ber (now oldest), not jah
    engine.get_price("unique:shako")  # miss → cache: [jah, shako]
    stats = engine.get_cache_stats()
    assert stats["size"] == 2
    # jah should still be cached (was refreshed by the hit)
    engine.conn.close()  # sabotage DB
    result = engine.get_price("rune:jah")
    assert result is not None
    assert result.estimate_fg == 5000


# ── get_cache_stats ───────────────────────────────────────────────────────


def test_get_cache_stats_initial(cache_db):
    """Fresh engine should have zero stats."""
    engine = PriceLookupEngine(cache_db)
    stats = engine.get_cache_stats()
    assert stats == {"hits": 0, "misses": 0, "size": 0, "max_size": 256}
    engine.close()


def test_get_cache_stats_after_activity(cache_db):
    """Stats reflect actual cache activity."""
    engine = PriceLookupEngine(cache_db, cache_size=128)
    engine.get_price("rune:jah")       # miss
    engine.get_price("rune:jah")       # hit
    engine.get_price("rune:ber")       # miss
    engine.get_price("nonexistent")    # miss (None cached)
    engine.get_price("nonexistent")    # hit (None from cache)
    stats = engine.get_cache_stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 3
    assert stats["size"] == 3
    assert stats["max_size"] == 128
    engine.close()


# ── Demand model enrichment with cache ────────────────────────────────────


def test_demand_enrichment_works_with_cache(cache_db):
    """Demand model enrichment should apply after cache lookup."""
    engine = PriceLookupEngine(cache_db)

    mock_demand = MagicMock()
    mock_metrics = MagicMock()
    mock_metrics.demand_score = 0.85
    mock_metrics.observed_velocity = 2.5
    mock_demand.calculate_demand.return_value = mock_metrics

    # First call — miss, enriched
    r1 = engine.get_price("rune:jah", demand_model=mock_demand)
    assert r1 is not None
    assert r1.demand_score == 0.85

    # Second call — hit, still enriched
    r2 = engine.get_price("rune:jah", demand_model=mock_demand)
    assert r2 is not None
    assert r2.demand_score == 0.85
    assert engine.get_cache_stats()["hits"] == 1

    # Call without demand_model — hit, no demand fields
    r3 = engine.get_price("rune:jah")
    assert r3 is not None
    assert r3.demand_score is None
    engine.close()


def test_demand_enrichment_does_not_pollute_cache(cache_db):
    """Demand enrichment on one call should not leak into the cached copy."""
    engine = PriceLookupEngine(cache_db)

    mock_demand = MagicMock()
    mock_metrics = MagicMock()
    mock_metrics.demand_score = 0.9
    mock_metrics.observed_velocity = 3.0
    mock_demand.calculate_demand.return_value = mock_metrics

    engine.get_price("rune:jah", demand_model=mock_demand)
    # Fetch again without demand — should NOT have demand_score
    plain = engine.get_price("rune:jah")
    assert plain is not None
    assert plain.demand_score is None
    engine.close()


# ── Backward compatibility ────────────────────────────────────────────────


def test_backward_compat_no_cache_size_arg(cache_db):
    """Existing callers that don't pass cache_size should work unchanged."""
    engine = PriceLookupEngine(cache_db)
    result = engine.get_price("rune:jah")
    assert result is not None
    assert result.estimate_fg == 5000
    engine.close()


def test_backward_compat_variant_arg(cache_db):
    """Existing callers using variant= kwarg should work with cache."""
    engine = PriceLookupEngine(cache_db)
    result = engine.get_price("rune", variant="rune:jah")
    assert result is not None
    assert result.estimate_fg == 5000
    # Same call again — should be a cache hit
    result2 = engine.get_price("rune", variant="rune:jah")
    assert result2 is not None
    assert engine.get_cache_stats()["hits"] == 1
    engine.close()
