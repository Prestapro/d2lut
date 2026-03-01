"""Tests for sell_recommendations module."""

from __future__ import annotations

import pytest

from d2lut.overlay.premium_pricing import PremiumEstimate
from d2lut.overlay.sell_recommendations import (
    ALL_TAGS,
    CHECK_ROLL,
    KEEP,
    LOW_CONFIDENCE,
    NO_MARKET_DATA,
    SELL_NOW,
    RecommendedItem,
    build_recommendations,
    build_sell_recommendations_html,
    classify_recommendation,
    detect_duplicates,
    estimate_quick_sell_total,
    prioritize_items,
)
from d2lut.overlay.valuation_export import ValuationItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item(
    slot: int = 0,
    name: str = "Shako",
    canonical: str | None = "unique:harlequin_crest",
    price: float | None = 350.0,
    confidence: str | None = "high",
    samples: int | None = 12,
    has_price: bool = True,
) -> ValuationItem:
    return ValuationItem(
        slot_index=slot,
        item_name=name,
        canonical_item_id=canonical,
        price_fg=price,
        price_low_fg=(price * 0.8) if price else None,
        price_high_fg=(price * 1.2) if price else None,
        price_confidence=confidence,
        sample_count=samples,
        has_price=has_price,
    )


def _premium(tier: str = "average", pct: float = 50.0) -> PremiumEstimate:
    return PremiumEstimate(
        base_price_fg=100.0,
        premium_multiplier=1.0,
        premium_price_fg=100.0,
        roll_tier=tier,
        roll_percentile=pct,
    )


# ---------------------------------------------------------------------------
# classify_recommendation
# ---------------------------------------------------------------------------

class TestClassifyRecommendation:
    def test_no_market_data_when_no_price(self):
        it = _item(price=None, has_price=False)
        tag, reason = classify_recommendation(it)
        assert tag == NO_MARKET_DATA

    def test_sell_now_for_liquid_item(self):
        it = _item(price=200.0, confidence="high", samples=10)
        tag, _ = classify_recommendation(it)
        assert tag == SELL_NOW

    def test_check_roll_for_strong_premium(self):
        it = _item(price=200.0, confidence="high", samples=10)
        prem = _premium(tier="strong", pct=85.0)
        tag, _ = classify_recommendation(it, prem)
        assert tag == CHECK_ROLL

    def test_keep_for_perfect_roll(self):
        it = _item(price=500.0, confidence="high", samples=8)
        prem = _premium(tier="perfect", pct=100.0)
        tag, _ = classify_recommendation(it, prem)
        assert tag == KEEP

    def test_keep_for_near_perfect_roll(self):
        it = _item(price=500.0, confidence="high", samples=8)
        prem = _premium(tier="near_perfect", pct=97.0)
        tag, _ = classify_recommendation(it, prem)
        assert tag == KEEP

    def test_low_confidence_few_samples(self):
        it = _item(price=100.0, confidence="low", samples=2)
        tag, _ = classify_recommendation(it)
        assert tag == LOW_CONFIDENCE

    def test_sell_now_with_average_premium(self):
        it = _item(price=100.0, confidence="high", samples=10)
        prem = _premium(tier="average", pct=50.0)
        tag, _ = classify_recommendation(it, prem)
        assert tag == SELL_NOW

    def test_sell_now_with_weak_premium(self):
        it = _item(price=100.0, confidence="high", samples=10)
        prem = _premium(tier="weak", pct=20.0)
        tag, _ = classify_recommendation(it, prem)
        assert tag == SELL_NOW

    def test_all_tags_are_valid(self):
        """Every returned tag must be in ALL_TAGS."""
        cases = [
            (_item(price=None, has_price=False), None),
            (_item(price=50, confidence="low", samples=1), None),
            (_item(price=200, confidence="high", samples=10), None),
            (_item(price=200, confidence="high", samples=10), _premium("strong", 85)),
            (_item(price=200, confidence="high", samples=10), _premium("perfect", 100)),
        ]
        for it, prem in cases:
            tag, _ = classify_recommendation(it, prem)
            assert tag in ALL_TAGS, f"Unexpected tag: {tag}"


# ---------------------------------------------------------------------------
# detect_duplicates
# ---------------------------------------------------------------------------

class TestDetectDuplicates:
    def test_no_duplicates(self):
        items = [
            _item(slot=0, name="Shako", canonical="unique:harlequin_crest"),
            _item(slot=1, name="Oculus", canonical="unique:the_oculus"),
        ]
        dups = detect_duplicates(items)
        assert len(dups) == 0

    def test_detects_duplicates(self):
        items = [
            _item(slot=0, name="Shako", canonical="unique:harlequin_crest"),
            _item(slot=1, name="Shako", canonical="unique:harlequin_crest"),
            _item(slot=2, name="Oculus", canonical="unique:the_oculus"),
        ]
        dups = detect_duplicates(items)
        assert len(dups) == 1
        key = list(dups.keys())[0]
        assert len(dups[key]) == 2

    def test_groups_by_canonical_id(self):
        items = [
            _item(slot=0, name="Harlequin Crest", canonical="unique:harlequin_crest"),
            _item(slot=1, name="Shako", canonical="unique:harlequin_crest"),
        ]
        dups = detect_duplicates(items)
        assert len(dups) == 1

    def test_empty_list(self):
        assert detect_duplicates([]) == {}

    def test_uses_item_name_when_no_canonical(self):
        items = [
            _item(slot=0, name="Mystery Item", canonical=None),
            _item(slot=1, name="mystery item", canonical=None),
        ]
        dups = detect_duplicates(items)
        assert len(dups) == 1


# ---------------------------------------------------------------------------
# estimate_quick_sell_total
# ---------------------------------------------------------------------------

class TestEstimateQuickSellTotal:
    def test_sums_sell_now_only(self):
        recs = [
            RecommendedItem(item=_item(slot=0, price=100), recommendation=SELL_NOW),
            RecommendedItem(item=_item(slot=1, price=200), recommendation=SELL_NOW),
            RecommendedItem(item=_item(slot=2, price=500), recommendation=KEEP),
            RecommendedItem(item=_item(slot=3, price=None, has_price=False), recommendation=NO_MARKET_DATA),
        ]
        assert estimate_quick_sell_total(recs) == 300.0

    def test_empty_list(self):
        assert estimate_quick_sell_total([]) == 0.0

    def test_no_sell_now_items(self):
        recs = [
            RecommendedItem(item=_item(slot=0, price=500), recommendation=KEEP),
        ]
        assert estimate_quick_sell_total(recs) == 0.0


# ---------------------------------------------------------------------------
# prioritize_items
# ---------------------------------------------------------------------------

class TestPrioritizeItems:
    def test_sell_now_before_check_roll(self):
        recs = [
            RecommendedItem(item=_item(slot=0, price=100), recommendation=CHECK_ROLL),
            RecommendedItem(item=_item(slot=1, price=200), recommendation=SELL_NOW),
        ]
        ordered = prioritize_items(recs)
        assert ordered[0].recommendation == SELL_NOW
        assert ordered[1].recommendation == CHECK_ROLL

    def test_full_ordering(self):
        recs = [
            RecommendedItem(item=_item(slot=0, price=None, has_price=False), recommendation=NO_MARKET_DATA),
            RecommendedItem(item=_item(slot=1, price=50), recommendation=LOW_CONFIDENCE),
            RecommendedItem(item=_item(slot=2, price=500), recommendation=KEEP),
            RecommendedItem(item=_item(slot=3, price=100), recommendation=CHECK_ROLL),
            RecommendedItem(item=_item(slot=4, price=200), recommendation=SELL_NOW),
        ]
        ordered = prioritize_items(recs)
        tags = [r.recommendation for r in ordered]
        assert tags == [SELL_NOW, CHECK_ROLL, KEEP, LOW_CONFIDENCE, NO_MARKET_DATA]

    def test_within_tag_higher_price_first(self):
        recs = [
            RecommendedItem(item=_item(slot=0, price=50), recommendation=SELL_NOW),
            RecommendedItem(item=_item(slot=1, price=300), recommendation=SELL_NOW),
            RecommendedItem(item=_item(slot=2, price=150), recommendation=SELL_NOW),
        ]
        ordered = prioritize_items(recs)
        prices = [r.item.price_fg for r in ordered]
        assert prices == [300, 150, 50]

    def test_empty_list(self):
        assert prioritize_items([]) == []


# ---------------------------------------------------------------------------
# build_recommendations (integration)
# ---------------------------------------------------------------------------

class TestBuildRecommendations:
    def test_basic_flow(self):
        items = [
            _item(slot=0, name="Shako", price=350, confidence="high", samples=10),
            _item(slot=1, name="Ber Rune", price=2000, confidence="high", samples=20),
            _item(slot=2, name="Unknown Rare", price=None, has_price=False),
        ]
        recs = build_recommendations(items)
        assert len(recs) == 3
        tags = {r.recommendation for r in recs}
        assert SELL_NOW in tags
        assert NO_MARKET_DATA in tags

    def test_duplicates_flagged(self):
        items = [
            _item(slot=0, name="Shako", canonical="unique:harlequin_crest", price=350),
            _item(slot=1, name="Shako", canonical="unique:harlequin_crest", price=350),
        ]
        recs = build_recommendations(items)
        assert all(r.is_duplicate for r in recs)
        assert all(r.duplicate_count == 2 for r in recs)

    def test_premium_integration(self):
        items = [_item(slot=0, name="Grief", price=1000, confidence="high", samples=15)]
        premiums = {0: _premium(tier="perfect", pct=100.0)}
        recs = build_recommendations(items, premiums)
        assert recs[0].recommendation == KEEP

    def test_empty_inventory(self):
        recs = build_recommendations([])
        assert recs == []

    def test_all_no_data(self):
        items = [
            _item(slot=i, name=f"Item{i}", price=None, has_price=False)
            for i in range(5)
        ]
        recs = build_recommendations(items)
        assert all(r.recommendation == NO_MARKET_DATA for r in recs)

    def test_mixed_tags(self):
        items = [
            _item(slot=0, price=500, confidence="high", samples=10),
            _item(slot=1, price=50, confidence="low", samples=1),
            _item(slot=2, price=None, has_price=False),
        ]
        premiums = {0: _premium(tier="strong", pct=85)}
        recs = build_recommendations(items, premiums)
        tags = {r.recommendation for r in recs}
        assert CHECK_ROLL in tags
        assert LOW_CONFIDENCE in tags
        assert NO_MARKET_DATA in tags

    def test_output_is_sorted(self):
        items = [
            _item(slot=0, price=None, has_price=False),
            _item(slot=1, price=200, confidence="high", samples=10),
        ]
        recs = build_recommendations(items)
        assert recs[0].recommendation == SELL_NOW
        assert recs[-1].recommendation == NO_MARKET_DATA


# ---------------------------------------------------------------------------
# build_sell_recommendations_html
# ---------------------------------------------------------------------------

class TestBuildSellRecommendationsHtml:
    def test_produces_valid_html(self):
        items = [_item(slot=0, price=100)]
        recs = build_recommendations(items)
        html_str = build_sell_recommendations_html(recs)
        assert html_str.startswith("<!DOCTYPE html>")
        assert "</html>" in html_str

    def test_contains_item_name(self):
        items = [_item(slot=0, name="Shako", price=350)]
        recs = build_recommendations(items)
        html_str = build_sell_recommendations_html(recs)
        assert "Shako" in html_str

    def test_contains_quick_sell_total(self):
        items = [
            _item(slot=0, price=100, confidence="high", samples=10),
            _item(slot=1, price=200, confidence="high", samples=10),
        ]
        recs = build_recommendations(items)
        html_str = build_sell_recommendations_html(recs)
        assert "300" in html_str

    def test_custom_title(self):
        recs = build_recommendations([_item(slot=0, price=100)])
        html_str = build_sell_recommendations_html(recs, title="My Sell List")
        assert "My Sell List" in html_str

    def test_empty_items(self):
        html_str = build_sell_recommendations_html([])
        assert "<!DOCTYPE html>" in html_str
        assert "0" in html_str

    def test_tag_labels_present(self):
        items = [
            _item(slot=0, price=200, confidence="high", samples=10),
            _item(slot=1, price=None, has_price=False),
        ]
        recs = build_recommendations(items)
        html_str = build_sell_recommendations_html(recs)
        assert "Sell now" in html_str
        assert "No market data" in html_str

    def test_self_contained_no_external_deps(self):
        recs = build_recommendations([_item(slot=0, price=100)])
        html_str = build_sell_recommendations_html(recs)
        # No external CSS/JS references
        assert "http" not in html_str.split("<style>")[0].split("</head>")[0].replace("<!DOCTYPE html>", "").replace('<html lang="en">', "").replace('<meta charset="utf-8">', "")
