"""Shared patterns and constants for price extraction."""

from __future__ import annotations

import re
from typing import Final

# Signal kinds for price observations
SIGNAL_SOLD: Final = "sold"
SIGNAL_BIN: Final = "bin"
SIGNAL_ASK: Final = "ask"
SIGNAL_CO: Final = "co"

# Confidence levels for each signal type
SIGNAL_CONFIDENCE: Final[dict[str, float]] = {
    SIGNAL_SOLD: 0.9,  # Completed transaction - highest confidence
    SIGNAL_BIN: 0.8,   # Buy-it-now price
    SIGNAL_ASK: 0.7,   # Asking price
    SIGNAL_CO: 0.6,    # Current offer
    "fg": 0.7,         # Generic FG mention
}

# Price patterns with associated signal kinds
# Each tuple: (pattern, signal_kind)
PRICE_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    (re.compile(r"sold\s*:?\s*(\d+)", re.I), SIGNAL_SOLD),
    (re.compile(r"bin\s*:?\s*(\d+)", re.I), SIGNAL_BIN),
    (re.compile(r"co\s*:?\s*(\d+)", re.I), SIGNAL_CO),
    (re.compile(r"ask(?:ing)?\s*:?\s*(\d+)", re.I), SIGNAL_ASK),
    (re.compile(r"(\d+(?:\.\d+)?)\s*fg\b", re.I), "fg"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*forum\s*gold\b", re.I), "fg"),
]


def get_signal_confidence(signal_kind: str) -> float:
    """Get confidence level for a signal kind.

    Args:
        signal_kind: The type of price signal

    Returns:
        Confidence score (0.0-1.0)
    """
    return SIGNAL_CONFIDENCE.get(signal_kind, 0.5)
