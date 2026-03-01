#!/usr/bin/env python3
"""Build a full catalog_price_map so every catalog item has a price status.

Price status values:
  - market:           Direct price_estimates match (variant_key starts with canonical_item_id)
  - variant_fallback: No exact match, but a related variant has a price estimate
  - heuristic_range:  No market data, but expert seed tier provides a bounded FG range
  - unknown:          No pricing information available

For sparse/non-tradeable combinations, emits bounded ranges (fg_min, fg_median, fg_max)
with explicit source_type — never fake point estimates.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path
from statistics import median


SEED_TIER_ORDER = {"TRASH": 0, "NONE": 1, "LOW": 2, "MED": 3, "HIGH": 4}

# ---------------------------------------------------------------------------
# Non-tradeable misc items (quest items, potions, scrolls, body parts, gold, etc.)
# These get heuristic_range with fg=0 and tradeable=0.
# ---------------------------------------------------------------------------
_NON_TRADEABLE_MISC_CODES: set[str] = {
    # Potions
    "elx", "hpo", "mpo", "hpf", "mpf", "vps", "yps", "rvs", "rvl", "wms",
    "hp1", "hp2", "hp3", "hp4", "hp5", "mp1", "mp2", "mp3", "mp4", "mp5",
    "bpl", "bps", "rpl", "rps", "hrb", "ice", "xyz",
    # Scrolls & tomes
    "tsc", "isc", "tbk", "ibk", "0sc", "tr1", "tr2",
    # Quest items & body parts
    "bks", "bkd", "brz", "eyz", "flg", "fng", "hrn", "hrt", "jaw", "scz", "spe",
    "g34", "j34", "ass", "bbb", "box", "luv", "mss", "qbr", "qey", "qhr", "std",
    "bey", "dhn", "mbr", "qll",
    # Gold, arrows, bolts, keys, ears
    "gld", "aqv", "cqv", "key", "ear", "tch",
    # Uber ancient materials (non-standard trade)
    "ua1", "ua2", "ua3", "ua4", "ua5",
}

# Gem tiers by quality prefix
_GEM_TIER_MAP: dict[str, str] = {
    "gc": "TRASH",   # Chipped
    "gf": "TRASH",   # Flawed
    "gs": "TRASH",   # Normal
    "gl": "NONE",    # Flawless
    "gp": "LOW",     # Perfect
    "gz": "NONE",    # Flawless (alt code)
    "sk": "TRASH",   # Skulls (chipped/flawed/normal)
}
# Override for perfect skulls and specific gems
_GEM_CODE_TIER: dict[str, str] = {
    "skz": "LOW",    # Perfect Skull
    "skl": "NONE",   # Flawless Skull
}

# Sunder charms and uber upgrade materials have some trade value
_MISC_TRADEABLE_OVERRIDES: dict[str, str] = {
    "cs2": "MED",    # Crafted Sunder Charm
    "um1": "LOW", "um2": "LOW", "um3": "LOW",
    "um4": "LOW", "um5": "LOW", "um6": "LOW",
}


def _category_default_tier(
    canonical_item_id: str,
    category: str,
    display_name: str,
) -> str:
    """Return a default seed tier for items without specific seed matches.

    This provides category-level heuristic pricing so most items get
    heuristic_range instead of unknown.
    """
    code = canonical_item_id.split(":", 1)[-1] if ":" in canonical_item_id else ""

    if category == "misc":
        if code in _NON_TRADEABLE_MISC_CODES:
            return "TRASH"  # non-tradeable, fg ≈ 0
        if code in _MISC_TRADEABLE_OVERRIDES:
            return _MISC_TRADEABLE_OVERRIDES[code]
        # Gems: tier by quality
        if code in _GEM_CODE_TIER:
            return _GEM_CODE_TIER[code]
        prefix2 = code[:2] if len(code) >= 2 else ""
        if prefix2 in _GEM_TIER_MAP:
            return _GEM_TIER_MAP[prefix2]
        # Generic amulet/ring base → NONE (magic/rare versions are traded, not the base)
        if code in ("amu", "rin", "vip"):
            return "NONE"
        # Worldstone shards
        if code.startswith("xa"):
            return "LOW"
        return "TRASH"  # remaining misc → non-tradeable

    if category == "base":
        # Most bases are worth very little unless elite/eth/socketed
        return "TRASH"

    if category == "unique":
        return "LOW"  # most uniques have some trade value

    if category == "set":
        return "LOW"  # most set items have some trade value

    if category == "charm":
        return "LOW"  # charms (generic GC/SC/LC) have trade value

    if category == "jewel":
        return "LOW"  # jewels have trade value

    if category == "essence":
        return "LOW"  # essences are tradeable

    if category == "token":
        return "MED"  # Token of Absolution

    if category == "key":
        return "LOW"  # keys of terror/hate/destruction

    if category == "keyset":
        return "MED"  # 3x3 keyset

    return ""


# Hardcoded fallback tier ranges when market data is too sparse to compute them.
# Based on typical D2R SC ladder FG values.
_FALLBACK_TIER_RANGES: dict[str, tuple[float, float, float]] = {
    "TRASH": (0.0, 0.0, 1.0),
    "NONE":  (1.0, 2.0, 5.0),
    "LOW":   (5.0, 15.0, 40.0),
    "MED":   (30.0, 80.0, 200.0),
    "HIGH":  (200.0, 500.0, 2000.0),
}


def _load_seed_entries(seed_file: Path | None) -> list[dict]:
    """Load expert seed entries from JSON file."""
    if seed_file is None or not seed_file.exists():
        return []
    try:
        raw = json.loads(seed_file.read_text(encoding="utf-8"))
    except Exception:
        return []
    entries_raw = raw.get("entries") if isinstance(raw, dict) else None
    if not isinstance(entries_raw, list):
        return []
    out: list[dict] = []
    for e in entries_raw:
        if not isinstance(e, dict):
            continue
        needle = str(e.get("needle") or "").strip().lower()
        tier = str(e.get("tier") or "").strip().upper()
        if not needle or tier not in SEED_TIER_ORDER:
            continue
        out.append({"needle": needle, "tier": tier})
    return out


# Inline seed hints (same as export_price_table_html.py SEED_VARIANT_HINTS).
_BUILTIN_SEED_HINTS: list[tuple[str, str]] = [
    ("annihilus", "HIGH"), ("hellfire_torch", "HIGH"), ("arachnid_mesh", "HIGH"),
    ("bul-kathos", "HIGH"), ("bk_wedding", "HIGH"), ("cold_rupture", "HIGH"),
    ("crack_of_the_heavens", "HIGH"), ("crown_of_ages", "HIGH"),
    ("deaths_fathom", "HIGH"), ("deaths_web", "HIGH"), ("griffons_eye", "HIGH"),
    ("harlequin_crest", "HIGH"), ("herald_of_zakarum", "HIGH"),
    ("highlords_wrath", "HIGH"), ("maras_kaleidoscope", "HIGH"),
    ("rainbow_facet", "HIGH"), ("skin_of_the_vipermagi", "HIGH"),
    ("tal_rashas_adjudication", "HIGH"), ("tal_rashas_guardianship", "HIGH"),
    ("the_oculus", "HIGH"), ("stone_of_jordan", "HIGH"),
    ("the_stone_of_jordan", "HIGH"), ("tyraels_might", "HIGH"),
    ("war_traveler", "HIGH"), ("wisp_projector", "HIGH"),
    ("andariels_visage", "MED"), ("chance_guards", "MED"),
    ("draculs_grasp", "MED"), ("gheeds_fortune", "MED"),
    ("gore_rider", "MED"), ("guillaumes_face", "MED"),
    ("homunculus", "MED"), ("metalgrid", "MED"),
    ("nightwings_veil", "MED"), ("ondals_wisdom", "MED"),
    ("ormus_robes", "MED"), ("raven_frost", "MED"),
    ("skullders_ire", "MED"), ("tal_rashas_fine-spun_cloth", "MED"),
    ("tal_rashas_horadric_crest", "MED"), ("tal_rashas_lidless_eye", "MED"),
    ("the_reapers_toll", "MED"), ("thunderstroke", "MED"),
    ("titans_revenge", "MED"), ("verdungos_hearty_cord", "MED"),
    ("waterwalk", "MED"), ("wizardspike", "MED"),
    ("magefist", "LOW"), ("nagelring", "LOW"),
    ("mosers_blessed_circle", "LOW"), ("jalals_mane", "LOW"),
    ("kiras_guardian", "LOW"), ("laying_of_hands", "LOW"),
    ("goldwrap", "LOW"), ("dwarf_star", "LOW"),
]


def _seed_tier_for_item(canonical_item_id: str, seed_entries: list[dict]) -> str:
    """Return seed tier for a canonical item id, or empty string."""
    cid = canonical_item_id.lower()
    # Check file-based seeds first
    for e in seed_entries:
        if e["needle"] in cid:
            return e["tier"]
    # Fallback to builtin hints
    for needle, tier in _BUILTIN_SEED_HINTS:
        if needle in cid:
            return tier
    return ""


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def _is_low_level_rune_cid(canonical_item_id: str) -> bool:
    """Return True for low-level runes (El..Lem => r01..r20)."""
    if not canonical_item_id.startswith("rune:"):
        return False
    # Form 1: rune:r01..r33
    if canonical_item_id.startswith("rune:r"):
        try:
            num = int(canonical_item_id.split(":r", 1)[1])
        except (ValueError, IndexError):
            return False
        return 1 <= num <= 20
    # Form 2: rune:tal / rune:sol / rune:lem, etc.
    low_rune_names = {
        "el", "eld", "tir", "nef", "eth", "ith", "tal", "ral", "ort", "thul",
        "amn", "sol", "shael", "dol", "hel", "io", "lum", "ko", "fal", "lem",
    }
    name = canonical_item_id.split(":", 1)[1].strip().lower()
    return name in low_rune_names


def _is_perfect_gem_row(row: dict) -> bool:
    """Return True for perfect gem rows in catalog_price_map."""
    if row.get("category") != "misc":
        return False
    name = str(row.get("display_name") or "").lower()
    cid = str(row.get("canonical_item_id") or "")
    return name.startswith("perfect ") or cid.startswith("misc:gp") or cid == "misc:skz"


def _load_recent_d2jsp_prices(
    conn: sqlite3.Connection,
    market_key: str,
    hours: int,
) -> dict[str, list[float]]:
    """Load recent d2jsp prices grouped by variant_key."""
    rows = conn.execute(
        """
        SELECT variant_key, price_fg
        FROM observed_prices
        WHERE market_key = ?
          AND source = 'd2jsp'
          AND price_fg IS NOT NULL
          AND price_fg > 0
          AND observed_at >= datetime('now', ?)
        """,
        (market_key, f"-{max(1, int(hours))} hours"),
    ).fetchall()
    out: dict[str, list[float]] = {}
    for r in rows:
        vk = r["variant_key"]
        out.setdefault(vk, []).append(float(r["price_fg"]))
    return out


def _normalize_variant_key_match(variant_key_matched: str | None) -> str | None:
    """Normalize stored variant_key_matched values (strip '(+N)' suffix)."""
    if not variant_key_matched:
        return None
    v = variant_key_matched.strip()
    marker = " (+"
    if marker in v:
        return v.split(marker, 1)[0].strip()
    return v


def _apply_low_rune_and_perfect_gem_refresh(
    price_map: dict[str, dict],
    cat_to_market: dict[str, list[str]],
    recent_prices_by_variant: dict[str, list[float]],
    deviation_threshold_pct: float,
) -> int:
    """Refresh low runes/perfect gems when current median is stale vs recent d2jsp.

    Returns number of adjusted rows.
    """
    adjusted = 0
    threshold = max(0.0, float(deviation_threshold_pct)) / 100.0
    # Anchor from Lem rune market (r20) to cap obvious low-rune parser contamination (e.g. Tal-set noise).
    lem_vals = sorted(recent_prices_by_variant.get("rune:lem", []))
    lem_anchor = _quantile(lem_vals, 0.50) if lem_vals else 30.0
    low_rune_cap = max(90.0, lem_anchor * 3.0)
    perfect_gem_cap = max(80.0, lem_anchor * 2.0)

    for cid, row in price_map.items():
        if not (_is_low_level_rune_cid(cid) or _is_perfect_gem_row(row)):
            continue

        prefixes = cat_to_market.get(cid, [cid])
        matched_recent: list[float] = []
        matched_vk: str | None = None
        for prefix in prefixes:
            for vk, vals in recent_prices_by_variant.items():
                if vk == prefix or vk.startswith(prefix + ":"):
                    matched_recent.extend(vals)
                    if matched_vk is None:
                        matched_vk = vk
        if not matched_recent:
            continue

        # Robust commodity cleanup:
        # - low runes: drop implausibly high observations to avoid Tal-set / title bleed contamination.
        # - perfect gems: cap high bleed/noise values.
        if _is_low_level_rune_cid(cid):
            filtered = [v for v in matched_recent if v <= low_rune_cap]
            recent_vals = sorted(filtered or matched_recent)
        elif _is_perfect_gem_row(row):
            filtered = [v for v in matched_recent if v <= perfect_gem_cap]
            recent_vals = sorted(filtered or matched_recent)
        else:
            recent_vals = sorted(matched_recent)
        recent_med = _quantile(recent_vals, 0.50)
        recent_lo = _quantile(recent_vals, 0.25)
        recent_hi = _quantile(recent_vals, 0.75)
        current_med = row.get("fg_median")

        should_update = False
        if current_med is None:
            should_update = True
        else:
            cur = float(current_med)
            rel_diff = abs(recent_med - cur) / max(cur, 1.0)
            should_update = rel_diff >= threshold

        if not should_update:
            continue

        row["price_status"] = "variant_fallback"
        row["source_type"] = "commodity_refresh_d2jsp_recent"
        row["fg_min"] = round(recent_lo, 1)
        row["fg_median"] = round(recent_med, 1)
        row["fg_max"] = round(recent_hi, 1)
        row["sample_count"] = len(recent_vals)
        row["confidence"] = "medium" if len(recent_vals) >= 5 else "low"
        row["variant_key_matched"] = matched_vk
        adjusted += 1
    return adjusted


def _apply_global_recent_refresh(
    price_map: dict[str, dict],
    recent_prices_by_variant: dict[str, list[float]],
    deviation_threshold_pct: float,
    min_samples: int,
) -> int:
    """Refresh any stale row from recent d2jsp median when deviation is high.

    Notes:
    - Excludes low-rune/perfect-gem rows (handled by commodity refresh pass).
    - Uses median + IQR (q25/q75) for robustness.
    """
    adjusted = 0
    threshold = max(0.0, float(deviation_threshold_pct)) / 100.0
    min_n = max(1, int(min_samples))

    for cid, row in price_map.items():
        if _is_low_level_rune_cid(cid) or _is_perfect_gem_row(row):
            continue
        cur = row.get("fg_median")
        vk = _normalize_variant_key_match(row.get("variant_key_matched"))
        if cur is None or not vk:
            continue
        vals = sorted(recent_prices_by_variant.get(vk, []))
        if len(vals) < min_n:
            continue
        rec_med = _quantile(vals, 0.50)
        rel_diff = abs(rec_med - float(cur)) / max(float(cur), 1.0)
        if rel_diff < threshold:
            continue

        row["price_status"] = "variant_fallback"
        row["source_type"] = "global_refresh_d2jsp_recent"
        row["fg_min"] = round(_quantile(vals, 0.25), 1)
        row["fg_median"] = round(rec_med, 1)
        row["fg_max"] = round(_quantile(vals, 0.75), 1)
        row["sample_count"] = len(vals)
        row["confidence"] = "medium" if len(vals) >= 5 else "low"
        adjusted += 1

    return adjusted


def _heuristic_ranges_by_tier(
    market_rows: list[dict],
) -> dict[str, tuple[float, float, float]]:
    """Compute (fg_min, fg_median, fg_max) heuristic ranges per seed tier from market data."""
    by_tier: dict[str, list[float]] = {}
    for r in market_rows:
        tier = r.get("seed_tier", "")
        est = r.get("estimate_fg")
        if not tier or est is None:
            continue
        by_tier.setdefault(tier, []).append(float(est))
    out: dict[str, tuple[float, float, float]] = {}
    for tier, vals in by_tier.items():
        if not vals:
            continue
        lo = round(_quantile(vals, 0.25), 1)
        med = round(_quantile(vals, 0.50), 1)
        hi = round(_quantile(vals, 0.75), 1)
        out[tier] = (lo, med, hi)
    return out



def _ensure_table(conn: sqlite3.Connection) -> None:
    """Create catalog_price_map table if it doesn't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS catalog_price_map (
            canonical_item_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            category TEXT NOT NULL,
            quality_class TEXT NOT NULL,
            tradeable INTEGER NOT NULL DEFAULT 1,
            price_status TEXT NOT NULL,  -- market|variant_fallback|heuristic_range|unknown
            source_type TEXT,            -- price_estimates|observed_prices|seed_heuristic|null
            fg_min REAL,
            fg_median REAL,
            fg_max REAL,
            sample_count INTEGER,
            confidence TEXT,
            seed_tier TEXT,
            variant_key_matched TEXT,    -- which variant_key provided the price
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cpm_status ON catalog_price_map(price_status);
        CREATE INDEX IF NOT EXISTS idx_cpm_category ON catalog_price_map(category);
    """)


def _slugify(name: str) -> str:
    """Slugify a display name to match market variant_key conventions."""
    import re
    s = name.lower()
    s = s.replace("&", " and ")
    s = s.replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _build_catalog_to_market_map(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Build a mapping from canonical_item_id -> list of possible market variant_key prefixes.

    The market uses slugified display names (e.g. base:cryptic_axe, rune:el, unique:griffons_eye)
    while the catalog uses game codes (e.g. base:7pa, rune:r01). This function bridges the gap.

    For uniques/sets, the catalog canonical_item_id uses the base item name (e.g. unique:diadem)
    but the market uses the unique item name (e.g. unique:griffons_eye). We resolve this via
    source_key (which stores the unique_index / set_index).
    """
    # Explicit overrides for catalog source_key -> market canonical_item_id mismatches.
    # Keys are catalog canonical_item_id, values are additional market prefixes to try.
    _MARKET_ALIAS_OVERRIDES: dict[str, list[str]] = {
        "unique:battle_boots": ["unique:war_traveler"],
        "unique:war_boots": ["unique:gore_rider"],
        "unique:dimensional_shard": ["unique:deaths_fathom"],
        "unique:unearthed_wand": ["unique:deaths_web"],
        "unique:troll_belt": ["unique:gheeds_fortune"],
        "unique:thresher": ["unique:reapers_toll"],
        "unique:russet_armor": ["unique:skulders_ire"],
        "unique:mithril_coil": ["unique:verdungos_hearty_cord"],
        "unique:spiderweb_sash": ["unique:arachnid_mesh"],
        "unique:diadem": ["unique:griffons_eye"],
        "unique:aerin_shield": ["unique:herald_of_zakarum"],
        "unique:spired_helm": ["unique:nightwings_veil"],
        "unique:bone_knife": ["unique:wizardspike"],
        "unique:bracers": ["unique:chance_guards"],
        "unique:vampirebone_gloves": ["unique:draculs_grasp"],
        "unique:demonhead": ["unique:andariels_visage"],
        "unique:slayer_guard": ["unique:arreats_face"],
        "unique:eldritch_orb": ["unique:eschutas_temper"],
        "unique:elder_staff": ["unique:ondals_wisdom"],
        "unique:ceremonial_javelin": ["unique:titans_revenge"],
        "unique:dream_spirit": ["unique:jalals_mane"],
        "unique:light_gauntlets": ["unique:magefist"],
        "unique:winged_helm": ["unique:guillaumes_face"],
        "unique:battle_guantlets": ["unique:laying_of_hands"],
        "unique:sky_spirit": ["unique:ravenlore"],
        "unique:scarab_husk": ["unique:skin_of_the_vipermagi"],
        "unique:ogre_gauntlets": ["unique:steelrend"],
        "unique:monarch": ["unique:stormshield"],
        "unique:demonhide_sash": ["unique:string_of_ears"],
        "unique:colossus_blade": ["unique:the_grandfather"],
        "unique:hydra_bow": ["unique:windforce"],
        "unique:kraken_shell": ["unique:leviathan"],
        "unique:sacred_armor": ["unique:tyraels_might"],
        "unique:bone_visage": ["unique:crown_of_ages"],
        "unique:tiara": ["unique:kiras_guardian"],
        "unique:war_belt": ["unique:goldwrap"],
        "unique:heavy_gloves": ["unique:chance_guards"],
        "unique:sharkskin_boots": ["unique:waterwalk"],
        "unique:scarabshell_boots": ["unique:sandstorm_trek"],
        "unique:lidless_wall": ["unique:lidless_wall"],
        # Set items that market uses unique: prefix for
        "set:winged_helm": ["unique:guillaumes_face"],
        "set:bramble_mitts": ["unique:laying_of_hands"],
        "set:ornate_plate": ["unique:griswolds_heart", "set:griswolds_heart"],
        "set:sacred_armor": ["set:immortal_kings_soul_cage"],
        "set:ogre_maul": ["set:immortal_kings_stone_crusher"],
        "set:chaos_armor": ["set:trang_ouls_scales"],
    }
    mapping: dict[str, list[str]] = {}
    rows = conn.execute(
        "SELECT canonical_item_id, display_name, category, base_code, source_table, source_key, metadata_json "
        "FROM catalog_items WHERE enabled = 1"
    ).fetchall()

    for r in rows:
        cid = r["canonical_item_id"]
        display = r["display_name"] or ""
        category = r["category"] or ""
        source_key = r["source_key"] or ""
        slug = _slugify(display)
        prefixes: list[str] = [cid]  # Always try the canonical id itself

        if category == "rune":
            # Catalog: rune:r01 (El Rune) -> market: rune:el
            rune_name = display.lower().replace(" rune", "").strip()
            if rune_name:
                prefixes.append(f"rune:{rune_name}")
        elif category == "base":
            # Catalog: base:7pa (Cryptic Axe) -> market: base:cryptic_axe
            prefixes.append(f"base:{slug}")
        elif category == "unique":
            # Catalog uses base name as display (e.g. "diadem" for Griffon's Eye).
            # source_key has the unique_index (e.g. "Griffon's Eye").
            prefixes.append(f"unique:{slug}")
            if source_key:
                source_slug = _slugify(source_key)
                prefixes.append(f"unique:{source_slug}")
        elif category == "set":
            prefixes.append(f"set:{slug}")
            if source_key:
                source_slug = _slugify(source_key)
                prefixes.append(f"set:{source_slug}")
        elif category == "key":
            pass
        elif category == "token":
            pass
        elif category == "essence":
            prefixes.append(f"essence:{slug}")
            # Market often uses "essence:mixed" for all essences
            prefixes.append("essence:mixed")
        elif category == "charm":
            prefixes.append(f"charm:{slug}")
        elif category == "jewel":
            prefixes.append(f"jewel:{slug}")
            if "rainbow" in display.lower() and "facet" in display.lower():
                prefixes.append("jewel:rainbow_facet")
            # Generic "Jewel" base matches rainbow_facet market data as fallback
            if slug == "jewel":
                prefixes.append("jewel:rainbow_facet")
        elif category == "keyset":
            pass
        elif category == "misc":
            prefixes.append(f"misc:{slug}")
            # Gems: try gem: prefix for market matching
            dn = display.lower()
            if any(g in dn for g in ("sapphire", "emerald", "ruby", "amethyst", "diamond", "topaz", "skull")):
                gem_slug = _slugify(display)
                prefixes.append(f"gem:{gem_slug}")
                # Perfect gems often traded as "gem:perfect_gems_mixed"
                if "perfect" in dn:
                    prefixes.append("gem:perfect_gems_mixed")
                    if "skull" in dn:
                        prefixes.append("gem:perfect_skull")
            # Worldstone shards
            if "worldstone" in dn and "shard" in dn:
                prefixes.append("consumable:worldstone_shard")

        mapping[cid] = list(dict.fromkeys(prefixes))  # dedupe preserving order

        # Apply explicit market alias overrides for known mismatches
        if cid in _MARKET_ALIAS_OVERRIDES:
            for alias in _MARKET_ALIAS_OVERRIDES[cid]:
                if alias not in mapping[cid]:
                    mapping[cid].append(alias)

    return mapping


def _build_seed_name_index(conn: sqlite3.Connection) -> dict[str, str]:
    """Build a reverse index: slugified unique/set name -> canonical_item_id.

    Used for seed tier matching: seeds use readable names like 'griffons_eye'
    but catalog canonical_item_ids use base names like 'unique:diadem'.
    """
    index: dict[str, str] = {}
    # Uniques: source_key = unique_index (the actual unique item name)
    rows = conn.execute(
        "SELECT canonical_item_id, source_key FROM catalog_items "
        "WHERE category = 'unique' AND source_key IS NOT NULL AND enabled = 1"
    ).fetchall()
    for r in rows:
        slug = _slugify(r["source_key"])
        if slug:
            index[slug] = r["canonical_item_id"]
    # Sets: source_key = set_index
    rows = conn.execute(
        "SELECT canonical_item_id, source_key FROM catalog_items "
        "WHERE category = 'set' AND source_key IS NOT NULL AND enabled = 1"
    ).fetchall()
    for r in rows:
        slug = _slugify(r["source_key"])
        if slug:
            index[slug] = r["canonical_item_id"]
    return index


def build_price_map(
    conn: sqlite3.Connection,
    market_key: str,
    seed_entries: list[dict],
    commodity_refresh_hours: int = 72,
    commodity_refresh_deviation_pct: float = 50.0,
    global_refresh_deviation_pct: float = 50.0,
    global_refresh_min_samples: int = 1,
) -> dict[str, dict]:
    """Build the full catalog price map.

    Returns dict of canonical_item_id -> row dict for reporting.
    """
    conn.row_factory = sqlite3.Row

    # 1. Load all catalog items
    catalog_items = conn.execute(
        "SELECT canonical_item_id, display_name, category, quality_class, tradeable FROM catalog_items WHERE enabled = 1"
    ).fetchall()

    # 2. Load all price_estimates for this market
    pe_rows = conn.execute(
        "SELECT variant_key, estimate_fg, range_low_fg, range_high_fg, confidence, sample_count "
        "FROM price_estimates WHERE market_key = ?",
        (market_key,),
    ).fetchall()
    pe_by_variant: dict[str, sqlite3.Row] = {r["variant_key"]: r for r in pe_rows}

    # 3. Load observed_prices aggregates per variant for fallback
    obs_agg = conn.execute(
        """
        SELECT variant_key, COUNT(*) as cnt, MIN(price_fg) as min_fg,
               MAX(price_fg) as max_fg, AVG(price_fg) as avg_fg
        FROM observed_prices
        WHERE market_key = ?
        GROUP BY variant_key
        """,
        (market_key,),
    ).fetchall()
    obs_by_variant: dict[str, sqlite3.Row] = {r["variant_key"]: r for r in obs_agg}

    # 4. Build catalog-to-market prefix mapping
    cat_to_market = _build_catalog_to_market_map(conn)

    # 4b. Build seed name index (unique/set source_key -> canonical_item_id)
    seed_name_index = _build_seed_name_index(conn)

    # 5. Build seed tier lookup and heuristic ranges
    market_with_seed: list[dict] = []
    for vk, pe in pe_by_variant.items():
        tier = _seed_tier_for_item(vk, seed_entries)
        if tier:
            market_with_seed.append({"seed_tier": tier, "estimate_fg": pe["estimate_fg"]})
    tier_ranges = _heuristic_ranges_by_tier(market_with_seed)

    # 6. For each catalog item, determine price status
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    # Pre-build a source_key lookup for seed matching
    source_keys: dict[str, str] = {}  # canonical_item_id -> source_key
    for ci in catalog_items:
        sk_rows = conn.execute(
            "SELECT source_key FROM catalog_items WHERE canonical_item_id = ?",
            (ci["canonical_item_id"],),
        ).fetchall()
        if sk_rows and sk_rows[0]["source_key"]:
            source_keys[ci["canonical_item_id"]] = sk_rows[0]["source_key"]

    result: dict[str, dict] = {}
    for ci in catalog_items:
        cid = ci["canonical_item_id"]
        row = {
            "canonical_item_id": cid,
            "display_name": ci["display_name"],
            "category": ci["category"],
            "quality_class": ci["quality_class"],
            "tradeable": ci["tradeable"],
            "price_status": "unknown",
            "source_type": None,
            "fg_min": None,
            "fg_median": None,
            "fg_max": None,
            "sample_count": None,
            "confidence": None,
            "seed_tier": _seed_tier_for_item(cid, seed_entries),
            "variant_key_matched": None,
            "updated_at": now_iso,
        }

        prefixes = cat_to_market.get(cid, [cid])

        # Strategy A: Price estimates match — aggregate ALL matching variants.
        # For bases, this rolls up sub-variants (eth/noneth/Xos) into a range.
        # For uniques, this rolls up class variants (torch:sorceress etc.).
        all_pe_matches: list[tuple[str, sqlite3.Row]] = []
        for prefix in prefixes:
            if prefix in pe_by_variant:
                all_pe_matches.append((prefix, pe_by_variant[prefix]))
            for vk, pe in pe_by_variant.items():
                if vk.startswith(prefix + ":"):
                    all_pe_matches.append((vk, pe))

        if all_pe_matches:
            # Aggregate: use weighted median across all matching variants
            total_samples = sum(pe["sample_count"] for _, pe in all_pe_matches)
            # Best single match (highest sample_count) for the primary estimate
            best_vk, best_pe = max(all_pe_matches, key=lambda x: x[1]["sample_count"])
            # Range spans all matched variants
            all_lows = [pe["range_low_fg"] for _, pe in all_pe_matches if pe["range_low_fg"] is not None]
            all_highs = [pe["range_high_fg"] for _, pe in all_pe_matches if pe["range_high_fg"] is not None]
            matched_vks = [vk for vk, _ in all_pe_matches]
            row["price_status"] = "market"
            row["source_type"] = "price_estimates"
            row["fg_min"] = min(all_lows) if all_lows else best_pe["range_low_fg"]
            row["fg_median"] = best_pe["estimate_fg"]
            row["fg_max"] = max(all_highs) if all_highs else best_pe["range_high_fg"]
            row["sample_count"] = total_samples
            row["confidence"] = best_pe["confidence"]
            row["variant_key_matched"] = best_vk if len(matched_vks) == 1 else f"{best_vk} (+{len(matched_vks)-1})"
            result[cid] = row
            continue

        # Strategy B: Observed prices fallback
        obs_matches: list[tuple[str, sqlite3.Row]] = []
        for prefix in prefixes:
            for vk, ob in obs_by_variant.items():
                if vk == prefix or vk.startswith(prefix + ":"):
                    obs_matches.append((vk, ob))

        if obs_matches:
            all_min = min(ob["min_fg"] for _, ob in obs_matches)
            all_max = max(ob["max_fg"] for _, ob in obs_matches)
            all_cnt = sum(ob["cnt"] for _, ob in obs_matches)
            all_avg = sum(ob["avg_fg"] * ob["cnt"] for _, ob in obs_matches) / max(all_cnt, 1)
            best_vk = max(obs_matches, key=lambda x: x[1]["cnt"])[0]
            row["price_status"] = "variant_fallback"
            row["source_type"] = "observed_prices"
            row["fg_min"] = round(all_min, 1)
            row["fg_median"] = round(all_avg, 1)
            row["fg_max"] = round(all_max, 1)
            row["sample_count"] = all_cnt
            row["confidence"] = "low"
            row["variant_key_matched"] = best_vk
            result[cid] = row
            continue

        # Strategy B2: Rune interpolation — for runes without market data,
        # interpolate from neighboring runes that do have prices.
        if ci["category"] == "rune" and cid.startswith("rune:r"):
            rune_num_str = cid.split(":r")[-1]
            try:
                rune_num = int(rune_num_str)
            except ValueError:
                rune_num = None
            if rune_num is not None:
                # Find nearest runes with market prices
                lo_price, hi_price = None, None
                for delta in range(1, 10):
                    if lo_price is None and rune_num - delta >= 1:
                        neighbor_cid = f"rune:r{rune_num - delta:02d}"
                        if neighbor_cid in result and result[neighbor_cid]["price_status"] in ("market", "variant_fallback"):
                            lo_price = result[neighbor_cid]["fg_median"]
                    if hi_price is None and rune_num + delta <= 33:
                        neighbor_cid = f"rune:r{rune_num + delta:02d}"
                        # Check pe_by_variant for forward runes not yet processed
                        for prefix in cat_to_market.get(neighbor_cid, [neighbor_cid]):
                            if prefix in pe_by_variant:
                                hi_price = pe_by_variant[prefix]["estimate_fg"]
                                break
                    if lo_price is not None and hi_price is not None:
                        break
                if lo_price is not None or hi_price is not None:
                    prices = [p for p in (lo_price, hi_price) if p is not None]
                    interp = round(sum(prices) / len(prices), 1)
                    row["price_status"] = "heuristic_range"
                    row["source_type"] = "rune_interpolation"
                    row["fg_min"] = round(min(prices) * 0.7, 1)
                    row["fg_median"] = interp
                    row["fg_max"] = round(max(prices) * 1.3, 1)
                    row["sample_count"] = 0
                    row["confidence"] = "seed"
                    result[cid] = row
                    continue

        # Also check seed tier against display_name slug and source_key (seeds use readable names)
        if not row["seed_tier"]:
            slug = _slugify(ci["display_name"])
            row["seed_tier"] = _seed_tier_for_item(slug, seed_entries)
        if not row["seed_tier"]:
            sk = source_keys.get(cid, "")
            if sk:
                row["seed_tier"] = _seed_tier_for_item(_slugify(sk), seed_entries)

        # Strategy C1: Category-level default tier for items without specific seeds
        if not row["seed_tier"]:
            row["seed_tier"] = _category_default_tier(cid, ci["category"], ci["display_name"])

        # Strategy C: Heuristic range from seed tier (market-derived or fallback)
        seed_tier = row["seed_tier"]
        if seed_tier:
            if seed_tier in tier_ranges:
                lo, med, hi = tier_ranges[seed_tier]
            elif seed_tier in _FALLBACK_TIER_RANGES:
                lo, med, hi = _FALLBACK_TIER_RANGES[seed_tier]
            else:
                lo, med, hi = None, None, None
            if lo is not None:
                row["price_status"] = "heuristic_range"
                row["source_type"] = "seed_heuristic"
                row["fg_min"] = lo
                row["fg_median"] = med
                row["fg_max"] = hi
                row["sample_count"] = 0
                row["confidence"] = "seed"
                result[cid] = row
                continue

        # Strategy D: Unknown
        result[cid] = row

    # 7. Commodity refresh pass:
    # For low-level runes and perfect gems, align stale medians to recent d2jsp observations.
    recent_prices = _load_recent_d2jsp_prices(conn, market_key, commodity_refresh_hours)
    _apply_low_rune_and_perfect_gem_refresh(
        result,
        cat_to_market=cat_to_market,
        recent_prices_by_variant=recent_prices,
        deviation_threshold_pct=commodity_refresh_deviation_pct,
    )
    _apply_global_recent_refresh(
        result,
        recent_prices_by_variant=recent_prices,
        deviation_threshold_pct=global_refresh_deviation_pct,
        min_samples=global_refresh_min_samples,
    )

    return result


def persist_price_map(conn: sqlite3.Connection, price_map: dict[str, dict]) -> int:
    """Write price_map to catalog_price_map table. Returns row count."""
    conn.execute("DELETE FROM catalog_price_map")
    count = 0
    for cid, row in price_map.items():
        conn.execute(
            """
            INSERT INTO catalog_price_map(
                canonical_item_id, display_name, category, quality_class, tradeable,
                price_status, source_type, fg_min, fg_median, fg_max,
                sample_count, confidence, seed_tier, variant_key_matched, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["canonical_item_id"], row["display_name"], row["category"],
                row["quality_class"], row["tradeable"],
                row["price_status"], row["source_type"],
                row["fg_min"], row["fg_median"], row["fg_max"],
                row["sample_count"], row["confidence"],
                row["seed_tier"], row["variant_key_matched"], row["updated_at"],
            ),
        )
        count += 1
    conn.commit()
    return count


def export_csv(price_map: dict[str, dict], out_path: Path) -> int:
    """Export catalog_price_map to CSV."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "canonical_item_id", "display_name", "category", "quality_class", "tradeable",
        "price_status", "source_type", "fg_min", "fg_median", "fg_max",
        "sample_count", "confidence", "seed_tier", "variant_key_matched",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(price_map.values(), key=lambda r: (r["category"], r["canonical_item_id"])):
            writer.writerow(row)
    return len(price_map)


def main() -> int:
    p = argparse.ArgumentParser(description="Build full catalog_price_map (every catalog item gets a price status)")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--seed-file", default="config/expert_trade_seeds.d2r.minimal.json",
                    help="Expert seed JSON file")
    p.add_argument("--csv-out", default="data/cache/catalog_price_map.csv", help="CSV output path")
    p.add_argument("--commodity-refresh-hours", type=int, default=72,
                   help="Recent d2jsp window (hours) for low-rune/perfect-gem refresh (default: 72)")
    p.add_argument("--commodity-refresh-deviation-pct", type=float, default=50.0,
                   help="Apply refresh when |recent-current|/current >= this pct (default: 50)")
    p.add_argument("--global-refresh-deviation-pct", type=float, default=50.0,
                   help="Global refresh threshold from recent d2jsp median (default: 50)")
    p.add_argument("--global-refresh-min-samples", type=int, default=1,
                   help="Minimum recent samples per variant for global refresh (default: 1)")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    seed_entries = _load_seed_entries(Path(args.seed_file) if args.seed_file else None)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_table(conn)

    price_map = build_price_map(
        conn,
        args.market_key,
        seed_entries,
        commodity_refresh_hours=args.commodity_refresh_hours,
        commodity_refresh_deviation_pct=args.commodity_refresh_deviation_pct,
        global_refresh_deviation_pct=args.global_refresh_deviation_pct,
        global_refresh_min_samples=args.global_refresh_min_samples,
    )
    count = persist_price_map(conn, price_map)
    conn.close()

    csv_count = export_csv(price_map, Path(args.csv_out))

    # Summary
    by_status: dict[str, int] = {}
    by_category: dict[str, dict[str, int]] = {}
    for row in price_map.values():
        st = row["price_status"]
        by_status[st] = by_status.get(st, 0) + 1
        cat = row["category"]
        by_category.setdefault(cat, {})
        by_category[cat][st] = by_category[cat].get(st, 0) + 1

    total = len(price_map)
    unknown_count = by_status.get("unknown", 0)
    unknown_pct = round(100 * unknown_count / max(total, 1), 1)

    if not args.quiet:
        print(f"catalog_price_map: {count} rows written to DB")
        print(f"CSV exported: {csv_count} rows to {args.csv_out}")
        print(f"\nPrice status breakdown:")
        for st in ["market", "variant_fallback", "heuristic_range", "unknown"]:
            n = by_status.get(st, 0)
            pct = round(100 * n / max(total, 1), 1)
            print(f"  {st:<20} {n:>5} ({pct}%)")
        print(f"  {'TOTAL':<20} {total:>5}")
        print(f"\nunknown_share={unknown_pct}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
