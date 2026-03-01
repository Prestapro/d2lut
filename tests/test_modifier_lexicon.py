from d2lut.normalize.modifier_lexicon import (
    infer_variant_from_noisy_ocr,
    infer_item_category_from_variant,
    norm_text,
    ocr_fold_text,
)


def test_infer_variant_from_noisy_ocr_hoto():
    text = 'HEART OF THE ®AK FLAIL "KOVEXPULTHUL" SOCKETED (4)'
    assert infer_variant_from_noisy_ocr(text, text) == "runeword:heart_of_the_oak"


def test_infer_variant_from_noisy_ocr_infanity():
    text = 'INFANITY SCYTHE "BERMALBERIST" ETHEREAL SOCKETED (4)'
    assert infer_variant_from_noisy_ocr(text, text) == "runeword:infinity"


def test_infer_variant_from_noisy_ocr_base_magee_plate():
    text = "SUPERIGQ Magee PLATE enhanced defense SeckeTeD (3)"
    assert infer_variant_from_noisy_ocr(text, text) == "base:mage_plate:noneth:3os"


def test_unid_torch_fallback_pattern():
    text = "LARGE CHARM keep inventory to gain bonus unidentified"
    assert infer_variant_from_noisy_ocr(text, text) == "unique:hellfire_torch"


def test_class_torch_fallback_pattern():
    text = "HELLFIRE TORCH LARGE CHARM +3 TO WARLOCK SKILLS ALL ATTRIBUTES ALL RESISTANCES"
    assert infer_variant_from_noisy_ocr(text, text) == "unique:hellfire_torch:sorceress"


def test_normalization_helpers():
    assert norm_text("Heart of the Oak") == "heart of the oak"
    assert ocr_fold_text("T@RCH | INFANITY") == "torch lnfanlty"


def test_variant_category_mapping():
    assert infer_item_category_from_variant("unique:hellfire_torch:sorceress") == "torch"
    assert infer_item_category_from_variant("base:mage_plate:noneth:3os") == "base_armor"
    assert infer_item_category_from_variant("rune:jah") == "runes"
