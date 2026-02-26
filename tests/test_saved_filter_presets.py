"""Tests for saved filter presets (Task 18).

Validates: Requirements 19.1, 19.2, 19.3, 19.4
"""

import json

from scripts.export_property_price_table_html import _build_html


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_row(**overrides):
    """Build a minimal out_rows dict for _build_html."""
    base = {
        "row_kind": "property",
        "name_display": "Test Item",
        "type_l1": "runeword",
        "type_l2": "",
        "type_l3": "",
        "class_tags": "",
        "signature": "test_sig",
        "req_lvl_min": None,
        "median_fg": 500.0,
        "max_fg": 600.0,
        "obs_count": 3,
        "variant_count": 2,
        "potential_score": 0,
        "potential_tags": [],
        "perfect_tier": "",
        "iso_sell": "",
        "top_variants": ["runeword:test"],
        "signals": "bin:2 sold:1",
        "confidence": "medium",
        "example_excerpt": "test excerpt",
        "last_source_url": "https://example.com",
        "kit": False,
        "lld_bucket": "unknown",
        "last_seen": "2025-01-15T10:00:00",
        "observations": [],
    }
    base.update(overrides)
    return base


def _get_html():
    return _build_html("test_market", [_minimal_row()])


# ---------------------------------------------------------------------------
# 18.1 — Built-in presets: UI elements present
# ---------------------------------------------------------------------------

class TestBuiltinPresetsUI:
    """Req 19.1: Built-in presets are available in the HTML."""

    def test_preset_selector_present(self):
        html = _get_html()
        assert 'id="presetSelect"' in html

    def test_builtin_preset_optgroup_present(self):
        html = _get_html()
        assert 'id="builtinPresetGroup"' in html

    def test_save_button_present(self):
        html = _get_html()
        assert 'id="presetSave"' in html

    def test_delete_button_present(self):
        html = _get_html()
        assert 'id="presetDelete"' in html


class TestBuiltinPresetDefinitions:
    """Req 19.1: All seven built-in presets are defined in JS."""

    def test_builtin_presets_object_present(self):
        html = _get_html()
        assert "BUILTIN_PRESETS" in html

    def test_commodities_preset(self):
        html = _get_html()
        assert '"Commodities"' in html

    def test_runewords_preset(self):
        html = _get_html()
        assert '"Runewords"' in html

    def test_torches_annis_preset(self):
        html = _get_html()
        assert '"Torches/Annis"' in html

    def test_lld_preset(self):
        html = _get_html()
        assert '"LLD"' in html

    def test_bases_preset(self):
        html = _get_html()
        assert '"Bases"' in html

    def test_no_source_link_preset(self):
        html = _get_html()
        assert '"No source link"' in html

    def test_high_fg_low_confidence_preset(self):
        html = _get_html()
        assert '"High FG + low confidence"' in html


class TestPresetApplication:
    """Req 19.2: Selecting a preset applies filter values and re-renders."""

    def test_apply_preset_function_present(self):
        html = _get_html()
        assert "function _applyPreset" in html

    def test_apply_preset_resets_defaults_then_applies(self):
        """_applyPreset should reset state to defaults before applying overrides."""
        html = _get_html()
        assert "Object.assign(state, defaults)" in html

    def test_apply_preset_syncs_ui_controls(self):
        """After applying preset, UI controls should be synced to new state."""
        html = _get_html()
        assert "syncMap" in html
        assert "el.value = state[stateKey]" in html

    def test_preset_select_change_triggers_apply(self):
        """Changing the preset selector should call _applyPreset."""
        html = _get_html()
        assert '"presetSelect"' in html
        assert "_applyPreset(BUILTIN_PRESETS[name])" in html

    def test_builtin_preset_commodities_sets_type1_filter(self):
        """Commodities preset should set type1Filter to bundle."""
        html = _get_html()
        assert '"Commodities": { type1Filter: "bundle"' in html

    def test_builtin_preset_no_source_link_sets_link_mode(self):
        """No source link preset should set linkMode to without."""
        html = _get_html()
        assert '"No source link": { linkMode: "without" }' in html

    def test_builtin_preset_high_fg_low_conf_sets_both(self):
        """High FG + low confidence preset should set minFg and conf."""
        html = _get_html()
        assert '"High FG + low confidence": { minFg: 500, conf: "low" }' in html


# ---------------------------------------------------------------------------
# 18.2 — Custom preset save/delete via localStorage
# ---------------------------------------------------------------------------

class TestCustomPresetLocalStorage:
    """Req 19.3, 19.4: Custom presets save/delete via localStorage."""

    def test_custom_preset_key_defined(self):
        html = _get_html()
        assert "d2lut_custom_presets" in html

    def test_load_custom_presets_function(self):
        html = _get_html()
        assert "function _loadCustomPresets" in html
        assert "localStorage.getItem(CUSTOM_PRESET_KEY)" in html

    def test_save_custom_presets_function(self):
        html = _get_html()
        assert "function _saveCustomPresets" in html
        assert "localStorage.setItem(CUSTOM_PRESET_KEY" in html

    def test_save_button_prompts_for_name(self):
        html = _get_html()
        assert 'prompt("Preset name:")' in html

    def test_save_stores_current_filter_state(self):
        html = _get_html()
        assert "function _currentFilterState" in html
        assert "custom[name.trim()] = _currentFilterState()" in html

    def test_delete_button_removes_custom_preset(self):
        html = _get_html()
        assert "delete custom[name]" in html
        assert "_saveCustomPresets(custom)" in html

    def test_delete_only_works_on_custom_presets(self):
        """Delete should only work when a custom: prefixed preset is selected."""
        html = _get_html()
        assert 'val.startsWith("custom:")' in html

    def test_custom_preset_optgroup_present(self):
        html = _get_html()
        assert 'id="customPresetGroup"' in html

    def test_populate_preset_options_called_on_init(self):
        html = _get_html()
        assert "_populatePresetOptions();" in html

    def test_preset_css_styles_present(self):
        html = _get_html()
        assert ".preset-group" in html
