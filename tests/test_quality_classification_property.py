"""Property-based tests for quality classification in CategoryAwareParser.

**Validates: Requirements 1.4, 7.2**

Property 2: Quality classification
- Quality classification is deterministic (same input → same output)
- Quality is always one of the valid values (set/unique/rare/magic/None)
- Items with known set markers always classify as "set"
- Items with known unique hints always classify as "unique"
- Quality inference doesn't overwrite existing quality values
"""

from __future__ import annotations

import hypothesis
from hypothesis import given, settings, assume
import hypothesis.strategies as st

from d2lut.overlay.category_aware_parser import CategoryAwareParser
from d2lut.overlay.ocr_parser import ParsedItem

VALID_QUALITIES = {"set", "unique", "rare", "magic", None}

SET_MARKERS = ["tal rasha", "immortal king", "m'avina", "griswold", "natalya"]
UNIQUE_HINTS = ["harlequin crest", "the stone of jordan", "arachnid mesh", "annihilus"]

# Strategy: printable text that avoids accidentally containing quality keywords
_safe_chars = st.sampled_from(
    list("abcdfghjklnopqtuvwxyz0123456789 -+%/")
)
safe_text = st.text(_safe_chars, min_size=0, max_size=60)


def _make_parsed(item_name: str = "", raw_text: str = "", quality: str | None = None) -> ParsedItem:
    return ParsedItem(
        raw_text=raw_text,
        item_name=item_name or None,
        quality=quality,
    )


parser = CategoryAwareParser()


# --- Property: determinism ---

@given(item_name=st.text(min_size=0, max_size=80), raw_text=st.text(min_size=0, max_size=120))
@settings(max_examples=200)
def test_quality_classification_is_deterministic(item_name: str, raw_text: str):
    """Same inputs always produce the same quality classification."""
    p1 = parser.parse_with_category(_make_parsed(item_name, raw_text))
    p2 = parser.parse_with_category(_make_parsed(item_name, raw_text))
    assert p1.quality == p2.quality


# --- Property: valid quality values ---

@given(item_name=st.text(min_size=0, max_size=80), raw_text=st.text(min_size=0, max_size=120))
@settings(max_examples=200)
def test_quality_is_always_valid(item_name: str, raw_text: str):
    """Quality must be one of set/unique/rare/magic/None."""
    result = parser.parse_with_category(_make_parsed(item_name, raw_text))
    assert result.quality in VALID_QUALITIES, f"Unexpected quality: {result.quality!r}"


# --- Property: set markers always classify as "set" ---

@given(
    marker=st.sampled_from(SET_MARKERS),
    prefix=safe_text,
    suffix=safe_text,
    in_name=st.booleans(),
)
@settings(max_examples=100)
def test_set_markers_classify_as_set(marker: str, prefix: str, suffix: str, in_name: bool):
    """Items containing a known set marker must classify as 'set'."""
    if in_name:
        item_name = f"{prefix} {marker} {suffix}"
        raw_text = suffix
    else:
        item_name = prefix
        raw_text = f"{prefix} {marker} {suffix}"
    result = parser.parse_with_category(_make_parsed(item_name, raw_text))
    assert result.quality == "set", (
        f"Expected 'set' for marker {marker!r}, got {result.quality!r}"
    )


# --- Property: unique hints always classify as "unique" ---

@given(
    hint=st.sampled_from(UNIQUE_HINTS),
    prefix=safe_text,
    suffix=safe_text,
    in_name=st.booleans(),
)
@settings(max_examples=100)
def test_unique_hints_classify_as_unique(hint: str, prefix: str, suffix: str, in_name: bool):
    """Items containing a known unique hint must classify as 'unique'."""
    # Avoid accidentally including a set marker that would take priority
    combined = f"{prefix} {hint} {suffix}".lower()
    assume(not any(m in combined for m in SET_MARKERS))

    if in_name:
        item_name = f"{prefix} {hint} {suffix}"
        raw_text = suffix
    else:
        item_name = prefix
        raw_text = f"{prefix} {hint} {suffix}"
    result = parser.parse_with_category(_make_parsed(item_name, raw_text))
    assert result.quality == "unique", (
        f"Expected 'unique' for hint {hint!r}, got {result.quality!r}"
    )


# --- Property: existing quality is never overwritten ---

@given(
    existing_quality=st.sampled_from(["set", "unique", "rare", "magic"]),
    item_name=st.text(min_size=0, max_size=80),
    raw_text=st.text(min_size=0, max_size=120),
)
@settings(max_examples=200)
def test_existing_quality_not_overwritten(existing_quality: str, item_name: str, raw_text: str):
    """When parsed.quality is already set, parse_with_category must preserve it."""
    result = parser.parse_with_category(_make_parsed(item_name, raw_text, quality=existing_quality))
    assert result.quality == existing_quality, (
        f"Quality changed from {existing_quality!r} to {result.quality!r}"
    )
