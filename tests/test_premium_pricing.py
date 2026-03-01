"""Tests for the premium pricing layer (roll scoring, tier classification, premium calculation)."""

import pytest
from d2lut.overlay.premium_pricing import (
    DEFAULT_TIER_MULTIPLIERS,
    DEFAULT_TIER_THRESHOLDS,
    PremiumEstimate,
    ROLL_RANGES,
    RollDetail,
    RollRange,
    classify_tier,
    compute_premium,
    score_stat,
)


# ---------------------------------------------------------------------------
# score_stat
# ---------------------------------------------------------------------------

class TestScoreStat:
    def test_min_roll_is_zero(self):
        rr = RollRange("attr", 10, 20)
        assert score_stat(10, rr) == 0.0

    def test_max_roll_is_100(self):
        rr = RollRange("attr", 10, 20)
        assert score_stat(20, rr) == 100.0

    def test_midpoint(self):
        rr = RollRange("attr", 10, 20)
        assert score_stat(15, rr) == 50.0

    def test_below_min_clamps_to_zero(self):
        rr = RollRange("attr", 10, 20)
        assert score_stat(5, rr) == 0.0

    def test_above_max_clamps_to_100(self):
        rr = RollRange("attr", 10, 20)
        assert score_stat(25, rr) == 100.0

    def test_zero_width_range_returns_100(self):
        rr = RollRange("fixed", 5, 5)
        assert score_stat(5, rr) == 100.0

    def test_fractional_value(self):
        rr = RollRange("res", 0, 100)
        assert score_stat(75, rr) == 75.0


# ---------------------------------------------------------------------------
# classify_tier
# ---------------------------------------------------------------------------

class TestClassifyTier:
    def test_perfect(self):
        assert classify_tier(100.0) == "perfect"

    def test_near_perfect(self):
        assert classify_tier(95.0) == "near_perfect"
        assert classify_tier(99.9) == "near_perfect"

    def test_strong(self):
        assert classify_tier(80.0) == "strong"
        assert classify_tier(94.9) == "strong"

    def test_average(self):
        assert classify_tier(50.0) == "average"
        assert classify_tier(79.9) == "average"

    def test_weak(self):
        assert classify_tier(0.0) == "weak"
        assert classify_tier(49.9) == "weak"

    def test_custom_thresholds(self):
        custom = {"perfect": 99.0, "near_perfect": 90.0, "strong": 70.0, "average": 40.0}
        assert classify_tier(95.0, custom) == "near_perfect"
        assert classify_tier(99.0, custom) == "perfect"


# ---------------------------------------------------------------------------
# compute_premium
# ---------------------------------------------------------------------------

class TestComputePremium:
    def test_perfect_torch(self):
        result = compute_premium(500.0, "torch", {"attributes": 20, "resistances": 20})
        assert result is not None
        assert result.roll_tier == "perfect"
        assert result.roll_percentile == 100.0
        assert result.premium_multiplier == 2.5
        assert result.premium_price_fg == 1250.0
        assert result.confidence_note == ""
        assert len(result.roll_details) == 2

    def test_min_roll_torch(self):
        result = compute_premium(500.0, "torch", {"attributes": 10, "resistances": 10})
        assert result is not None
        assert result.roll_tier == "weak"
        assert result.roll_percentile == 0.0
        assert result.premium_multiplier == 1.0
        assert result.premium_price_fg == 500.0

    def test_near_perfect_torch(self):
        # 19/20 -> 90% and 100% -> avg 95%
        result = compute_premium(500.0, "torch", {"attributes": 19, "resistances": 20})
        assert result is not None
        assert result.roll_tier == "near_perfect"
        assert result.premium_multiplier == 1.8

    def test_strong_torch(self):
        # 18/18 -> 80% each -> avg 80%
        result = compute_premium(500.0, "torch", {"attributes": 18, "resistances": 18})
        assert result is not None
        assert result.roll_tier == "strong"
        assert result.premium_multiplier == 1.3

    def test_average_torch(self):
        # 15/15 -> 50% each -> avg 50%
        result = compute_premium(500.0, "torch", {"attributes": 15, "resistances": 15})
        assert result is not None
        assert result.roll_tier == "average"
        assert result.premium_multiplier == 1.0

    def test_unknown_item_class_returns_none(self):
        result = compute_premium(100.0, "nonexistent_item", {"x": 5})
        assert result is None

    def test_no_matching_stats_returns_none(self):
        result = compute_premium(100.0, "torch", {"unrelated_stat": 15})
        assert result is None

    def test_partial_stats_adds_confidence_note(self):
        result = compute_premium(500.0, "torch", {"attributes": 20})
        assert result is not None
        assert "Partial roll data" in result.confidence_note
        assert "resistances" in result.confidence_note
        assert len(result.roll_details) == 1

    def test_grief_perfect(self):
        result = compute_premium(1000.0, "grief", {"damage": 400})
        assert result is not None
        assert result.roll_tier == "perfect"
        assert result.premium_price_fg == 2500.0

    def test_hoto_strong(self):
        # 38/40 -> (38-30)/(40-30) = 80%
        result = compute_premium(200.0, "hoto", {"all_resistances": 38})
        assert result is not None
        assert result.roll_tier == "strong"
        assert result.premium_multiplier == 1.3

    def test_facet_perfect(self):
        result = compute_premium(300.0, "facet", {"enemy_res_reduction": 5, "damage_bonus": 5})
        assert result is not None
        assert result.roll_tier == "perfect"

    def test_cta_near_perfect(self):
        # 6 BO -> (6-1)/(6-1) = 100% -> perfect
        result = compute_premium(150.0, "cta", {"battle_orders": 6})
        assert result is not None
        assert result.roll_tier == "perfect"
        # 5 BO -> (5-1)/(6-1) = 80% -> strong
        result2 = compute_premium(150.0, "cta", {"battle_orders": 5})
        assert result2 is not None
        assert result2.roll_tier == "strong"

    def test_anni_all_stats(self):
        result = compute_premium(800.0, "anni", {
            "attributes": 20, "resistances": 20, "experience": 10,
        })
        assert result is not None
        assert result.roll_tier == "perfect"
        assert len(result.roll_details) == 3

    def test_worst_scoring_mode(self):
        # 20 attr (100%) + 10 res (0%) -> worst = 0%
        result = compute_premium(
            500.0, "torch",
            {"attributes": 20, "resistances": 10},
            scoring_mode="worst",
        )
        assert result is not None
        assert result.roll_tier == "weak"
        assert result.roll_percentile == 0.0

    def test_custom_multipliers(self):
        custom_mults = {"perfect": 5.0, "near_perfect": 3.0, "strong": 2.0, "average": 1.0, "weak": 0.5}
        result = compute_premium(
            100.0, "torch",
            {"attributes": 20, "resistances": 20},
            tier_multipliers=custom_mults,
        )
        assert result is not None
        assert result.premium_multiplier == 5.0
        assert result.premium_price_fg == 500.0

    def test_custom_roll_ranges(self):
        custom_ranges = {
            "custom_item": [RollRange("power", 1, 10)],
        }
        result = compute_premium(
            100.0, "custom_item",
            {"power": 10},
            roll_ranges=custom_ranges,
        )
        assert result is not None
        assert result.roll_tier == "perfect"


# ---------------------------------------------------------------------------
# Roll range definitions sanity checks
# ---------------------------------------------------------------------------

class TestRollRangeDefinitions:
    def test_all_ranges_have_valid_bounds(self):
        for item_class, ranges in ROLL_RANGES.items():
            for rr in ranges:
                assert rr.max_val >= rr.min_val, (
                    f"{item_class}.{rr.stat_name}: max ({rr.max_val}) < min ({rr.min_val})"
                )

    def test_key_item_classes_present(self):
        expected = {"torch", "anni", "cta", "hoto", "grief", "facet"}
        assert expected.issubset(ROLL_RANGES.keys())

    def test_default_multipliers_cover_all_tiers(self):
        for tier in ("perfect", "near_perfect", "strong", "average", "weak"):
            assert tier in DEFAULT_TIER_MULTIPLIERS

    def test_default_thresholds_descending(self):
        t = DEFAULT_TIER_THRESHOLDS
        assert t["perfect"] > t["near_perfect"] > t["strong"] > t["average"]
