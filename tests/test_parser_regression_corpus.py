"""Parametrized regression tests for parser corpus entries.

Validates extract_props() and props_signature() against curated d2jsp excerpts
that exercise known parser gaps. Entries marked xfail are EXPECTED to fail on
unfixed code — this documents the gaps rather than hiding them.

Requirements: 25.3
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

from scripts.export_property_price_table_html import extract_props, props_signature

# ---------------------------------------------------------------------------
# Load corpus from fixture file (no __init__.py in tests/fixtures/)
# ---------------------------------------------------------------------------
_CORPUS_PATH = Path(__file__).parent / "fixtures" / "parser_regression_corpus.py"
_spec = importlib.util.spec_from_file_location("parser_regression_corpus", _CORPUS_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
CORPUS = _mod.CORPUS


def _corpus_id(entry: dict) -> str:
    """Short test ID from category + truncated excerpt."""
    cat = entry["category"]
    excerpt = entry["excerpt"][:40].replace(" ", "_")
    return f"{cat}::{excerpt}"


@pytest.mark.parametrize(
    "entry",
    CORPUS,
    ids=[_corpus_id(e) for e in CORPUS],
)
def test_corpus_entry(entry: dict) -> None:
    """Validate a single corpus entry against extract_props / props_signature.

    For xfail entries, pytest.xfail() is called so the test is marked as
    expected-failure rather than a hard failure.  This lets the suite stay
    green while documenting known parser gaps.
    """
    if entry["xfail"]:
        pytest.xfail(reason=entry["xfail_reason"])

    excerpt = entry["excerpt"]
    expected_fields = entry["expected_fields"]
    expected_sig = entry["expected_signature"]

    props = extract_props(excerpt)
    sig = props_signature(props)

    # Check expected fields
    for field_name, expected_value in expected_fields.items():
        actual = getattr(props, field_name, None)
        assert actual == expected_value, (
            f"Field {field_name!r}: expected {expected_value!r}, got {actual!r} "
            f"for excerpt {excerpt!r}"
        )

    # Check expected signature
    assert sig == expected_sig, (
        f"Signature mismatch for {excerpt!r}:\n"
        f"  expected: {expected_sig!r}\n"
        f"  actual:   {sig!r}"
    )
