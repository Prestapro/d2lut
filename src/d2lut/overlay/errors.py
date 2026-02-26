"""Overlay-specific exception classes for structured error handling.

Provides a hierarchy of exceptions for the overlay system so callers
can catch specific failure modes and log/display appropriate diagnostics.
"""

from __future__ import annotations


class OverlayError(Exception):
    """Base exception for all overlay system errors."""

    def __init__(self, message: str, detail: str | None = None):
        self.detail = detail
        super().__init__(message)


class OCRError(OverlayError):
    """Raised when OCR text extraction or preprocessing fails."""


class IdentificationError(OverlayError):
    """Raised when item identification / catalog matching fails."""


class PriceLookupError(OverlayError):
    """Raised when price lookup or market query fails."""


class ConfigurationError(OverlayError):
    """Raised when overlay configuration is invalid or cannot be loaded."""


class ScreenCaptureError(OverlayError):
    """Raised when screenshot capture fails."""
