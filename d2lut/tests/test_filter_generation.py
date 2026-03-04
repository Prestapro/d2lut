"""Tests for D2R filter generation behavior."""

from __future__ import annotations

from dataclasses import replace
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


def test_filter_output_has_unique_itemdisplay_codes(tmp_path):
    module = _load_filter_builder_module()
    builder = module.FilterBuilder(db_path=None, preset="default")

    first = module.PricedItem(
        name="jah",
        variant_key="rune:jah",
        d2r_code="r31",
        display_name="Jah Rune",
        price_fg=180.0,
        tier="HIGH",
        category="rune",
    )
    duplicate = replace(
        first,
        variant_key="rune:jah_alt",
        display_name="Jah Rune Duplicate",
        price_fg=40.0,
        tier="MID",
    )
    builder.items = [first, duplicate]

    output_path = tmp_path / "d2r.filter"
    builder.build_filter(output_path)
    content = output_path.read_text(encoding="utf-8")

    assert content.count("ItemDisplay[r31]") == 1


def test_tier_boundaries_are_stable():
    module = _load_filter_builder_module()
    builder = module.FilterBuilder(db_path=None, preset="default")

    assert builder._get_tier(500.0) == "GG"
    assert builder._get_tier(100.0) == "HIGH"
    assert builder._get_tier(20.0) == "MID"
    assert builder._get_tier(5.0) == "LOW"
    assert builder._get_tier(4.99) == "TRASH"
    assert builder._get_tier(999_999.0) == "GG"
