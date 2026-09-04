"""Tests for text validator font metrics and line width calculation."""

import pytest
from src.text_validator import (
    load_glyph_metrics,
    strip_control_tags,
    calculate_line_width_px,
    wrap_line_to_width,
    wrap_text_block,
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


def test_wrap_line_to_width_short_line():
    """Verify line within max_width_px is returned unchanged as a single element list."""
    widths = {'H': 8, 'e': 5, 'l': 3, 'o': 5, ' ': 3, 'w': 7, 'r': 4, 'd': 5}
    line = "Hello world"
    # Total width: 8+5+3+3+5 + 3 + 7+5+4+3+5 = 24 + 3 + 24 = 51 px
    res = wrap_line_to_width(line, widths, max_width_px=230)
    assert res == ["Hello world"]


def test_wrap_line_to_width_long_line_word_boundaries():
    """Verify long line wraps cleanly at word boundaries."""
    # Char width = 10px, space = 5px
    widths = {ch: 10 for ch in "abcdefghijklmnopqrstuvwxyz"}
    widths[' '] = 5

    # "aaa bbb ccc"
    # "aaa" = 30px
    # "aaa bbb" = 30 + 5 + 30 = 65px
    # "aaa bbb ccc" = 65 + 5 + 30 = 100px
    line = "aaa bbb ccc ddd"
    # With max_width_px = 70:
    # "aaa bbb" (65px <= 70)
    # "ccc ddd" (65px <= 70)
    res = wrap_line_to_width(line, widths, max_width_px=70)
    assert res == ["aaa bbb", "ccc ddd"]


def test_wrap_line_to_width_oversized_word():
    """Verify single word exceeding max_width_px is placed on its own line."""
    widths = {ch: 10 for ch in "abcdefghijklmnopqrstuvwxyz"}
    widths[' '] = 5
    # "a"*10 = 100px > 50px
    line = "short aaaaaaaaaa end"
    res = wrap_line_to_width(line, widths, max_width_px=50)
    assert res == ["short", "aaaaaaaaaa", "end"]


def test_wrap_line_to_width_preserves_control_tags():
    """Verify control tags stay attached to adjacent tokens without corruption."""
    widths = {ch: 10 for ch in "abcdefghijklmnopqrstuvwxyz,!"}
    widths[' '] = 5
    # hero token is 30px
    # "Hello {CRONO}, look here!{WAIT_KEY}"
    line = "{COLOR:01}aaa bbb ccc!{WAIT_KEY}"
    # "aaa bbb" = 65px
    # "ccc!{WAIT_KEY}" = 40px
    res = wrap_line_to_width(line, widths, max_width_px=70)
    assert res == ["{COLOR:01}aaa bbb", "ccc!{WAIT_KEY}"]

    # Hero tag preservation
    line_hero = "aaa {CRONO} bbb ccc"
    # hero_name_width_px = 30
    # "aaa {CRONO}" = 30 + 5 + 30 = 65px
    # "bbb ccc" = 30 + 5 + 30 = 65px
    res_hero = wrap_line_to_width(line_hero, widths, max_width_px=70, hero_name_width_px=30)
    assert res_hero == ["aaa {CRONO}", "bbb ccc"]


def test_wrap_text_block_preserves_existing_pages():
    """Verify existing {PAGE} delimiters are preserved."""
    widths = {ch: 5 for ch in "abcdefghijklmnopqrstuvwxyz0123456789 "}
    text = "Page 1 line 1\nPage 1 line 2{PAGE}Page 2 line 1"
    formatted, warnings = wrap_text_block(text, widths, max_width_px=230, max_lines=3)
    assert formatted == "Page 1 line 1\nPage 1 line 2{PAGE}Page 2 line 1"
    assert warnings == []


def test_wrap_text_block_auto_paginate_true():
    """Verify auto_paginate=True splits 4+ lines across pages with {PAGE}."""
    widths = {ch: 5 for ch in "abcdefghijklmnopqrstuvwxyz0123456789 "}
    text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    formatted, warnings = wrap_text_block(text, widths, max_width_px=230, max_lines=3, auto_paginate=True)
    assert formatted == "Line 1\nLine 2\nLine 3{PAGE}Line 4\nLine 5"
    assert warnings == []


def test_wrap_text_block_auto_paginate_false_warning():
    """Verify auto_paginate=False keeps 4+ lines and generates warning."""
    widths = {ch: 5 for ch in "abcdefghijklmnopqrstuvwxyz0123456789 "}
    text = "Line 1\nLine 2\nLine 3\nLine 4"
    formatted, warnings = wrap_text_block(text, widths, max_width_px=230, max_lines=3, auto_paginate=False)
    assert formatted == "Line 1\nLine 2\nLine 3\nLine 4"
    assert len(warnings) == 1
    assert warnings[0] == "Page has 4 lines (exceeds max 3)"


def test_wrap_text_block_with_line_tags():
    """Verify {LINE} tags are treated as line breaks and normalized."""
    widths = {ch: 5 for ch in "abcdefghijklmnopqrstuvwxyz0123456789 "}
    text = "Line 1{LINE}Line 2{LINE}Line 3"
    formatted, warnings = wrap_text_block(text, widths, max_width_px=230, max_lines=3)
    assert formatted == "Line 1\nLine 2\nLine 3"
    assert warnings == []


def test_wrap_text_block_wrapping_and_auto_paginate():
    """Verify wrapping long lines into multiple lines triggers auto_pagination."""
    widths = {ch: 10 for ch in "abcdefghijklmnopqrstuvwxyz "}
    # One long line: "aaa bbb ccc ddd eee fff ggg hhh"
    # With max_width_px = 70: each chunk of 2 words is ~65px.
    # 8 words -> 4 wrapped lines.
    # max_lines = 2 -> 2 pages with 2 lines each.
    text = "aaa bbb ccc ddd eee fff ggg hhh"
    formatted, warnings = wrap_text_block(text, widths, max_width_px=70, max_lines=2, auto_paginate=True)
    assert formatted == "aaa bbb\nccc ddd{PAGE}eee fff\nggg hhh"
    assert warnings == []


def test_wrap_text_block_empty():
    """Verify empty text block returns empty string and no warnings."""
    widths = {'a': 5}
    formatted, warnings = wrap_text_block("", widths)
    assert formatted == ""
    assert warnings == []

