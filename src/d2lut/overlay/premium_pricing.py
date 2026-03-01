"""Premium pricing layer for top-value item classes.

Scores parsed item rolls as a percentile within the possible range,
classifies into tiers (perfect / near-perfect / strong / average / weak),
and calculates a premium uplift multiplier on top of the baseline price.

Roll ranges are game-data constants and can be extended or overridden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RollRange:
    """Min/max range for a single stat on an item class."""
    stat_name: str
    min_val: float
    max_val: float


@dataclass
class RollDetail:
    """Per-stat breakdown of a roll score."""
    stat_name: str
    actual: float
    min_val: float
    max_val: float
    percentile: float  # 0-100


@dataclass
class PremiumEstimate:
    """Result of premium pricing analysis."""
    base_price_fg: float
    premium_multiplier: float
    premium_price_fg: float
    roll_tier: str  # perfect, near_perfect, strong, average, weak
    roll_percentile: float  # 0-100 (averaged across stats)
    roll_details: list[RollDetail] = field(default_factory=list)
    confidence_note: str = ""


# ---------------------------------------------------------------------------
# Default tier thresholds and multipliers (configurable)
# ---------------------------------------------------------------------------

DEFAULT_TIER_THRESHOLDS: dict[str, float] = {
    "perfect": 100.0,
    "near_perfect": 95.0,
    "strong": 80.0,
    "average": 50.0,
    # anything below average is "weak"
}

DEFAULT_TIER_MULTIPLIERS: dict[str, float] = {
    "perfect": 2.5,
    "near_perfect": 1.8,
    "strong": 1.3,
    "average": 1.0,
    "weak": 1.0,
}


# ---------------------------------------------------------------------------
# Roll range definitions (game-data constants)
# ---------------------------------------------------------------------------

# Each key is a canonical item class identifier.
# Values are lists of RollRange for the variable stats on that item.

ROLL_RANGES: dict[str, list[RollRange]] = {
    # Hellfire Torch: +3 class skills (fixed), 10-20 attributes, 10-20 resistances
    "torch": [
        RollRange("attributes", 10, 20),
        RollRange("resistances", 10, 20),
    ],
    # Annihilus: +1 skills (fixed), 10-20 attributes, 10-20 resistances, 5-10 experience
    "anni": [
        RollRange("attributes", 10, 20),
        RollRange("resistances", 10, 20),
        RollRange("experience", 5, 10),
    ],
    # Call to Arms (CTA): +1-6 Battle Orders
    "cta": [
        RollRange("battle_orders", 1, 6),
    ],
    # Heart of the Oak (HOTO): +30-40 all resistances
    "hoto": [
        RollRange("all_resistances", 30, 40),
    ],
    # Grief: +340-400 damage
    "grief": [
        RollRange("damage", 340, 400),
    ],
    # Infinity: -45 to -55% enemy lightning resistance (higher magnitude = better)
    "infinity": [
        RollRange("conviction_aura", 12, 17),
    ],
    # Enigma: no variable combat stats that drive premium (str/life are minor)
    # Include +750-775 defense for completeness
    "enigma": [
        RollRange("strength", 0, 1),  # +0.75 per level, effectively fixed
    ],
    # Rainbow Facets: -3 to -5% enemy res, +3 to +5% damage
    "facet": [
        RollRange("enemy_res_reduction", 3, 5),
        RollRange("damage_bonus", 3, 5),
    ],
    # Skillers (grand charms): +1 skill tree (fixed), 0-45 life
    "skiller": [
        RollRange("life", 0, 45),
    ],
    # Small charms: 0-20 life, 0-11 single res, 0-5 all res (varies by combo)
    # Use life + single_res as representative variable stats
    "small_charm": [
        RollRange("life", 0, 20),
        RollRange("single_resistance", 0, 11),
    ],
    # Jewels: highly variable; use common PvP stats
    "jewel": [
        RollRange("ed", 0, 40),
        RollRange("ias", 0, 15),
    ],
    # Arachnid Mesh: +1 skills (fixed), 10-20% slow target
    "arachnid": [
        RollRange("slow_target", 10, 20),
    ],
    # Mara's Kaleidoscope: +20-30 all resistances
    "maras": [
        RollRange("all_resistances", 20, 30),
    ],
}


# ---------------------------------------------------------------------------
# Core scoring logic
# ---------------------------------------------------------------------------

def score_stat(actual: float, roll: RollRange) -> float:
    """Return a 0-100 percentile for a single stat within its roll range.

    Returns 100 if the range is zero-width (fixed stat).
    Clamps to [0, 100].
    """
    span = roll.max_val - roll.min_val
    if span <= 0:
        return 100.0
    raw = (actual - roll.min_val) / span * 100.0
    return max(0.0, min(100.0, raw))


def classify_tier(
    percentile: float,
    thresholds: dict[str, float] | None = None,
) -> str:
    """Classify a percentile into a tier string."""
    t = thresholds or DEFAULT_TIER_THRESHOLDS
    if percentile >= t["perfect"]:
        return "perfect"
    if percentile >= t["near_perfect"]:
        return "near_perfect"
    if percentile >= t["strong"]:
        return "strong"
    if percentile >= t["average"]:
        return "average"
    return "weak"


def compute_premium(
    base_price_fg: float,
    item_class: str,
    stat_values: dict[str, float],
    *,
    roll_ranges: dict[str, list[RollRange]] | None = None,
    tier_thresholds: dict[str, float] | None = None,
    tier_multipliers: dict[str, float] | None = None,
    scoring_mode: str = "average",
) -> PremiumEstimate | None:
    """Score an item's rolls and compute premium pricing.

    Parameters
    ----------
    base_price_fg:
        Baseline market price in FG.
    item_class:
        Key into the roll ranges table (e.g. ``"torch"``, ``"grief"``).
    stat_values:
        Mapping of stat name -> actual rolled value.
    roll_ranges:
        Override roll range definitions (defaults to ``ROLL_RANGES``).
    tier_thresholds:
        Override tier percentile thresholds.
    tier_multipliers:
        Override tier multiplier table.
    scoring_mode:
        ``"average"`` (mean of per-stat percentiles) or ``"worst"``
        (conservative: use lowest per-stat percentile).

    Returns ``None`` if *item_class* is not in the roll ranges table or
    no matching stats are found.
    """
    ranges = (roll_ranges or ROLL_RANGES).get(item_class)
    if not ranges:
        return None

    details: list[RollDetail] = []
    for rr in ranges:
        if rr.stat_name not in stat_values:
            continue
        actual = stat_values[rr.stat_name]
        pct = score_stat(actual, rr)
        details.append(RollDetail(
            stat_name=rr.stat_name,
            actual=actual,
            min_val=rr.min_val,
            max_val=rr.max_val,
            percentile=pct,
        ))

    if not details:
        return None

    if scoring_mode == "worst":
        overall_pct = min(d.percentile for d in details)
    else:
        overall_pct = sum(d.percentile for d in details) / len(details)

    tier = classify_tier(overall_pct, tier_thresholds)
    mults = tier_multipliers or DEFAULT_TIER_MULTIPLIERS
    multiplier = mults.get(tier, 1.0)
    premium_fg = round(base_price_fg * multiplier, 2)

    # Confidence note
    note = ""
    if len(details) < len(ranges):
        missing = [r.stat_name for r in ranges if r.stat_name not in stat_values]
        note = f"Partial roll data (missing: {', '.join(missing)}); score based on {len(details)}/{len(ranges)} stats."

    return PremiumEstimate(
        base_price_fg=base_price_fg,
        premium_multiplier=multiplier,
        premium_price_fg=premium_fg,
        roll_tier=tier,
        roll_percentile=round(overall_pct, 2),
        roll_details=details,
        confidence_note=note,
    )
