"""Tests for core domain exception hierarchy."""

import pytest
from src.core.exceptions import (
    CtdsError,
    FontError,
    GraphicsError,
    RomError,
    ValidationError,
)


def test_exception_inheritance() -> None:
    assert issubclass(RomError, CtdsError)
    assert issubclass(GraphicsError, CtdsError)
    assert issubclass(FontError, CtdsError)
    assert issubclass(ValidationError, CtdsError)
    assert issubclass(CtdsError, Exception)


def test_exception_instantiation() -> None:
    err = RomError("Corrupted ROM header")
    assert str(err) == "Corrupted ROM header"
    assert isinstance(err, CtdsError)

    gfx_err = GraphicsError("Invalid palette bank")
    assert str(gfx_err) == "Invalid palette bank"
    assert isinstance(gfx_err, CtdsError)

    font_err = FontError("Missing glyph in font table")
    assert str(font_err) == "Missing glyph in font table"
    assert isinstance(font_err, CtdsError)

    val_err = ValidationError("Line exceeds pixel width")
    assert str(val_err) == "Line exceeds pixel width"
    assert isinstance(val_err, CtdsError)

    base_err = CtdsError("General CTDS error")
    assert str(base_err) == "General CTDS error"
    assert isinstance(base_err, Exception)
