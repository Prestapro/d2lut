from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import median

from d2lut.models import ObservedPrice, PriceEstimate


def _weighted_median(values: list[tuple[float, float]]) -> float:
    """Weighted median over (value, weight); falls back to plain median if needed."""
    if not values:
        raise ValueError("empty values")
    clean = [(float(v), max(0.0, float(w))) for v, w in values if v is not None]
    if not clean:
        raise ValueError("no numeric values")
    total_w = sum(w for _, w in clean)
    if total_w <= 0:
        return float(median(v for v, _ in clean))
    clean.sort(key=lambda x: x[0])
    half = total_w / 2.0
    acc = 0.0
    for v, w in clean:
        acc += w
        if acc >= half:
            return float(v)
    return float(clean[-1][0])


class PricingEngine:
    """Simple baseline estimator.

    Uses median of available signals. Real implementation should include:
    - recency weighting
    - source confidence weighting
    - roll-sensitive variants
    - category-aware weighting for disambiguation
    """

    def build_index(self, observations: list[ObservedPrice]) -> dict[str, PriceEstimate]:
        buckets: dict[str, list[tuple[float, float, int | None]]] = defaultdict(list)

        for obs in observations:
            value = obs.sold_fg or obs.bin_fg or obs.ask_fg
            if value and value > 0:
                base_weight = max(0.01, float(getattr(obs, "confidence", 0.0) or 0.0))
                
                # Apply category-aware weight adjustments
                category_id = getattr(obs, "thread_category_id", None)
                category_weight = self._calculate_category_weight(obs.variant_key, category_id)
                
                final_weight = base_weight * category_weight
                buckets[obs.variant_key].append((float(value), final_weight, category_id))

        now = datetime.now(timezone.utc)
        result: dict[str, PriceEstimate] = {}
        for variant_key, values in buckets.items():
            raw_vals = [v for v, _w, _c in values]
            weighted_vals = [(v, w) for v, w, _c in values]
            m = _weighted_median(weighted_vals)
            lo = float(min(raw_vals))
            hi = float(max(raw_vals))
            total_w = sum(w for _v, w, _c in values)
            avg_w = total_w / max(1, len(values))
            conf_label = "low"
            if len(values) >= 5 and avg_w >= 0.45:
                conf_label = "high"
            elif len(values) >= 3 and avg_w >= 0.25:
                conf_label = "medium"
            result[variant_key] = PriceEstimate(
                variant_key=variant_key,
                estimate_fg=m,
                range_low_fg=lo,
                range_high_fg=hi,
                confidence=conf_label,
                sample_count=len(values),
                last_updated=now,
            )
        return result

    def _calculate_category_weight(self, variant_key: str, category_id: int | None) -> float:
        """Calculate category-specific weight multiplier for improved disambiguation.
        
        Category IDs on d2jsp (common patterns):
        - c=2: Often weapons/armor
        - c=3: Often charms/jewels
        - c=4: Often runes/keys
        - c=5: Often LLD (Low Level Dueling) items
        
        This helps disambiguate items like:
        - Runes vs other items with similar names
        - Charms vs other items
        - LLD items vs regular items
        """
        if category_id is None:
            # No category context - use neutral weight
            return 1.0
        
        # Extract item type from variant_key
        item_type = variant_key.split(":")[0] if ":" in variant_key else ""
        
        # Category 4: Boost runes/keys/tokens/essences
        if category_id == 4:
            if item_type in ("rune", "key", "keyset", "token", "essence"):
                return 1.3  # 30% boost for category-matched items
            else:
                return 0.7  # Reduce weight for non-matching items
        
        # Category 3: Boost charms/jewels/facets
        if category_id == 3:
            if item_type in ("charm", "jewel"):
                return 1.3
            else:
                return 0.7
        
        # Category 5: Boost LLD items (identified by variant patterns)
        if category_id == 5:
            # LLD items often have specific level requirements or are in specific categories
            # For now, give slight boost to all items in this category
            return 1.2
        
        # Category 2: Weapons/armor/bases
        if category_id == 2:
            if item_type in ("base", "unique", "set"):
                return 1.2
            else:
                return 0.8
        
        # Default: neutral weight for other categories
        return 1.0
