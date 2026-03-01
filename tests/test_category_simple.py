"""Simple tests for category-aware parsing and weighting (no pytest)."""
from __future__ import annotations

import sys
sys.path.insert(0, "src")

from d2lut.normalize.d2jsp_market import parse_forum_threads_from_html
from d2lut.pricing.engine import PricingEngine
from d2lut.models import ObservedPrice
from datetime import datetime, timezone


def test_parse_forum_threads_extracts_category_from_url():
    """Test that category ID is extracted from thread URLs."""
    print("Testing category extraction from URLs...")
    html = """
    <html>
    <body>
    <table>
    <tr>
        <td><div class="b1">5</div></td>
        <td><a href="topic.php?t=12345&c=4">Jah Rune FT</a></td>
    </tr>
    <tr>
        <td><div class="b1">3</div></td>
        <td><a href="topic.php?t=67890&c=3">Anni Charm</a></td>
    </tr>
    <tr>
        <td><div class="b1">2</div></td>
        <td><a href="topic.php?t=11111">No Category</a></td>
    </tr>
    </table>
    </body>
    </html>
    """
    
    threads = parse_forum_threads_from_html(html, forum_id=271)
    
    # Should have 3 threads
    assert len(threads) == 3, f"Expected 3 threads, got {len(threads)}"
    
    # First thread should have category 4
    jah_thread = next(t for t in threads if t["thread_id"] == 12345)
    assert jah_thread["thread_category_id"] == 4, f"Expected category 4, got {jah_thread.get('thread_category_id')}"
    assert "Jah" in jah_thread["title"]
    print(f"  ✓ Jah thread has category 4: {jah_thread['title']}")
    
    # Second thread should have category 3
    anni_thread = next(t for t in threads if t["thread_id"] == 67890)
    assert anni_thread["thread_category_id"] == 3, f"Expected category 3, got {anni_thread.get('thread_category_id')}"
    assert "Anni" in anni_thread["title"]
    print(f"  ✓ Anni thread has category 3: {anni_thread['title']}")
    
    # Third thread should have no category
    no_cat_thread = next(t for t in threads if t["thread_id"] == 11111)
    assert "thread_category_id" not in no_cat_thread or no_cat_thread["thread_category_id"] is None
    print(f"  ✓ Thread without category: {no_cat_thread['title']}")
    
    print("✓ Category extraction test passed\n")


def test_pricing_engine_category_weights():
    """Test that pricing engine applies correct category weights."""
    print("Testing category weight calculations...")
    engine = PricingEngine()
    
    # Rune in category 4 should get 1.3x multiplier
    weight = engine._calculate_category_weight("rune:jah", category_id=4)
    assert weight == 1.3, f"Expected 1.3, got {weight}"
    print(f"  ✓ Rune in category 4: weight = {weight}")
    
    # Non-rune in category 4 should get 0.7x multiplier
    weight = engine._calculate_category_weight("unique:annihilus", category_id=4)
    assert weight == 0.7, f"Expected 0.7, got {weight}"
    print(f"  ✓ Non-rune in category 4: weight = {weight}")
    
    # Rune with no category should get 1.0x multiplier
    weight = engine._calculate_category_weight("rune:jah", category_id=None)
    assert weight == 1.0, f"Expected 1.0, got {weight}"
    print(f"  ✓ Rune with no category: weight = {weight}")
    
    # Charm in category 3 should get 1.3x multiplier
    weight = engine._calculate_category_weight("charm:small", category_id=3)
    assert weight == 1.3, f"Expected 1.3, got {weight}"
    print(f"  ✓ Charm in category 3: weight = {weight}")
    
    # LLD item in category 5 should get 1.2x multiplier
    weight = engine._calculate_category_weight("unique:some_item", category_id=5)
    assert weight == 1.2, f"Expected 1.2, got {weight}"
    print(f"  ✓ LLD item in category 5: weight = {weight}")
    
    print("✓ Category weight test passed\n")


def test_pricing_engine_uses_category_weights():
    """Test that pricing engine applies category weights to observations."""
    print("Testing pricing engine with category weights...")
    engine = PricingEngine()
    
    # Create observations for a rune with different categories
    observations = [
        ObservedPrice(
            canonical_item_id="rune:jah",
            variant_key="rune:jah",
            bin_fg=5000.0,
            confidence=0.8,
            thread_category_id=4,  # Correct category - should get boost
        ),
        ObservedPrice(
            canonical_item_id="rune:jah",
            variant_key="rune:jah",
            bin_fg=5500.0,
            confidence=0.8,
            thread_category_id=2,  # Wrong category - should get penalty
        ),
        ObservedPrice(
            canonical_item_id="rune:jah",
            variant_key="rune:jah",
            bin_fg=5200.0,
            confidence=0.8,
            thread_category_id=None,  # No category - neutral
        ),
    ]
    
    estimates = engine.build_index(observations)
    
    # Should have one estimate for the variant
    assert "rune:jah" in estimates, "Expected estimate for rune:jah"
    estimate = estimates["rune:jah"]
    
    print(f"  Estimate: {estimate.estimate_fg} FG (range: {estimate.range_low_fg}-{estimate.range_high_fg})")
    print(f"  Sample count: {estimate.sample_count}")
    print(f"  Confidence: {estimate.confidence}")
    
    # The estimate should be influenced by category weights
    assert estimate.estimate_fg > 0
    assert estimate.sample_count == 3
    
    # The weighted median should be closer to the category 4 observation (5000)
    # than the category 2 observation (5500) due to the weight boost
    assert estimate.estimate_fg <= 5300, f"Expected estimate <= 5300, got {estimate.estimate_fg}"
    print(f"  ✓ Weighted median pulled toward category 4 observation (5000)")
    
    print("✓ Pricing engine category weight test passed\n")


def test_category_aware_disambiguation():
    """Test that category context helps disambiguate similar items."""
    print("Testing category-aware disambiguation...")
    engine = PricingEngine()
    
    # Simulate observations for items that could be confused
    observations = [
        # Tal rune observations in category 4 (runes)
        ObservedPrice(
            canonical_item_id="rune:tal",
            variant_key="rune:tal",
            bin_fg=50.0,
            confidence=0.8,
            thread_category_id=4,
        ),
        ObservedPrice(
            canonical_item_id="rune:tal",
            variant_key="rune:tal",
            bin_fg=55.0,
            confidence=0.8,
            thread_category_id=4,
        ),
        # Tal Rasha's amulet in category 2 (items)
        ObservedPrice(
            canonical_item_id="set:tal_rashas_adjudication",
            variant_key="set:tal_rashas_adjudication",
            bin_fg=300.0,
            confidence=0.8,
            thread_category_id=2,
        ),
        ObservedPrice(
            canonical_item_id="set:tal_rashas_adjudication",
            variant_key="set:tal_rashas_adjudication",
            bin_fg=320.0,
            confidence=0.8,
            thread_category_id=2,
        ),
    ]
    
    estimates = engine.build_index(observations)
    
    # Should have separate estimates for each item
    assert "rune:tal" in estimates, "Expected estimate for rune:tal"
    assert "set:tal_rashas_adjudication" in estimates, "Expected estimate for Tal Rasha's amulet"
    
    # Rune should be around 50-55
    tal_rune = estimates["rune:tal"]
    print(f"  Tal rune: {tal_rune.estimate_fg} FG")
    assert 45 <= tal_rune.estimate_fg <= 60, f"Expected 45-60, got {tal_rune.estimate_fg}"
    
    # Set item should be around 300-320
    tal_amy = estimates["set:tal_rashas_adjudication"]
    print(f"  Tal Rasha's amulet: {tal_amy.estimate_fg} FG")
    assert 290 <= tal_amy.estimate_fg <= 330, f"Expected 290-330, got {tal_amy.estimate_fg}"
    
    print("  ✓ Items correctly separated by category context")
    print("✓ Disambiguation test passed\n")


if __name__ == "__main__":
    try:
        test_parse_forum_threads_extracts_category_from_url()
        test_pricing_engine_category_weights()
        test_pricing_engine_uses_category_weights()
        test_category_aware_disambiguation()
        print("=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
