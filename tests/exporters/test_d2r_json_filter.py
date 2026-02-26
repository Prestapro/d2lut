import json
import sqlite3
import pytest
from d2lut.exporters.d2r_json_filter import D2RJsonFilterExporter
from d2lut.models import PriceEstimate
from datetime import datetime

@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE catalog_items (canonical_item_id TEXT, source_table TEXT, source_key TEXT, display_name TEXT)")
    conn.execute("CREATE TABLE catalog_affixes (affix_id TEXT, affix_name TEXT)")
    
    # Insert some dummy mapping data
    conn.execute("INSERT INTO catalog_items VALUES ('unique:harlequin_crest', 'catalog_uniques', 'Harlequin Crest', 'Shako')")
    conn.execute("INSERT INTO catalog_items VALUES ('base:uap', 'catalog_bases', 'uap', 'Monarch')")
    conn.execute("INSERT INTO catalog_affixes VALUES ('prefix:acrobat''s', 'Acrobat''s')")
    
    # Dummy data for multi-map variant
    conn.execute("INSERT INTO catalog_items VALUES ('unique:multi_map_item', 'catalog_uniques', 'MultiMapKey1', 'Item 1')")
    conn.execute("INSERT INTO catalog_items VALUES ('unique:multi_map_item', 'catalog_uniques', 'MultiMapKey2', 'Item 2')")
    
    yield conn
    conn.close()

def test_export_sparse_generation(test_db):
    exporter = D2RJsonFilterExporter(min_fg=10.0, always_include_kinds=["rune"])
    prices = {
        "rune:jah": PriceEstimate("rune:jah", 4000.0, 3900.0, 4100.0, "high", 50, datetime.now()),
        "unique:harlequin_crest": PriceEstimate("unique:harlequin_crest", 150.0, 100.0, 200.0, "high", 50, datetime.now()),
        "prefix:acrobat's": PriceEstimate("prefix:acrobat's", 50.0, 40.0, 60.0, "low", 10, datetime.now()),
        "base:uap": PriceEstimate("base:uap", 20.0, 15.0, 25.0, "medium", 30, datetime.now()),
        "rune:el": PriceEstimate("rune:el", 1.0, 1.0, 1.0, "low", 5, datetime.now()) # Should be included because of always_include_kinds
    }
    
    # Generate sparse output
    result = exporter.export(prices, test_db)
    data = json.loads(result)
    
    # Verify outputs
    assert len(data) == 5
    
    # Verify exact key mappings
    keys = {d["Key"]: d["enUS"] for d in data}
    assert "r31" in keys
    assert keys["r31"] == "r31 [4000 fg]"
    
    assert "Harlequin Crest" in keys
    assert keys["Harlequin Crest"] == "Harlequin Crest [150 fg]"
    
    assert "Acrobat's" in keys
    assert keys["Acrobat's"] == "Acrobat's [50 fg]"
    
    assert "uap" in keys
    assert keys["uap"] == "uap [20 fg]"
    
    assert "r01" in keys # Kept by always_include_kinds
    assert keys["r01"] == "r01 [1 fg]"
    
def test_export_dict_merge_and_idempotency(test_db, tmp_path):
    exporter = D2RJsonFilterExporter(min_fg=10.0, price_mode="range_low")
    prices = {
        "rune:ber": PriceEstimate("rune:ber", 3000.0, 2900.0, 3100.0, "high", 50, datetime.now()),
    }
    
    # Create base dictionary json with existing old prices
    base_file = tmp_path / "item-names.json"
    base_data = {
        "r30": "Ber Rune [1500 fg]", # Old price to be cleared
        "uap": {"enUS": "Monarch"}
    }
    base_file.write_text(json.dumps(base_data))
    
    result = exporter.export(prices, test_db, base_json_path=str(base_file))
    data = json.loads(result)
    
    # The old ` [1500 fg]` should be cleanly replaced by ` [2900 fg]`
    assert data["r30"] == "Ber Rune [2900 fg]"
    assert data["uap"]["enUS"] == "Monarch" # Untouched

def test_export_dict_new_key_insertion(test_db, tmp_path):
    exporter = D2RJsonFilterExporter(min_fg=10.0)
    prices = {
        "rune:jah": PriceEstimate("rune:jah", 4000.0, 3900.0, 4100.0, "high", 50, datetime.now()),
    }
    
    # Base dict without the key
    base_file = tmp_path / "item-names.json"
    base_file.write_text(json.dumps({"uap": "Monarch"}))
    
    result = exporter.export(prices, test_db, base_json_path=str(base_file))
    data = json.loads(result)
    
    # The new key should be inserted in `{key}{price}` format as a fallback
    assert "r31" in data
    assert data["r31"] == "r31 [4000 fg]"
    assert data["uap"] == "Monarch"

def test_export_multi_map_warning(test_db):
    exporter = D2RJsonFilterExporter(min_fg=10.0)
    prices = {
        "unique:multi_map_item": PriceEstimate("unique:multi_map_item", 100.0, 90.0, 110.0, "high", 50, datetime.now()),
    }
    
    # The DB fixture has two source_keys for 'unique:multi_map_item'
    result = exporter.export(prices, test_db)
    data = json.loads(result)
    
    # Should generate entries for both mapped keys
    assert len(data) == 2
    keys = {d["Key"]: d["enUS"] for d in data}
    assert "MultiMapKey1 [100 fg]" == keys.get("MultiMapKey1")
    assert "MultiMapKey2 [100 fg]" == keys.get("MultiMapKey2")
    
    # Audit report should flag it as multi_map
    assert exporter.audit_report["mapped_count"] == 1
    assert "unique:multi_map_item" in exporter.audit_report["multi_map_variants"]

def test_export_range_high_formatting(test_db):
    exporter = D2RJsonFilterExporter(min_fg=10.0, price_mode="range_high")
    prices = {
        "base:uap": PriceEstimate("base:uap", 20.0, 15.0, 35.0, "medium", 30, datetime.now()),
    }
    
    result = exporter.export(prices, test_db)
    data = json.loads(result)
    
    assert len(data) == 1
    assert data[0]["enUS"] == "uap [35 fg]" # Range high instead of 20

def test_export_always_include_kinds_multiple(test_db):
    exporter = D2RJsonFilterExporter(min_fg=100.0, always_include_kinds=["key", "token"])
    prices = {
        "key:terror": PriceEstimate("key:terror", 5.0, 4.0, 6.0, "high", 50, datetime.now()),
        "token:absolution": PriceEstimate("token:absolution", 15.0, 14.0, 16.0, "high", 50, datetime.now()),
        "base:uap": PriceEstimate("base:uap", 20.0, 15.0, 35.0, "medium", 30, datetime.now()), # Excluded by min_fg
    }
    
    result = exporter.export(prices, test_db)
    data = json.loads(result)
    
    assert len(data) == 2 # 2 included, 1 excluded
    keys = {d["Key"]: d["enUS"] for d in data}
    
    assert "pk1" in keys # terror key map
    assert "toa" in keys # token map
    assert "uap" not in keys

def test_export_dict_short_names(test_db, tmp_path):
    exporter = D2RJsonFilterExporter(min_fg=10.0, use_short_names=True, hide_junk=True)
    prices = {
        "rune:jah": PriceEstimate("rune:jah", 4000.0, 3900.0, 4100.0, "high", 50, datetime.now()),
    }
    
    base_file = tmp_path / "item-names.json"
    base_file.write_text(json.dumps({
        "hp5": "Super Healing Potion", # Should become "Super HP"
        "aq2": "Arrows",               # Should become "" (hidden)
        "tsc": "Scroll of Town Portal",# Should become "TP Scroll"
        "r31": "Jah Rune"              # Should become "Jah Rune [4000 fg]"
    }))
    
    result = exporter.export(prices, test_db, base_json_path=str(base_file))
    data = json.loads(result)
    
    assert data["hp5"] == "Super HP"
    assert data["aq2"] == ""
    assert data["tsc"] == "TP Scroll"
    assert data["r31"] == "Jah Rune [4000 fg]"

def test_export_sparse_short_names(test_db):
    # In sparse mode, we only generate items we have prices for
    exporter = D2RJsonFilterExporter(min_fg=10.0, use_short_names=True, hide_junk=True)
    prices = {
        "rune:jah": PriceEstimate("rune:jah", 4000.0, 3900.0, 4100.0, "high", 50, datetime.now()),
    }
    
    result = exporter.export(prices, test_db)
    data = json.loads(result)
    
    assert len(data) == 1
    assert data[0]["enUS"] == "r31 [4000 fg]"

def test_export_apply_colors(test_db, tmp_path):
    exporter = D2RJsonFilterExporter(min_fg=10.0, apply_colors=True)
    prices = {
        "rune:jah": PriceEstimate("rune:jah", 4000.0, 3900.0, 4100.0, "high", 50, datetime.now()), # 1000+ -> ÿc; (Purple)
        "rune:ber": PriceEstimate("rune:ber", 500.0, 400.0, 600.0, "high", 50, datetime.now()),    # 200-999 -> ÿc4 (Gold)
    }
    
    base_file = tmp_path / "item-names.json"
    # Seed one item with an existing colored price to test idempotency deletion
    base_file.write_text(json.dumps({
        "r30": "Ber Rune ÿc2[9999 fg]ÿc0", # Green (legacy/test formatting)
        "r31": "Jah Rune"
    }))
    
    result = exporter.export(prices, test_db, base_json_path=str(base_file))
    data = json.loads(result)
    
    # Verify new pricing overrode old color arrays completely
    assert data["r30"] == "Ber Rune ÿc4[500 fg]ÿc0"
    assert data["r31"] == "Jah Rune ÿc;[4000 fg]ÿc0"

def test_export_apply_colors_with_custom_format_idempotent(test_db, tmp_path):
    exporter = D2RJsonFilterExporter(min_fg=10.0, apply_colors=True, format_str=" | {fg} FG")
    prices = {
        "rune:ber": PriceEstimate("rune:ber", 500.0, 400.0, 600.0, "high", 50, datetime.now()),
    }

    base_file = tmp_path / "item-names.json"
    # Existing colored custom tag should be fully removed and replaced.
    base_file.write_text(json.dumps({
        "r30": "Ber Rune ÿc2| 9999 FGÿc0"
    }))

    result = exporter.export(prices, test_db, base_json_path=str(base_file))
    data = json.loads(result)
    assert data["r30"] == "Ber Rune ÿc4| 500 FGÿc0"

def test_export_explain_audit_samples(test_db):
    exporter = D2RJsonFilterExporter(
        min_fg=100.0,
        always_include_kinds=["rune:jah"],
        apply_colors=True,
        collect_explain=True,
        explain_limit=5,
    )
    prices = {
        "rune:jah": PriceEstimate("rune:jah", 50.0, 45.0, 55.0, "high", 10, datetime.now()),  # forced include
        "rune:ber": PriceEstimate("rune:ber", 90.0, 80.0, 100.0, "high", 10, datetime.now()),  # below threshold skip
    }
    result = exporter.export(prices, test_db)
    data = json.loads(result)
    assert len(data) == 1
    report = exporter.audit_report
    assert report["eligible_count"] == 1
    assert report["eligible_by_forced"] == 1
    assert report["eligible_by_threshold"] == 0
    assert len(report["sample_injections"]) == 1
    assert report["sample_injections"][0]["variant_key"] == "rune:jah"
    assert report["sample_injections"][0]["forced_match"] is True
    assert report["sample_injections"][0]["color_tag"] == "ÿc0"  # 50 fg tier
    assert len(report["sample_skipped_below_threshold"]) == 1
    assert report["sample_skipped_below_threshold"][0]["variant_key"] == "rune:ber"
