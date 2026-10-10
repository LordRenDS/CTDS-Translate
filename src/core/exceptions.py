"""Core domain exceptions for Chrono Trigger DS translation toolset."""

__all__ = [
    "CtdsError",
    "FontError",
    "GraphicsError",
    "RomError",
    "ValidationError",
]


class CtdsError(Exception):
    """Base exception for all errors raised by the CTDS translation toolset."""


class RomError(CtdsError):
    """Exception raised for errors during ROM unpacking, building, or integrity verification."""


class GraphicsError(CtdsError):
    """Exception raised for errors during graphics conversion, palette mapping, or sprite handling."""


class FontError(CtdsError, ValueError):
    """Exception raised for errors during font extraction, compilation, or Cyrillic injection."""


class ValidationError(CtdsError, ValueError):
    """Exception raised for errors during dialogue length validation, metric calculation, or reflow."""
