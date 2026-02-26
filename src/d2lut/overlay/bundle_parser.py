"""Bundle parser for overlay system.

Detects known item bundles (runeword component sets, set item collections)
from OCR-parsed item lists and provides bundle-level pricing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from d2lut.overlay.price_lookup import PriceLookupEngine


@dataclass(frozen=True)
class BundleDefinition:
    """Definition of a known item bundle."""

    bundle_name: str
    bundle_type: str  # "rune", "set", "custom"
    required_items: tuple[str, ...]  # normalised lowercase item names (duplicates allowed)


@dataclass
class DetectedBundle:
    """A bundle detected from a list of items."""

    bundle_name: str
    bundle_type: str
    items: list[str]  # the matched item strings (original casing)
    confidence: float = 1.0


@dataclass
class BundleResult:
    """Result of bundle detection on an item list."""

    bundles: list[DetectedBundle] = field(default_factory=list)
    partial_bundles: list[DetectedBundle] = field(default_factory=list)
    remaining_items: list[str] = field(default_factory=list)
    total_bundle_value: float | None = None


# ---------------------------------------------------------------------------
# Built-in bundle definitions
# ---------------------------------------------------------------------------

# Common runeword component sets (runes needed to make the runeword)
_RUNE_BUNDLES: list[BundleDefinition] = [
    BundleDefinition("Enigma", "rune", ("jah", "ith", "ber")),
    BundleDefinition("Infinity", "rune", ("ber", "mal", "ber", "ist")),
    BundleDefinition("Call to Arms", "rune", ("amn", "ral", "mal", "ist", "ohm")),
    BundleDefinition("Heart of the Oak", "rune", ("ko", "vex", "pul", "thul")),
    BundleDefinition("Grief", "rune", ("eth", "tir", "lo", "mal", "ral")),
    BundleDefinition("Breath of the Dying", "rune", ("vex", "hel", "el", "eld", "zod", "eth")),
    BundleDefinition("Spirit", "rune", ("tal", "thul", "ort", "amn")),
    BundleDefinition("Insight", "rune", ("ral", "tir", "tal", "sol")),
    BundleDefinition("Chains of Honor", "rune", ("dol", "um", "ber", "ist")),
    BundleDefinition("Fortitude", "rune", ("el", "sol", "dol", "lo")),
    BundleDefinition("Last Wish", "rune", ("jah", "mal", "jah", "sur", "jah", "ber")),
    BundleDefinition("Faith", "rune", ("ohm", "jah", "lem", "eld")),
    BundleDefinition("Exile", "rune", ("vex", "ohm", "ist", "dol")),
    BundleDefinition("Phoenix", "rune", ("vex", "vex", "lo", "jah")),
    BundleDefinition("Doom", "rune", ("hel", "ohm", "um", "lo", "cham")),
    BundleDefinition("Dream", "rune", ("io", "jah", "pul")),
]

# Common set item collections (full sets)
_SET_BUNDLES: list[BundleDefinition] = [
    BundleDefinition(
        "Tal Rasha's Wrappings",
        "set",
        (
            "tal rasha's adjudication",
            "tal rasha's fine-spun cloth",
            "tal rasha's guardianship",
            "tal rasha's horadric crest",
            "tal rasha's lidless eye",
        ),
    ),
    BundleDefinition(
        "Immortal King",
        "set",
        (
            "immortal king's stone crusher",
            "immortal king's will",
            "immortal king's soul cage",
            "immortal king's detail",
            "immortal king's forge",
            "immortal king's pillar",
        ),
    ),
    BundleDefinition(
        "Trang-Oul's Avatar",
        "set",
        (
            "trang-oul's claws",
            "trang-oul's guise",
            "trang-oul's scales",
            "trang-oul's girth",
            "trang-oul's wing",
        ),
    ),
    BundleDefinition(
        "Organ Set",
        "set",
        ("mephisto's brain", "diablo's horn", "baal's eye"),
    ),
    BundleDefinition(
        "Key Set",
        "set",
        ("key of terror", "key of hate", "key of destruction"),
    ),
    BundleDefinition(
        "Natalya's Odium",
        "set",
        (
            "natalya's mark",
            "natalya's shadow",
            "natalya's totem",
            "natalya's soul",
        ),
    ),
    BundleDefinition(
        "Griswold's Legacy",
        "set",
        (
            "griswold's heart",
            "griswold's honor",
            "griswold's redemption",
            "griswold's valor",
        ),
    ),
    BundleDefinition(
        "M'avina's Battle Hymn",
        "set",
        (
            "m'avina's caster",
            "m'avina's embrace",
            "m'avina's icy clutch",
            "m'avina's tenet",
            "m'avina's true sight",
        ),
    ),
    BundleDefinition(
        "Aldur's Watchtower",
        "set",
        (
            "aldur's stony gaze",
            "aldur's deception",
            "aldur's gauntlet",
            "aldur's advance",
        ),
    ),
]


class BundleParser:
    """Detects known bundles from item lists and provides bundle pricing.

    Works with OCR-parsed item names (strings), not raw market text.
    Handles OCR variants like "Ber Rune" or "ber rune" by stripping
    common suffixes before matching.
    """

    # Suffixes that OCR may append to item names (checked in order)
    _OCR_SUFFIXES = (" rune",)

    # Minimum fraction of required items that must be present for a
    # partial bundle match (e.g. 0.5 = at least half).
    PARTIAL_THRESHOLD = 0.5

    def __init__(self) -> None:
        self._definitions: list[BundleDefinition] = []
        # Load built-in definitions
        self._definitions.extend(_RUNE_BUNDLES)
        self._definitions.extend(_SET_BUNDLES)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_bundle_definition(self, definition: BundleDefinition) -> None:
        """Register an additional bundle definition."""
        self._definitions.append(definition)

    def detect_bundles(
        self,
        items: list[str],
        *,
        include_partial: bool = False,
    ) -> BundleResult:
        """Detect known bundles from a list of item name strings.

        Each item can only belong to one bundle (first match wins,
        definitions are checked largest-required-set first so bigger
        bundles take priority).

        Args:
            items: Item name strings (e.g. from OCR or inventory list).
            include_partial: When True, also report partial matches
                (bundles where >= PARTIAL_THRESHOLD of items are present).

        Returns:
            BundleResult with detected bundles, partial bundles, and
            leftover items.
        """
        if not items:
            return BundleResult()

        # Normalise once — strip OCR suffixes for matching
        norm_items = [self._normalise_for_match(s) for s in items]
        used_indices: set[int] = set()
        detected: list[DetectedBundle] = []

        # Check larger bundles first so they take priority
        sorted_defs = sorted(
            self._definitions,
            key=lambda d: len(d.required_items),
            reverse=True,
        )

        for defn in sorted_defs:
            match_indices = self._match_bundle(defn, norm_items, used_indices)
            if match_indices is not None:
                matched_originals = [items[i] for i in match_indices]
                detected.append(
                    DetectedBundle(
                        bundle_name=defn.bundle_name,
                        bundle_type=defn.bundle_type,
                        items=matched_originals,
                        confidence=1.0,
                    )
                )
                used_indices.update(match_indices)

        # Partial bundle detection (opt-in)
        partial: list[DetectedBundle] = []
        if include_partial:
            for defn in sorted_defs:
                # Skip definitions already fully matched
                if any(d.bundle_name == defn.bundle_name for d in detected):
                    continue
                part_indices, total_req = self._match_partial(
                    defn, norm_items, used_indices
                )
                if part_indices and total_req > 0:
                    frac = len(part_indices) / total_req
                    if frac >= self.PARTIAL_THRESHOLD and frac < 1.0:
                        matched_originals = [items[i] for i in part_indices]
                        partial.append(
                            DetectedBundle(
                                bundle_name=defn.bundle_name,
                                bundle_type=defn.bundle_type,
                                items=matched_originals,
                                confidence=round(frac, 2),
                            )
                        )

        remaining = [items[i] for i in range(len(items)) if i not in used_indices]

        return BundleResult(
            bundles=detected,
            partial_bundles=partial,
            remaining_items=remaining,
        )

    def get_bundle_price(
        self,
        bundle: DetectedBundle,
        price_engine: PriceLookupEngine | None = None,
    ) -> float | None:
        """Calculate bundle price by summing individual item prices.

        Args:
            bundle: A detected bundle.
            price_engine: Optional PriceLookupEngine for DB lookups.

        Returns:
            Total FG value or None if pricing unavailable.
        """
        if price_engine is None:
            return None

        total = 0.0
        for item_name in bundle.items:
            est = price_engine.get_price(item_name.strip().lower())
            if est is None:
                # Can't price the full bundle if any component is missing
                return None
            total += est.estimate_fg

        return total

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _normalise_for_match(cls, raw: str) -> str:
        """Lowercase, strip whitespace, and remove common OCR suffixes."""
        text = raw.strip().lower()
        for suffix in cls._OCR_SUFFIXES:
            if text.endswith(suffix):
                text = text[: -len(suffix)]
                break  # only strip one suffix
        return text

    @staticmethod
    def _match_bundle(
        defn: BundleDefinition,
        norm_items: list[str],
        used: set[int],
    ) -> list[int] | None:
        """Try to match a bundle definition against available items.

        Supports duplicate required items (e.g. Infinity needs 2× ber).
        Returns list of matched indices or None if not all required items
        are present.
        """
        matched: list[int] = []

        for req in defn.required_items:
            found = False
            for idx, norm in enumerate(norm_items):
                if idx in used or idx in matched:
                    continue
                if norm == req:
                    matched.append(idx)
                    found = True
                    break
            if not found:
                return None

        return matched

    @staticmethod
    def _match_partial(
        defn: BundleDefinition,
        norm_items: list[str],
        used: set[int],
    ) -> tuple[list[int], int]:
        """Match as many required items as possible (greedy).

        Returns (matched_indices, total_required_count).
        """
        matched: list[int] = []
        for req in defn.required_items:
            for idx, norm in enumerate(norm_items):
                if idx in used or idx in matched:
                    continue
                if norm == req:
                    matched.append(idx)
                    break
        return matched, len(defn.required_items)
