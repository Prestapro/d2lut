"""Tests for Task 24: classifier-grade modifier foundation.

Covers:
- Expanded category/quality constraints
- New d2jsp shorthand + OCR corruption aliases
- Per-class variant inference
- Constraint filtering correctness
"""
from d2lut.normalize.modifier_lexicon import (
    DEFAULT_CATEGORY_CONSTRAINTS,
    PROPERTY_NAME_CODE_PREFIXES,
    infer_item_category_from_variant,
    infer_variant_from_noisy_ocr,
    norm_text,
    ocr_fold_text,
    property_allowed_by_category_constraints,
    MANUAL_ITEM_OCR_ALIASES,
)


# ---------------------------------------------------------------------------
# 1. Expanded category constraints
# ---------------------------------------------------------------------------

class TestExpandedCategoryConstraints:
    """Verify new constraint categories reject impossible combos."""

    def test_charm_denies_sockets(self):
        assert not property_allowed_by_category_constraints("charm", "sockets")

    def test_charm_denies_ethereal(self):
        assert not property_allowed_by_category_constraints("charm", "ethereal")

    def test_charm_allows_life(self):
        assert property_allowed_by_category_constraints("charm", "life")

    def test_charm_allows_all_resistances(self):
        assert property_allowed_by_category_constraints("charm", "all_resistances")

    def test_amulet_denies_sockets(self):
        assert not property_allowed_by_category_constraints("amulet", "sockets")

    def test_amulet_denies_ethereal(self):
        assert not property_allowed_by_category_constraints("amulet", "ethereal")

    def test_amulet_allows_fcr(self):
        assert property_allowed_by_category_constraints("amulet", "fcr")

    def test_ring_denies_sockets(self):
        assert not property_allowed_by_category_constraints("ring", "sockets")

    def test_ring_allows_life(self):
        assert property_allowed_by_category_constraints("ring", "life")

    def test_boots_denies_sockets(self):
        assert not property_allowed_by_category_constraints("boots", "sockets")

    def test_boots_denies_ias(self):
        assert not property_allowed_by_category_constraints("boots", "ias")

    def test_boots_allows_frw(self):
        assert property_allowed_by_category_constraints("boots", "frw")

    def test_boots_allows_fhr(self):
        assert property_allowed_by_category_constraints("boots", "fhr")

    def test_belt_denies_sockets(self):
        assert not property_allowed_by_category_constraints("belt", "sockets")

    def test_belt_allows_life(self):
        assert property_allowed_by_category_constraints("belt", "life")

    def test_shield_denies_ias(self):
        assert not property_allowed_by_category_constraints("shield", "ias")

    def test_shield_allows_all_resistances(self):
        assert property_allowed_by_category_constraints("shield", "all_resistances")

    def test_helm_denies_ias(self):
        assert not property_allowed_by_category_constraints("helm", "ias")

    def test_helm_allows_fcr(self):
        assert property_allowed_by_category_constraints("helm", "fcr")

    def test_circlet_allows_sockets(self):
        # Circlets can have sockets
        assert property_allowed_by_category_constraints("circlet", "sockets")

    def test_circlet_allows_fcr(self):
        assert property_allowed_by_category_constraints("circlet", "fcr")

    def test_body_armor_allows_life(self):
        assert property_allowed_by_category_constraints("body_armor", "life")

    def test_body_armor_denies_ias(self):
        assert not property_allowed_by_category_constraints("body_armor", "ias")

    def test_set_item_denies_sockets(self):
        assert not property_allowed_by_category_constraints("set_item", "sockets")

    def test_unique_item_allows_sockets(self):
        # Some uniques have sockets (e.g. Lidless, CoA)
        assert property_allowed_by_category_constraints("unique_item", "sockets")

    def test_runeword_item_allows_sockets(self):
        assert property_allowed_by_category_constraints("runeword_item", "sockets")

    def test_rare_item_denies_sockets(self):
        assert not property_allowed_by_category_constraints("rare_item", "sockets")

    def test_unknown_category_allows_everything(self):
        assert property_allowed_by_category_constraints("unknown_cat", "sockets")
        assert property_allowed_by_category_constraints("unknown_cat", "fcr")

    def test_unknown_property_allowed(self):
        assert property_allowed_by_category_constraints("runes", "unknown_prop")

    def test_base_weapon_allows_enhanced_damage(self):
        """Regression: dmg code must match allow_codes correctly."""
        assert property_allowed_by_category_constraints("base_weapon", "enhanced_damage")

    def test_base_armor_allows_defense(self):
        assert property_allowed_by_category_constraints("base_armor", "defense")

    def test_base_armor_allows_base_type(self):
        assert property_allowed_by_category_constraints("base_armor", "base_type")

    def test_base_weapon_allows_base_type(self):
        assert property_allowed_by_category_constraints("base_weapon", "base_type")


# ---------------------------------------------------------------------------
# 2. New d2jsp shorthand + OCR corruption aliases
# ---------------------------------------------------------------------------

class TestExpandedOCRAliases:
    """Verify new runeword/item inference from noisy OCR text."""

    def test_grief_ocr_corruption(self):
        assert infer_variant_from_noisy_ocr("GRLEF", None) == "runeword:grief"

    def test_grief_normal(self):
        assert infer_variant_from_noisy_ocr("Grief Phase Blade", None) == "runeword:grief"

    def test_coh_shorthand(self):
        assert infer_variant_from_noisy_ocr("COH Archon Plate", None) == "runeword:chains_of_honor"

    def test_chains_of_honor_full(self):
        assert infer_variant_from_noisy_ocr("Chains of Honor", None) == "runeword:chains_of_honor"

    def test_fort_shorthand(self):
        assert infer_variant_from_noisy_ocr("Fort Archon Plate", None) == "runeword:fortitude"

    def test_fortitude_full(self):
        assert infer_variant_from_noisy_ocr("Fortitude", None) == "runeword:fortitude"

    def test_spirit_ocr_corruption(self):
        assert infer_variant_from_noisy_ocr("SPIRLT MONARCH", None) == "runeword:spirit"

    def test_spirit_normal(self):
        assert infer_variant_from_noisy_ocr("Spirit Monarch", None) == "runeword:spirit"

    def test_faith_normal(self):
        assert infer_variant_from_noisy_ocr("Faith Grand Matron Bow", None) == "runeword:faith"

    def test_last_wish_full(self):
        assert infer_variant_from_noisy_ocr("Last Wish", None) == "runeword:last_wish"

    def test_infinity_ocr_l(self):
        """OCR I->l corruption: lnfinity."""
        assert infer_variant_from_noisy_ocr("lnfinity", None) == "runeword:infinity"

    def test_hoto_ocr_zero(self):
        """OCR O->0 corruption: H0T0."""
        assert infer_variant_from_noisy_ocr("H0T0 Flail", None) == "runeword:heart_of_the_oak"

    def test_ebotd_shorthand(self):
        assert infer_variant_from_noisy_ocr("EBOTD", None) == "runeword:breath_of_the_dying"

    def test_ebotdz_shorthand(self):
        assert infer_variant_from_noisy_ocr("EBOTDZ", None) == "runeword:breath_of_the_dying"

    def test_insight_ocr_l(self):
        assert infer_variant_from_noisy_ocr("lnsight", None) == "runeword:insight"

    def test_anni_shorthand_in_aliases(self):
        """Verify 'anni' is in MANUAL_ITEM_OCR_ALIASES."""
        alias_texts = {a[1].lower() for a in MANUAL_ITEM_OCR_ALIASES}
        assert "anni" in alias_texts

    def test_soj_shorthand_in_aliases(self):
        alias_texts = {a[1].lower() for a in MANUAL_ITEM_OCR_ALIASES}
        assert "soj" in alias_texts

    def test_arach_shorthand_in_aliases(self):
        alias_texts = {a[1].lower() for a in MANUAL_ITEM_OCR_ALIASES}
        assert "arach" in alias_texts

    def test_maras_shorthand_in_aliases(self):
        alias_texts = {a[1].lower() for a in MANUAL_ITEM_OCR_ALIASES}
        assert "maras" in alias_texts

    def test_hoz_shorthand_in_aliases(self):
        alias_texts = {a[1].lower() for a in MANUAL_ITEM_OCR_ALIASES}
        assert "hoz" in alias_texts

    def test_griff_shorthand_in_aliases(self):
        alias_texts = {a[1].lower() for a in MANUAL_ITEM_OCR_ALIASES}
        assert "griff" in alias_texts


# ---------------------------------------------------------------------------
# 3. OCR fold expansion
# ---------------------------------------------------------------------------

class TestOCRFoldExpansion:
    """Verify new OCR fold characters."""

    def test_copyright_folds_to_c(self):
        assert "c" in ocr_fold_text("©")

    def test_cent_folds_to_c(self):
        assert "c" in ocr_fold_text("¢")

    def test_euro_folds_to_e(self):
        assert "e" in ocr_fold_text("€")

    def test_existing_folds_preserved(self):
        # Verify existing folds still work
        assert ocr_fold_text("@") == "o"
        assert ocr_fold_text("0") == "o"
        assert ocr_fold_text("1") == "l"


# ---------------------------------------------------------------------------
# 4. Expanded variant category mapping
# ---------------------------------------------------------------------------

class TestExpandedVariantCategoryMapping:
    """Verify infer_item_category_from_variant handles new categories."""

    def test_runeword_category(self):
        assert infer_item_category_from_variant("runeword:grief") == "runeword_item"

    def test_set_category(self):
        assert infer_item_category_from_variant("set:tal_rasha_guardianship") == "set_item"

    def test_unique_generic_category(self):
        assert infer_item_category_from_variant("unique:war_traveler") == "unique_item"

    def test_charm_category(self):
        assert infer_item_category_from_variant("charm:gheed") == "charm"

    def test_torch_still_torch(self):
        """Torch should still map to 'torch', not generic 'unique_item'."""
        assert infer_item_category_from_variant("unique:hellfire_torch:sorceress") == "torch"

    def test_anni_still_anni(self):
        assert infer_item_category_from_variant("unique:annihilus") == "anni"

    def test_rune_still_runes(self):
        assert infer_item_category_from_variant("rune:ber") == "runes"

    def test_base_armor_still_works(self):
        assert infer_item_category_from_variant("base:mage_plate:noneth:3os") == "base_armor"

    def test_base_weapon_still_works(self):
        assert infer_item_category_from_variant("base:thresher:eth:4os") == "base_weapon"


# ---------------------------------------------------------------------------
# 5. Constraint table completeness
# ---------------------------------------------------------------------------

class TestConstraintTableCompleteness:
    """Verify all expected categories exist in DEFAULT_CATEGORY_CONSTRAINTS."""

    EXPECTED_CATEGORIES = [
        "runes", "torch", "anni", "jewel", "charm",
        "amulet", "ring", "circlet", "gloves", "boots", "belt",
        "shield", "helm", "body_armor",
        "base_armor", "base_weapon",
        "set_item", "unique_item", "runeword_item", "magic_item", "rare_item",
    ]

    def test_all_expected_categories_present(self):
        for cat in self.EXPECTED_CATEGORIES:
            assert cat in DEFAULT_CATEGORY_CONSTRAINTS, f"Missing category: {cat}"

    def test_all_categories_have_deny_or_allow(self):
        for cat, rules in DEFAULT_CATEGORY_CONSTRAINTS.items():
            assert "deny_codes" in rules or "allow_codes" in rules, (
                f"Category {cat} has neither deny_codes nor allow_codes"
            )
