"""Tests for text validator font metrics and line width calculation."""

import pytest
from src.text_validator import (
    load_glyph_metrics,
    strip_control_tags,
    calculate_line_width_px,
    HERO_TOKENS,
)


def test_load_glyph_metrics():
    """Verify loading glyph metrics from base font and Cyrillic overlay."""
    widths = load_glyph_metrics(
        "extracted fonts/msg/big/msgcmn.json",
        "assets/fonts/cyrillic_big.json"
    )
    assert ' ' in widths
    assert widths[' '] == 3  # Space width in big font
    assert 'A' in widths
    assert widths['A'] > 0
    assert 'А' in widths  # Cyrillic capital A
    assert widths['А'] > 0
    assert 'я' in widths  # Cyrillic lowercase ya
    assert widths['я'] > 0


def test_load_glyph_metrics_base_only():
    """Verify loading glyph metrics without Cyrillic font."""
    widths = load_glyph_metrics("extracted fonts/msg/big/msgcmn.json")
    assert ' ' in widths
    assert widths[' '] == 3
    assert 'A' in widths
    assert widths['A'] > 0


def test_load_glyph_metrics_missing_file():
    """Verify FileNotFoundError is raised when font json does not exist."""
    with pytest.raises(FileNotFoundError):
        load_glyph_metrics("nonexistent_font_path.json")


def test_load_glyph_metrics_fallback():
    """Verify fallback width for unmapped characters."""
    widths = load_glyph_metrics("extracted fonts/msg/big/msgcmn.json")
    # Character definitely not in base English font
    assert widths['\u20AC'] == 5  # Euro sign or unknown char falls back to 5px


def test_strip_control_tags():
    """Verify non-visual control tokens are stripped while hero tokens are preserved."""
    raw = "Hello {CRONO}, look here!{WAIT_KEY}{PAGE}"
    stripped = strip_control_tags(raw)
    assert "{WAIT_KEY}" not in stripped
    assert "{PAGE}" not in stripped
    assert "{CRONO}" in stripped
    assert stripped == "Hello {CRONO}, look here!"


def test_strip_control_tags_all_hero_tokens():
    """Verify all 8 hero name tokens are preserved."""
    for hero in HERO_TOKENS:
        text = f"Hero: {hero}!{{WAIT_KEY}}"
        stripped = strip_control_tags(text)
        assert hero in stripped
        assert "{WAIT_KEY}" not in stripped
        assert stripped == f"Hero: {hero}!"


def test_strip_control_tags_various_controls():
    """Verify various control tags (COLOR, TAG, GLYPH, LINE, SOUND, EVENT_SYNC) are stripped."""
    text = "{COLOR:01}{LINE}{TAG:2A}{GLYPH:100}{SOUND:03}{EVENT_SYNC:05}Dialogue{NULL}"
    stripped = strip_control_tags(text)
    assert stripped == "Dialogue"


def test_calculate_line_width_px():
    """Verify pixel width calculation for characters and spaces."""
    widths = {'a': 5, 'b': 5, ' ': 3, 'i': 2, 'C': 6}
    # "a b" -> 5 + 3 + 5 = 13 px
    w = calculate_line_width_px("a b", widths)
    assert w == 13


def test_calculate_line_width_px_with_hero_tag():
    """Verify hero tag width calculation with default and custom width."""
    widths = {'a': 5, 'b': 5, ' ': 3, 'i': 2, 'C': 6}
    # With hero tag {CRONO} estimated at default 30px
    w_hero = calculate_line_width_px("a {CRONO} b", widths, hero_name_width_px=30)
    assert w_hero == 5 + 3 + 30 + 3 + 5  # 46 px

    # With custom hero width
    w_custom = calculate_line_width_px("a {CRONO} b", widths, hero_name_width_px=45)
    assert w_custom == 5 + 3 + 45 + 3 + 5  # 61 px


def test_calculate_line_width_px_multiple_heroes():
    """Verify multiple hero tokens in a single line."""
    widths = {' ': 3, '&': 6}
    line = "{CRONO} & {MARLE}"
    # 30 + 3 + 6 + 3 + 30 = 72 px
    assert calculate_line_width_px(line, widths, hero_name_width_px=30) == 72


def test_calculate_line_width_px_with_non_visual_tags():
    """Verify non-visual tags do not add pixel width."""
    widths = {'a': 5, 'b': 5}
    line = "a{WAIT_KEY}{COLOR:02}b{PAGE}"
    assert calculate_line_width_px(line, widths) == 10


def test_calculate_line_width_px_fallback():
    """Verify unmapped characters use the 5px fallback."""
    widths = {'a': 5}
    line = "a?"  # '?' not in widths
    assert calculate_line_width_px(line, widths) == 5 + 5  # 10 px


def test_calculate_line_width_px_empty():
    """Verify empty string returns 0 width."""
    widths = {'a': 5}
    assert calculate_line_width_px("", widths) == 0
