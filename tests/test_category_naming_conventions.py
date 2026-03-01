"""Test category-specific naming conventions and property extraction."""

from d2lut.overlay.category_aware_parser import CategoryAwareParser
from d2lut.overlay.ocr_parser import ParsedItem


def test_weapon_naming_convention():
    """Test weapon category applies proper naming conventions."""
    parser = CategoryAwareParser()
    
    # Test ethereal weapon with ED and sockets
    parsed = ParsedItem(
        raw_text="Ethereal Berserker Axe\n300% Enhanced Damage\n6 Sockets",
        item_name="Berserker Axe",
        confidence=0.9
    )
    
    enriched = parser.parse_with_category(parsed)
    
    # Verify weapon-specific properties are extracted
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("base_type") == "berserker axe"
    assert props.get("enhanced_damage") == "300%"
    assert props.get("sockets") == "6"
    assert props.get("ethereal") == "true"
    
    # Verify diagnostic shows weapon category
    assert enriched.diagnostic.get("category_hint_applied") == "weapons"


def test_armor_naming_convention():
    """Test armor category applies proper naming conventions."""
    parser = CategoryAwareParser()
    
    # Test superior armor with defense
    parsed = ParsedItem(
        raw_text="Superior Archon Plate\nDefense: 524\n15% Enhanced Defense\n4 Sockets",
        item_name="Archon Plate",
        confidence=0.9
    )
    
    enriched = parser.parse_with_category(parsed)
    
    # Verify armor-specific properties
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("base_type") == "archon plate"
    assert props.get("defense") == "524"
    assert props.get("sockets") == "4"
    
    assert enriched.diagnostic.get("category_hint_applied") == "armor"


def test_charm_naming_convention():
    """Test charm category applies proper naming conventions."""
    parser = CategoryAwareParser()
    
    # Test grand charm with skill and life
    parsed = ParsedItem(
        raw_text="Grand Charm of Vita\n+1 to Barbarian Combat Skills\n+36 to Life",
        item_name="Grand Charm",
        confidence=0.9
    )
    
    enriched = parser.parse_with_category(parsed)
    
    # Verify charm-specific properties
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("charm_size") == "grand"
    assert props.get("life") == "36"
    
    assert enriched.diagnostic.get("category_hint_applied") == "charms"


def test_jewel_naming_convention():
    """Test jewel category applies proper naming conventions."""
    parser = CategoryAwareParser()
    
    # Test jewel with IAS and ED
    parsed = ParsedItem(
        raw_text="Jewel of Fervor\n15% Increased Attack Speed\n40% Enhanced Damage",
        item_name="Jewel",
        confidence=0.9
    )
    
    enriched = parser.parse_with_category(parsed)
    
    # Verify jewel-specific properties
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("ias") == "15%"
    assert props.get("enhanced_damage") == "40%"
    
    assert enriched.diagnostic.get("category_hint_applied") == "jewels"


def test_rune_naming_convention():
    """Test rune category applies proper naming conventions."""
    parser = CategoryAwareParser()
    
    # Test rune name extraction
    parsed = ParsedItem(
        raw_text="Ber Rune\nLevel Requirement: 63",
        item_name="Ber Rune",
        confidence=0.95
    )
    
    enriched = parser.parse_with_category(parsed)
    
    # Verify rune-specific properties
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("rune_name") == "ber"
    
    assert enriched.diagnostic.get("category_hint_applied") == "runes"


def test_lld_charm_naming_convention():
    """Test LLD charm applies proper naming conventions."""
    parser = CategoryAwareParser()
    
    # Test LLD small charm with max damage, AR, and life
    parsed = ParsedItem(
        raw_text="LLD Small Charm\n+3 to Maximum Damage\n+20 to Attack Rating\n+20 to Life",
        item_name="Small Charm",
        confidence=0.9
    )
    
    enriched = parser.parse_with_category(parsed, category_hint="lld")
    
    # Verify LLD charm properties
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("charm_size") == "small"
    assert props.get("max_damage") == "3"
    assert props.get("attack_rating") == "20"
    assert props.get("life") == "20"
    
    # Verify both LLD and charm categories are detected
    assert enriched.diagnostic.get("lld_context") is True
    assert enriched.diagnostic.get("category_hint_applied") == "lld"


def test_shield_naming_convention():
    """Test shield (armor category) applies proper naming conventions."""
    parser = CategoryAwareParser()
    
    # Test monarch shield
    parsed = ParsedItem(
        raw_text="Monarch\nDefense: 156\n4 Sockets",
        item_name="Monarch",
        confidence=0.9
    )
    
    enriched = parser.parse_with_category(parsed)
    
    # Verify shield properties
    props = {p.name: p.value for p in enriched.base_properties}
    assert props.get("base_type") == "monarch"
    assert props.get("defense") == "156"
    assert props.get("sockets") == "4"
    
    assert enriched.diagnostic.get("category_hint_applied") == "armor"


def test_property_value_formatting():
    """Test that property values follow consistent formatting conventions."""
    parser = CategoryAwareParser()
    
    # Test various property formats — percentage-based stats get %, flat stats are plain numbers
    test_cases = [
        ("15% IAS", "ias", "15%"),
        ("300% ED", "enhanced_damage", "300%"),
        ("+20 to Life", "life", "20"),
        ("Defense: 524", "defense", "524"),
        ("4 Sockets", "sockets", "4"),
        ("+11 Fire Resistance", "fire_resistance", "11"),
        ("10% Faster Cast Rate", "fcr", "10%"),
        ("20% Faster Run/Walk", "frw", "20%"),
        ("5% Faster Hit Recovery", "fhr", "5%"),
        ("+17 to Mana", "mana", "17"),
        ("7% Magic Find", "magic_find", "7%"),
    ]
    
    for text, expected_prop, expected_value in test_cases:
        parsed = ParsedItem(
            raw_text=f"Test Item\n{text}",
            item_name="Test Item",
            confidence=0.9
        )
        
        enriched = parser.parse_with_category(parsed)
        
        if enriched.base_properties:
            prop = next((p for p in enriched.base_properties if p.name == expected_prop), None)
            if prop:
                assert prop.value == expected_value, f"Expected {expected_prop}={expected_value}, got {prop.value}"


if __name__ == "__main__":
    test_weapon_naming_convention()
    test_armor_naming_convention()
    test_charm_naming_convention()
    test_jewel_naming_convention()
    test_rune_naming_convention()
    test_lld_charm_naming_convention()
    test_shield_naming_convention()
    test_property_value_formatting()
    print("All naming convention tests passed!")
