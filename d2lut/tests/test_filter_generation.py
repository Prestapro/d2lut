"""Tests for D2R filter generation behavior."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


def _load_filter_builder_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "build_d2r_filter.py"
    spec = spec_from_file_location("build_d2r_filter", script_path)
    module = module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_deduplicate_keeps_highest_price():
    module = _load_filter_builder_module()
    
    first = module.FilterItem(
        code="uui",
        display_name="Shako",
        price=15.0,
        category="unique",
    )
    duplicate = module.FilterItem(
        code="uui",
        display_name="Peasant Crown",
        price=2.0,
        category="unique",
    )
    
    # Passing both items; the one with higher price should win per code
    deduped = module.deduplicate([first, duplicate])
    
    assert len(deduped) == 1
    assert "uui" in deduped
    assert deduped["uui"].display_name == "Shako"
    assert deduped["uui"].price == 15.0


def test_tier_boundaries_are_stable():
    module = _load_filter_builder_module()

    assert module.get_tier(500.0) == "GG"
    assert module.get_tier(100.0) == "HIGH"
    assert module.get_tier(20.0) == "MID"
    assert module.get_tier(5.0) == "LOW"
    assert module.get_tier(4.99) == "TRASH"
    assert module.get_tier(999_999.0) == "GG"

def test_layer_generation_syntax():
    module = _load_filter_builder_module()
    
    item = module.FilterItem(
        code="uui",
        display_name="Shako",
        price=15.0,
        category="unique"
    )
    
    runeword_map = module.build_runeword_map()
    cfg = module.PRESETS["default"]
    
    layers = module.generate_layers(item, runeword_map, threshold=0.0, cfg=cfg)
    
    # In default preset we expect up to 3-4 rules for a normal base
    assert len(layers) > 0
    assert any("ItemDisplay[uui&UNIQUE]:" in line for line in layers)
    assert any("ItemDisplay[uui&SET]:" in line for line in layers)
    assert any("ItemDisplay[uui]:" in line for line in layers)
