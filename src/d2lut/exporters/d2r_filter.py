from __future__ import annotations

from d2lut.models import PriceEstimate


class D2RFilterExporter:
    """Export value tiers for D2R built-in loot filter rules.

    Note: exact `fg` suffix injection into item labels is not supported by the
    built-in filter. This exporter is for tiered visibility/highlighting only.
    """

    def export(self, price_index: dict[str, PriceEstimate]) -> str:
        # Placeholder format until target filter syntax template is finalized.
        lines = ["// d2lut generated tiers"]
        for key, est in sorted(price_index.items(), key=lambda kv: kv[1].estimate_fg, reverse=True):
            lines.append(f"// {key}: ~{est.estimate_fg:.0f} fg ({est.confidence})")
        return "\n".join(lines) + "\n"

