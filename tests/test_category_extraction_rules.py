"""Unit tests for category-specific property extraction rules."""

from d2lut.overlay.category_aware_parser import CategoryAwareParser
from d2lut.overlay.ocr_parser import ParsedItem, Property


def test_weapon_extraction_ed_and_sockets():
    """Test weapon category extracts ED% and sockets."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Phase Blade\n300% Enhanced Damage\n4 Sockets",
        item_name="Phase Blade",
        confidence=0.9
    )
    
    enriched = parser.parse_with_category(parsed)
    
    # Check that properties were extracted
    prop_names = {p.name for p in enriched.base_properties}
    assert "enhanced_damage" in prop_names
    assert "sockets" in prop_names
    assert "base_type" in prop_names
    
    # Check values
    ed_prop = next(p for p in enriched.base_properties if p.name == "enhanced_damage")
    assert ed_prop.value == "300%"
    
    sockets_prop = next(p for p in enriched.base_properties if p.name == "sockets")
    assert sockets_prop.value == "4"


def test_armor_extraction_defense_and_ethereal():
    """Test armor category extracts defense and ethereal status."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Ethereal Archon Plate\nDefense: 524\n4 Sockets",
        item_name="Archon Plate",
        confidence=0.9
    )
    
    enriched = parser.parse_with_category(parsed)
    
    prop_names = {p.name for p in enriched.base_properties}
    assert "defense" in prop_names
    assert "ethereal" in prop_names
    assert "sockets" in prop_names
    assert "base_type" in prop_names
    
    defense_prop = next(p for p in enriched.base_properties if p.name == "defense")
    assert defense_prop.value == "524"
    
    eth_prop = next(p for p in enriched.base_properties if p.name == "ethereal")
    assert eth_prop.value == "true"


def test_charm_extraction_life_and_resistances():
    """Test charm category extracts life and resistances."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Small Charm\n+20 to Life\n+11 Fire Resistance",
        item_name="Small Charm",
        confidence=0.9
    )
    
    enriched = parser.parse_with_category(parsed, category_hint="charms")
    
    prop_names = {p.name for p in enriched.base_properties}
    assert "charm_size" in prop_names
    assert "life" in prop_names
    assert "fire_resistance" in prop_names
    
    life_prop = next(p for p in enriched.base_properties if p.name == "life")
    assert life_prop.value == "20"
    
    fr_prop = next(p for p in enriched.base_properties if p.name == "fire_resistance")
    assert fr_prop.value == "11"


def test_charm_extraction_all_resistances():
    """Test charm extracts all resistances."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Grand Charm\n+5 to All Resistances",
        item_name="Grand Charm",
        confidence=0.9
    )
    
    enriched = parser.parse_with_category(parsed, category_hint="charms")
    
    prop_names = {p.name for p in enriched.base_properties}
    assert "all_resistances" in prop_names
    
    all_res_prop = next(p for p in enriched.base_properties if p.name == "all_resistances")
    assert all_res_prop.value == "5"


def test_jewel_extraction_ias_and_ed():
    """Test jewel category extracts IAS and ED."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Jewel\n15% Increased Attack Speed\n30% Enhanced Damage",
        item_name="Jewel",
        confidence=0.9
    )
    
    enriched = parser.parse_with_category(parsed)
    
    prop_names = {p.name for p in enriched.base_properties}
    assert "ias" in prop_names
    assert "enhanced_damage" in prop_names
    
    ias_prop = next(p for p in enriched.base_properties if p.name == "ias")
    assert ias_prop.value == "15%"
    
    ed_prop = next(p for p in enriched.base_properties if p.name == "enhanced_damage")
    assert ed_prop.value == "30%"


def test_rune_extraction_rune_name():
    """Test rune category extracts rune name."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Jah Rune",
        item_name="Jah Rune",
        confidence=0.95
    )
    
    enriched = parser.parse_with_category(parsed, category_hint="runes")
    
    prop_names = {p.name for p in enriched.base_properties}
    assert "rune_name" in prop_names
    
    rune_prop = next(p for p in enriched.base_properties if p.name == "rune_name")
    assert rune_prop.value == "jah"


def test_charm_extraction_skills():
    """Test charm extracts skill bonuses."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Grand Charm\n+1 to All Skills",
        item_name="Grand Charm",
        confidence=0.9
    )
    
    enriched = parser.parse_with_category(parsed, category_hint="charms")
    
    prop_names = {p.name for p in enriched.base_properties}
    assert "all_skills" in prop_names
    
    skills_prop = next(p for p in enriched.base_properties if p.name == "all_skills")
    assert skills_prop.value == "1"


def test_charm_extraction_max_damage_and_ar():
    """Test charm extracts max damage and AR (LLD charm pattern)."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Small Charm\n+3 to Maximum Damage\n+20 to Attack Rating",
        item_name="Small Charm",
        confidence=0.9
    )
    
    enriched = parser.parse_with_category(parsed, category_hint="charms")
    
    prop_names = {p.name for p in enriched.base_properties}
    assert "max_damage" in prop_names
    assert "attack_rating" in prop_names
    
    max_dmg_prop = next(p for p in enriched.base_properties if p.name == "max_damage")
    assert max_dmg_prop.value == "3"
    
    ar_prop = next(p for p in enriched.base_properties if p.name == "attack_rating")
    assert ar_prop.value == "20"


def test_no_duplicate_properties():
    """Test that existing properties are not duplicated."""
    parser = CategoryAwareParser()
    existing_life = Property(name="life", value="15")
    parsed = ParsedItem(
        raw_text="Small Charm\n+20 to Life",
        item_name="Small Charm",
        base_properties=[existing_life],
        confidence=0.9
    )
    
    enriched = parser.parse_with_category(parsed, category_hint="charms")
    
    # Should not add duplicate life property
    life_props = [p for p in enriched.base_properties if p.name == "life"]
    assert len(life_props) == 1
    assert life_props[0].value == "15"  # Original value preserved


def test_multiple_resistances_extraction():
    """Test extraction of multiple individual resistances."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Grand Charm\n+11 Fire Resistance\n+10 Cold Resistance\n+9 Lightning Resistance",
        item_name="Grand Charm",
        confidence=0.9
    )
    
    enriched = parser.parse_with_category(parsed, category_hint="charms")
    
    prop_names = {p.name for p in enriched.base_properties}
    assert "fire_resistance" in prop_names
    assert "cold_resistance" in prop_names
    assert "lightning_resistance" in prop_names
    
    fr_prop = next(p for p in enriched.base_properties if p.name == "fire_resistance")
    assert fr_prop.value == "11"
    
    cr_prop = next(p for p in enriched.base_properties if p.name == "cold_resistance")
    assert cr_prop.value == "10"
    
    lr_prop = next(p for p in enriched.base_properties if p.name == "lightning_resistance")
    assert lr_prop.value == "9"


def test_charm_extraction_fhr():
    """Test charm category extracts FHR."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Small Charm\n5% Faster Hit Recovery\n+20 to Life",
        item_name="Small Charm",
        confidence=0.9
    )
    enriched = parser.parse_with_category(parsed, category_hint="charms")
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("fhr") == "5%"
    assert props.get("life") == "20"


def test_charm_extraction_frw():
    """Test charm category extracts FRW."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Small Charm\n3% Faster Run/Walk",
        item_name="Small Charm",
        confidence=0.9
    )
    enriched = parser.parse_with_category(parsed, category_hint="charms")
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("frw") == "3%"


def test_charm_extraction_mf():
    """Test charm category extracts magic find."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Small Charm\n7% Better Chance of Getting Magic Items",
        item_name="Small Charm",
        confidence=0.9
    )
    enriched = parser.parse_with_category(parsed, category_hint="charms")
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("magic_find") == "7%"


def test_charm_extraction_mana():
    """Test charm category extracts mana."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Grand Charm\n+17 to Mana",
        item_name="Grand Charm",
        confidence=0.9
    )
    enriched = parser.parse_with_category(parsed, category_hint="charms")
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("mana") == "17"


def test_jewel_extraction_fcr():
    """Test jewel category extracts FCR."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Jewel\n10% Faster Cast Rate\n+15 Fire Resistance",
        item_name="Jewel",
        confidence=0.9
    )
    enriched = parser.parse_with_category(parsed)
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("fcr") == "10%"
    assert props.get("fire_resistance") == "15"


def test_jewel_extraction_fhr_and_mf():
    """Test jewel category extracts FHR and MF."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Jewel\n7% Faster Hit Recovery\n7% Magic Find",
        item_name="Jewel",
        confidence=0.9
    )
    enriched = parser.parse_with_category(parsed)
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("fhr") == "7%"
    assert props.get("magic_find") == "7%"


def test_weapon_extraction_ias():
    """Test weapon category extracts IAS."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Phase Blade\n40% Increased Attack Speed\n300% Enhanced Damage",
        item_name="Phase Blade",
        confidence=0.9
    )
    enriched = parser.parse_with_category(parsed)
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("ias") == "40%"
    assert props.get("enhanced_damage") == "300%"


def test_weapon_extraction_fcr():
    """Test weapon category extracts FCR (e.g. HOTO base)."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Flail\n40% Faster Cast Rate\n3 Sockets",
        item_name="Flail",
        confidence=0.9
    )
    enriched = parser.parse_with_category(parsed)
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("fcr") == "40%"
    assert props.get("sockets") == "3"


def test_armor_extraction_fcr_and_resistances():
    """Test armor category extracts FCR and resistances."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Circlet\n20% Faster Cast Rate\n+20 to All Resistances\n2 Sockets",
        item_name="Circlet",
        confidence=0.9
    )
    enriched = parser.parse_with_category(parsed)
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("fcr") == "20%"
    assert props.get("all_resistances") == "20"
    assert props.get("sockets") == "2"


def test_armor_extraction_fhr_frw_life():
    """Test armor category extracts FHR, FRW, and life."""
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="Archon Plate\nDefense: 524\n30% Faster Hit Recovery\n20% Faster Run/Walk\n+60 to Life",
        item_name="Archon Plate",
        confidence=0.9
    )
    enriched = parser.parse_with_category(parsed)
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("fhr") == "30%"
    assert props.get("frw") == "20%"
    assert props.get("life") == "60"
    assert props.get("defense") == "524"


def test_expanded_weapon_base_detection():
    """Test that expanded weapon bases are detected correctly."""
    parser = CategoryAwareParser()
    for base in ["Colossus Blade", "Flail", "Crystal Sword", "Hydra Bow", "Suwayyah"]:
        parsed = ParsedItem(
            raw_text=f"{base}\n300% Enhanced Damage",
            item_name=base,
            confidence=0.9
        )
        enriched = parser.parse_with_category(parsed)
        assert enriched.diagnostic.get("category_hint_applied") == "weapons", f"Failed for {base}"


def test_expanded_armor_base_detection():
    """Test that expanded armor bases are detected correctly."""
    parser = CategoryAwareParser()
    for base in ["Diadem", "Circlet", "Sacred Armor", "Vortex Shield"]:
        parsed = ParsedItem(
            raw_text=f"{base}\nDefense: 400",
            item_name=base,
            confidence=0.9
        )
        enriched = parser.parse_with_category(parsed)
        assert enriched.diagnostic.get("category_hint_applied") == "armor", f"Failed for {base}"


if __name__ == "__main__":
    test_weapon_extraction_ed_and_sockets()
    test_armor_extraction_defense_and_ethereal()
    test_charm_extraction_life_and_resistances()
    test_charm_extraction_all_resistances()
    test_jewel_extraction_ias_and_ed()
    test_rune_extraction_rune_name()
    test_charm_extraction_skills()
    test_charm_extraction_max_damage_and_ar()
    test_no_duplicate_properties()
    test_multiple_resistances_extraction()
    test_charm_extraction_fhr()
    test_charm_extraction_frw()
    test_charm_extraction_mf()
    test_charm_extraction_mana()
    test_jewel_extraction_fcr()
    test_jewel_extraction_fhr_and_mf()
    test_weapon_extraction_ias()
    test_weapon_extraction_fcr()
    test_armor_extraction_fcr_and_resistances()
    test_armor_extraction_fhr_frw_life()
    test_expanded_weapon_base_detection()
    test_expanded_armor_base_detection()
    print("All category extraction tests passed!")
