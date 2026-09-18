import argparse
import json
import os
import pytest
from src.text_validator import (
    load_glyph_metrics,
    strip_control_tags,
    calculate_line_width_px,
    wrap_line_to_width,
    wrap_text_block,
    collapse_hyphenated_breaks,
    validate_and_format_file,
    validate_and_format_directory,
    split_word_carry,
    GlyphWidths,
    HERO_TOKENS,
    TextWindowPreset,
    WINDOW_PRESETS,
    get_preset_for_file,
    get_constraints_for_entry,
)
from src.cli import create_parser, cmd_validate_text_length


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
    """Verify non-visual control tags (COLOR, TAG, LINE, SOUND, EVENT_SYNC) are stripped while GLYPH placeholder is preserved."""
    text = "{COLOR:01}{LINE}{TAG:2A}{GLYPH:100}{SOUND:03}{EVENT_SYNC:05}Dialogue{NULL}"
    stripped = strip_control_tags(text)
    assert stripped == "{GLYPH:100}Dialogue"


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
    """Verify existing {PAGE} delimiters are preserved across both reflow and non-reflow modes."""
    widths = {ch: 5 for ch in "abcdefghijklmnopqrstuvwxyz0123456789 "}
    text = "Page 1 line 1\nPage 1 line 2{PAGE}Page 2 line 1"
    # When reflow=False, preserves existing newlines and {PAGE}
    formatted, warnings = wrap_text_block(text, widths, max_width_px=230, max_lines=3, reflow=False)
    assert formatted == "Page 1 line 1\nPage 1 line 2{PAGE}Page 2 line 1"
    assert warnings == []

    # When reflow=True (default), lines within page are collapsed, but {PAGE} is preserved
    formatted_reflow, warnings_reflow = wrap_text_block(text, widths, max_width_px=230, max_lines=3)
    assert formatted_reflow == "Page 1 line 1 Page 1 line 2{PAGE}Page 2 line 1"
    assert warnings_reflow == []


def test_wrap_text_block_auto_paginate_true():
    """Verify auto_paginate=True splits 4+ lines across pages with {PAGE}."""
    widths = {ch: 5 for ch in "abcdefghijklmnopqrstuvwxyz0123456789 "}
    text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    formatted, warnings = wrap_text_block(text, widths, max_width_px=230, max_lines=3, auto_paginate=True, reflow=False)
    assert formatted == "Line 1\nLine 2\nLine 3{PAGE}Line 4\nLine 5"
    assert warnings == []


def test_wrap_text_block_auto_paginate_false_warning():
    """Verify auto_paginate=False keeps 4+ lines and generates warning."""
    widths = {ch: 5 for ch in "abcdefghijklmnopqrstuvwxyz0123456789 "}
    text = "Line 1\nLine 2\nLine 3\nLine 4"
    formatted, warnings = wrap_text_block(text, widths, max_width_px=230, max_lines=3, auto_paginate=False, reflow=False)
    assert formatted == "Line 1\nLine 2\nLine 3\nLine 4"
    assert len(warnings) == 1
    assert warnings[0] == "Page has 4 lines (exceeds max 3)"


def test_wrap_text_block_with_line_tags():
    """Verify {LINE} tags are treated as line breaks and normalized when reflow=False."""
    widths = {ch: 5 for ch in "abcdefghijklmnopqrstuvwxyz0123456789 "}
    text = "Line 1{LINE}Line 2{LINE}Line 3"
    formatted, warnings = wrap_text_block(text, widths, max_width_px=230, max_lines=3, reflow=False)
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


def test_validate_file_dry_run(tmp_path):
    """Verify overflows are detected, warnings collected, but file is NOT modified when fix=False."""
    widths = {ch: 10 for ch in "abcdefghijklmnopqrstuvwxyz"}
    widths[' '] = 4
    # "a a a a a a a a" -> 8 * 10 + 7 * 4 = 108 px > 60 px
    data = [
        {"id": 0, "original_en": "short", "translation": "a a a a a a a a"}
    ]
    file_path = tmp_path / "test_dialogue.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    res = validate_and_format_file(
        str(file_path),
        glyph_widths=widths,
        max_width_px=60,
        fix=False,
    )

    assert res["file_path"] == str(file_path)
    assert res["total_entries"] == 1
    assert res["overflows_found"] == 1
    assert len(res["warnings"]) >= 1
    assert res["modified"] is False
    assert res["changes_count"] == 1

    # Verify original file on disk is unchanged
    with open(file_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded[0]["translation"] == "a a a a a a a a"


def test_validate_file_fix_in_place(tmp_path):
    """Verify file is overwritten with rewrapped text when fix=True."""
    widths = {ch: 10 for ch in "abcdefghijklmnopqrstuvwxyz"}
    widths[' '] = 4
    # "aaa bbb ccc ddd" -> wraps to ["aaa bbb", "ccc ddd"] at 70px
    data = [
        {"id": 1, "original_en": "aaa bbb ccc ddd", "translation": "aaa bbb ccc ddd"}
    ]
    file_path = tmp_path / "fix_in_place.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    res = validate_and_format_file(
        str(file_path),
        glyph_widths=widths,
        max_width_px=70,
        fix=True,
    )

    assert res["modified"] is True
    assert res["changes_count"] == 1
    assert res["overflows_found"] == 1

    # Verify file was updated on disk
    with open(file_path, "r", encoding="utf-8") as f:
        updated = json.load(f)
    assert updated[0]["translation"] == "aaa bbb\nccc ddd"


def test_validate_file_fix_out_path(tmp_path):
    """Verify file is written to new out_path, leaving source file untouched."""
    widths = {ch: 10 for ch in "abcdefghijklmnopqrstuvwxyz"}
    widths[' '] = 4
    data = [
        {"id": 2, "original_en": "aaa bbb ccc", "translation": "aaa bbb ccc"}
    ]
    src_path = tmp_path / "src.json"
    src_path.write_text(json.dumps(data), encoding="utf-8")
    out_path = tmp_path / "sub" / "out.json"

    res = validate_and_format_file(
        str(src_path),
        glyph_widths=widths,
        max_width_px=70,
        fix=True,
        out_path=str(out_path),
    )

    assert res["modified"] is True
    assert res["changes_count"] == 1
    assert out_path.is_file()

    # Source file remains untouched
    with open(src_path, "r", encoding="utf-8") as f:
        orig = json.load(f)
    assert orig[0]["translation"] == "aaa bbb ccc"

    # Out path has wrapped text
    with open(out_path, "r", encoding="utf-8") as f:
        dest = json.load(f)
    assert dest[0]["translation"] == "aaa bbb\nccc"


def test_validate_directory_batch(tmp_path):
    """Creates a temp directory with multiple JSON files, runs batch validation, verifies summary counts."""
    widths = {ch: 10 for ch in "abcdefghijklmnopqrstuvwxyz"}
    widths[' '] = 4

    dir1 = tmp_path / "folder1"
    dir2 = tmp_path / "folder2"
    dir1.mkdir()
    dir2.mkdir()

    # File 1: needs wrapping
    f1 = dir1 / "file1.json"
    f1.write_text(json.dumps([
        {"id": 0, "translation": "aaa bbb ccc ddd"}
    ]), encoding="utf-8")

    # File 2: already short, no wrapping needed
    f2 = dir1 / "file2.json"
    f2.write_text(json.dumps([
        {"id": 0, "translation": "short"}
    ]), encoding="utf-8")

    # File 3: in dir2, 2 entries (1 empty skipped, 1 needs wrapping)
    f3 = dir2 / "file3.json"
    f3.write_text(json.dumps([
        {"id": 0, "translation": ""},
        {"id": 1, "translation": "aaa bbb ccc ddd"}
    ]), encoding="utf-8")

    # Run batch validation in dry-run
    res = validate_and_format_directory(
        str(tmp_path),
        max_width_px=70,
        fix=False,
        glyph_widths=widths,
    )

    assert res["files_checked"] == 3
    assert res["files_modified"] == 0
    assert res["total_entries"] == 4
    assert res["total_overflows"] == 2
    assert len(res["file_reports"]) == 3

    # Now test with fix=True and out_dir
    out_dir = tmp_path / "output"
    res_fix = validate_and_format_directory(
        str(tmp_path),
        max_width_px=70,
        fix=True,
        out_dir=str(out_dir),
        glyph_widths=widths,
    )

    assert res_fix["files_checked"] == 3
    assert res_fix["files_modified"] == 3
    assert (out_dir / "folder1" / "file1.json").is_file()
    assert (out_dir / "folder1" / "file2.json").is_file()
    assert (out_dir / "folder2" / "file3.json").is_file()


def test_validate_file_dict_format(tmp_path):
    """Verify validation works when JSON format is a dict with 'entries' key."""
    widths = {ch: 10 for ch in "abcdefghijklmnopqrstuvwxyz"}
    widths[' '] = 4
    data = {
        "entries": [
            {"id": 0, "translation": "aaa bbb ccc ddd"}
        ]
    }
    file_path = tmp_path / "dict_format.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    res = validate_and_format_file(
        str(file_path),
        glyph_widths=widths,
        max_width_px=70,
        fix=True,
    )

    assert res["modified"] is True
    with open(file_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["entries"][0]["translation"] == "aaa bbb\nccc ddd"


def test_validate_file_custom_field(tmp_path):
    """Verify validation works on custom field (e.g., original_en)."""
    widths = {ch: 10 for ch in "abcdefghijklmnopqrstuvwxyz"}
    widths[' '] = 4
    data = [
        {"id": 0, "original_en": "aaa bbb ccc ddd", "translation": "short"}
    ]
    file_path = tmp_path / "custom_field.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    res = validate_and_format_file(
        str(file_path),
        glyph_widths=widths,
        max_width_px=70,
        field="original_en",
        fix=True,
    )

    assert res["changes_count"] == 1
    with open(file_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded[0]["original_en"] == "aaa bbb\nccc ddd"
    assert loaded[0]["translation"] == "short"


def test_validate_file_auto_paginate(tmp_path):
    """Verify auto_paginate=True splits lines into pages with {PAGE}."""
    widths = {ch: 5 for ch in "abcdefghijklmnopqrstuvwxyz0123456789 "}
    data = [
        {"id": 0, "translation": "Line 1\nLine 2\nLine 3\nLine 4"}
    ]
    file_path = tmp_path / "auto_paginate.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    res = validate_and_format_file(
        str(file_path),
        glyph_widths=widths,
        max_width_px=230,
        max_lines=3,
        auto_paginate=True,
        fix=True,
        reflow=False,
    )

    assert res["changes_count"] == 1
    assert res["modified"] is True
    with open(file_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded[0]["translation"] == "Line 1\nLine 2\nLine 3{PAGE}Line 4"


def test_validate_directory_with_real_font_metrics(tmp_path):
    """Verify batch validation works with real font files from disk and Russian Cyrillic text."""
    data = [
        {"id": 0, "translation": "Привет мир! Это очень длинная строка диалога на русском языке для проверки переноса строк."}
    ]
    json_path = tmp_path / "msg0.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    res = validate_and_format_directory(
        str(tmp_path),
        font_json_path="extracted fonts/msg/big/msgcmn.json",
        cyrillic_json_path="assets/fonts/cyrillic_big.json",
        max_width_px=230,
        fix=True,
    )

    assert res["files_checked"] == 1
    assert res["files_modified"] == 1
    assert res["total_overflows"] >= 1
    with open(json_path, "r", encoding="utf-8") as f:
        updated = json.load(f)
    assert "\n" in updated[0]["translation"]


def test_validate_directory_missing_dir():
    """Verify FileNotFoundError is raised when json_dir does not exist."""
    with pytest.raises(FileNotFoundError):
        validate_and_format_directory("nonexistent_directory_12345")


def test_cli_parser_validate_text_length():
    """Verify validate-text-length subcommand arguments parsing and defaults."""
    parser = create_parser()

    # Defaults
    args = parser.parse_args(["validate-text-length"])
    assert args.command == "validate-text-length"
    assert args.json_dir == "translated text"
    assert args.fix is False
    assert args.out is None
    assert args.max_width is None
    assert args.max_lines is None
    assert args.paginate is False
    assert args.font_json == "extracted fonts/msg/big/msgcmn.json"
    assert args.cyrillic_json == "assets/fonts/cyrillic_big.json"
    assert args.field == "translation"
    assert args.reflow is None
    assert args.preset == "auto"

    # Custom options
    args_custom = parser.parse_args([
        "validate-text-length",
        "--json-dir", "custom/dir",
        "--fix",
        "--out", "custom/out",
        "--max-width", "200",
        "--max-lines", "2",
        "--paginate",
        "--font-json", "custom/font.json",
        "--cyrillic-json", "custom/cyrillic.json",
        "--field", "original_en",
    ])
    assert args_custom.command == "validate-text-length"
    assert args_custom.json_dir == "custom/dir"
    assert args_custom.fix is True
    assert args_custom.out == "custom/out"
    assert args_custom.max_width == 200
    assert args_custom.max_lines == 2
    assert args_custom.paginate is True
    assert args_custom.font_json == "custom/font.json"
    assert args_custom.cyrillic_json == "custom/cyrillic.json"
    assert args_custom.field == "original_en"


def test_cli_parser_validate_text_lenght_alias():
    """Verify validate-text-lenght alias subcommand parses identically."""
    parser = create_parser()

    args = parser.parse_args(["validate-text-lenght"])
    assert args.command == "validate-text-lenght"
    assert args.json_dir == "translated text"
    assert args.fix is False
    assert args.out is None
    assert args.max_width is None
    assert args.max_lines is None
    assert args.paginate is False
    assert args.font_json == "extracted fonts/msg/big/msgcmn.json"
    assert args.cyrillic_json == "assets/fonts/cyrillic_big.json"
    assert args.field == "translation"
    assert args.reflow is None
    assert args.preset == "auto"

    args_custom = parser.parse_args([
        "validate-text-lenght",
        "--json-dir", "custom/dir",
        "--fix",
        "--out", "custom/out",
        "--max-width", "180",
        "--max-lines", "4",
        "--paginate",
        "--font-json", "custom/font.json",
        "--cyrillic-json", "custom/cyrillic.json",
        "--field", "original_en",
    ])
    assert args_custom.command == "validate-text-lenght"
    assert args_custom.json_dir == "custom/dir"
    assert args_custom.fix is True
    assert args_custom.out == "custom/out"
    assert args_custom.max_width == 180
    assert args_custom.max_lines == 4
    assert args_custom.paginate is True
    assert args_custom.font_json == "custom/font.json"
    assert args_custom.cyrillic_json == "custom/cyrillic.json"
    assert args_custom.field == "original_en"


def test_cli_cmd_dry_run_success_and_overflow(tmp_path, capsys):
    """Verify cmd_validate_text_length execution for dry-run success, overflow detection, and fix mode."""
    # 1. Nonexistent directory
    args_nonexistent = argparse.Namespace(
        json_dir=str(tmp_path / "does_not_exist"),
        font_json="extracted fonts/msg/big/msgcmn.json",
        cyrillic_json="assets/fonts/cyrillic_big.json",
        max_width=230,
        max_lines=3,
        paginate=False,
        field="translation",
        fix=False,
        out=None,
    )
    rc = cmd_validate_text_length(args_nonexistent)
    assert rc == 1
    captured = capsys.readouterr().out
    assert "Error: JSON directory not found" in captured

    # 2. Clean directory with 1 entry that fits
    clean_dir = tmp_path / "clean_dir"
    clean_dir.mkdir()
    (clean_dir / "clean.json").write_text(
        json.dumps([{"id": 0, "translation": "Hello"}]),
        encoding="utf-8",
    )
    args_clean = argparse.Namespace(
        json_dir=str(clean_dir),
        font_json="extracted fonts/msg/big/msgcmn.json",
        cyrillic_json="assets/fonts/cyrillic_big.json",
        max_width=230,
        max_lines=3,
        paginate=False,
        field="translation",
        fix=False,
        out=None,
    )
    rc_clean = cmd_validate_text_length(args_clean)
    assert rc_clean == 0
    captured_clean = capsys.readouterr().out
    assert "[DRY-RUN CHECK]" in captured_clean
    assert "Files inspected: 1" in captured_clean
    assert "Total entries checked: 1" in captured_clean
    assert "Overlong lines detected: 0" in captured_clean
    assert "Warnings: 0" in captured_clean
    assert "Files modified: 0" in captured_clean

    # 3. Overflowing file in dry-run mode (expect returncode 1)
    overflow_dir = tmp_path / "overflow_dir"
    overflow_dir.mkdir()
    (overflow_dir / "overflow.json").write_text(
        json.dumps([{"id": 0, "translation": "This is a very long line of text that exceeds sixty pixels."}]),
        encoding="utf-8",
    )
    args_overflow = argparse.Namespace(
        json_dir=str(overflow_dir),
        font_json="extracted fonts/msg/big/msgcmn.json",
        cyrillic_json="assets/fonts/cyrillic_big.json",
        max_width=60,
        max_lines=3,
        paginate=False,
        field="translation",
        fix=False,
        out=None,
    )
    rc_overflow = cmd_validate_text_length(args_overflow)
    assert rc_overflow == 1
    captured_overflow = capsys.readouterr().out
    assert "[DRY-RUN CHECK]" in captured_overflow
    assert "Overlong lines detected: 1" in captured_overflow
    assert "Detail lines for files with issues:" in captured_overflow

    # 4. Overflowing file in fix mode (expect returncode 0 and file modified)
    args_fix = argparse.Namespace(
        json_dir=str(overflow_dir),
        font_json="extracted fonts/msg/big/msgcmn.json",
        cyrillic_json="assets/fonts/cyrillic_big.json",
        max_width=60,
        max_lines=3,
        paginate=False,
        field="translation",
        fix=True,
        out=None,
    )
    rc_fix = cmd_validate_text_length(args_fix)
    assert rc_fix == 0
    captured_fix = capsys.readouterr().out
    assert "[FIX & FORMAT]" in captured_fix
    assert "Files modified: 1" in captured_fix


def test_wrap_text_block_reflow_default():
    """Verify ragged newlines inside a page are collapsed and packed cleanly up to max_width_px by default."""
    widths = {'a': 5, 'b': 5, 'c': 5, 'd': 5, ' ': 3}
    text = "a\nb c"
    # By default (reflow=True), "a\nb c" collapses to "a b c" (width: 5+3+5+3+5 = 21px <= 50px)
    wrapped, warnings = wrap_text_block(text, widths, max_width_px=50)
    assert wrapped == "a b c"
    assert "\n" not in wrapped
    assert warnings == []

    # Also test with multiple ragged lines packing into fewer lines
    text_multi = "a b\nc\nd"
    wrapped_multi, _ = wrap_text_block(text_multi, widths, max_width_px=50)
    assert wrapped_multi == "a b c d"


def test_wrap_text_block_no_reflow():
    """Verify that when reflow=False, existing newlines are preserved if each line is <= max_width_px."""
    widths = {'a': 5, 'b': 5, 'c': 5, ' ': 3}
    text = "a\nb c"
    # When reflow=False, preserves existing \n because each line is <= 50px
    wrapped, warnings = wrap_text_block(text, widths, max_width_px=50, reflow=False)
    assert wrapped == "a\nb c"
    assert warnings == []


def test_wrap_text_block_reflow_paragraphs_and_line_tags():
    """Verify double newlines define paragraphs and {LINE} tags collapse in reflow mode."""
    widths = {ch: 5 for ch in "abcdefghijklmnopqrstuvwxyz "}
    text = "first line\nsecond line\n\nnew para{LINE}line two"
    wrapped, warnings = wrap_text_block(text, widths, max_width_px=230)
    assert wrapped == "first line second line\nnew para line two"
    assert warnings == []


def test_validate_file_with_reflow(tmp_path):
    """Verify file validation formats with reflow by default and preserves breaks when reflow=False."""
    widths = {'a': 5, 'b': 5, 'c': 5, ' ': 3}
    data = [
        {"id": 0, "translation": "a\nb c"}
    ]
    file_path = tmp_path / "test_reflow.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    # Default reflow=True
    res = validate_and_format_file(
        str(file_path),
        glyph_widths=widths,
        max_width_px=50,
        fix=True,
    )
    assert res["modified"] is True
    assert res["changes_count"] == 1
    with open(file_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded[0]["translation"] == "a b c"

    # With reflow=False
    file_path_no_reflow = tmp_path / "test_no_reflow.json"
    file_path_no_reflow.write_text(json.dumps(data), encoding="utf-8")
    res_no_reflow = validate_and_format_file(
        str(file_path_no_reflow),
        glyph_widths=widths,
        max_width_px=50,
        fix=True,
        reflow=False,
    )
    assert res_no_reflow["modified"] is False
    assert res_no_reflow["changes_count"] == 0
    with open(file_path_no_reflow, "r", encoding="utf-8") as f:
        loaded_no_reflow = json.load(f)
    assert loaded_no_reflow[0]["translation"] == "a\nb c"


def test_validate_directory_with_reflow(tmp_path):
    """Verify validate_and_format_directory reflows text by default and respects reflow=False."""
    widths = {'a': 5, 'b': 5, 'c': 5, ' ': 3}
    d = tmp_path / "trans"
    d.mkdir()
    (d / "file.json").write_text(json.dumps([{"id": 0, "translation": "a\nb c"}]), encoding="utf-8")

    # With reflow=False
    res_no_reflow = validate_and_format_directory(
        str(d),
        max_width_px=50,
        fix=True,
        glyph_widths=widths,
        reflow=False,
    )
    assert res_no_reflow["files_modified"] == 0
    with open(d / "file.json", "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded[0]["translation"] == "a\nb c"

    # With reflow=True (default)
    res_default = validate_and_format_directory(
        str(d),
        max_width_px=50,
        fix=True,
        glyph_widths=widths,
    )
    assert res_default["files_modified"] == 1
    with open(d / "file.json", "r", encoding="utf-8") as f:
        loaded2 = json.load(f)
    assert loaded2[0]["translation"] == "a b c"


def test_cli_parser_reflow_flag():
    """Verify --no-reflow flag parser defaults and flag handling for validate-text-length and alias."""
    parser = create_parser()
    assert parser.parse_args(["validate-text-length"]).reflow is None
    assert parser.parse_args(["validate-text-length", "--no-reflow"]).reflow is False
    assert parser.parse_args(["validate-text-lenght", "--no-reflow"]).reflow is False


def test_cli_cmd_validate_text_length_no_reflow(tmp_path, capsys):
    """Verify cmd_validate_text_length preserves line breaks and displays banner when --no-reflow is passed."""
    test_dir = tmp_path / "text_dir"
    test_dir.mkdir()
    data = [{"id": 0, "translation": "first line\nsecond line"}]
    (test_dir / "test.json").write_text(json.dumps(data), encoding="utf-8")

    parser = create_parser()

    # 1. Test execution with --no-reflow flag
    args = parser.parse_args([
        "validate-text-length",
        "--json-dir", str(test_dir),
        "--fix",
        "--no-reflow",
    ])
    rc = cmd_validate_text_length(args)
    assert rc == 0
    captured = capsys.readouterr().out
    assert "Reflow existing breaks : Disabled" in captured

    with open(test_dir / "test.json", "r", encoding="utf-8") as f:
        content = json.load(f)
    assert content[0]["translation"] == "first line\nsecond line"

    # 2. Test execution without --no-reflow (default reflow=True)
    args_default = parser.parse_args([
        "validate-text-length",
        "--json-dir", str(test_dir),
        "--fix",
    ])
    rc_default = cmd_validate_text_length(args_default)
    assert rc_default == 0
    captured_default = capsys.readouterr().out
    assert "Reflow existing breaks : Enabled" in captured_default

    with open(test_dir / "test.json", "r", encoding="utf-8") as f:
        content_default = json.load(f)
    assert content_default[0]["translation"] == "first line second line"


def test_get_preset_for_file_matching():
    """Verify auto-detection of window presets for all 9 types and fallback to dialogue."""
    # 1. Dialogue files
    assert get_preset_for_file("msg01.json").name == "dialogue"
    assert get_preset_for_file("extracted text/msg/big/cmes2.json").name == "dialogue"
    assert get_preset_for_file("kmes0.json").name == "dialogue"
    assert get_preset_for_file("mesi_test.json").name == "dialogue"
    assert get_preset_for_file("mesk1.json").name == "dialogue"
    assert get_preset_for_file("mess2.json").name == "dialogue"
    assert get_preset_for_file("mest3.json").name == "dialogue"
    assert get_preset_for_file("exms4.json").name == "dialogue"
    assert get_preset_for_file("comu5.json").name == "dialogue"

    # 2. Tutorial / System hint files
    p_tut = get_preset_for_file("tutorial.json")
    assert p_tut.name == "tutorial"
    assert p_tut.max_lines == 6
    assert p_tut.max_width_px == 200
    assert p_tut.reflow is True
    assert p_tut.font_type == "big"
    assert get_preset_for_file("start.json").name == "dialogue"
    assert get_preset_for_file("ev_title.json").name == "chapter_title"

    # 3. Encyclopedia / Character bio files
    p_encyclopedia = get_preset_for_file("player.json")
    assert p_encyclopedia.name == "encyclopedia"
    assert p_encyclopedia.max_lines == 6
    assert p_encyclopedia.max_width_px == 136
    assert get_preset_for_file("ex_montec.json").name == "encyclopedia"
    assert get_preset_for_file("ex_itemget.json").name == "encyclopedia"
    assert get_preset_for_file("ex_illust.json").name == "encyclopedia"
    assert get_preset_for_file("ex_ending.json").name == "ending_desc"

    # 4. Item descriptions
    p_item_desc = get_preset_for_file("item_mes.json")
    assert p_item_desc.name == "item_desc"
    assert p_item_desc.max_lines == 1
    assert p_item_desc.max_width_px == 210
    assert p_item_desc.reflow is False
    assert get_preset_for_file("item_mes2.json").name == "item_desc"

    # 5. Item sub (short tooltips)
    p_item_sub = get_preset_for_file("item_sub.json")
    assert p_item_sub.name == "item_sub"
    assert p_item_sub.max_lines == 2
    assert p_item_sub.max_width_px == 110
    assert p_item_sub.reflow is False

    # 6. Item name
    p_item_name = get_preset_for_file("item.json")
    assert p_item_name.name == "item_name"
    assert p_item_name.max_lines == 1
    assert p_item_name.max_width_px == 105
    assert p_item_name.reflow is False
    assert get_preset_for_file("ex_item.json").name == "item_name"

    # 7. Battle tooltips
    p_battle = get_preset_for_file("battle.json")
    assert p_battle.name == "battle"
    assert p_battle.max_lines == 2
    assert p_battle.max_width_px == 180
    assert p_battle.reflow is True

    # 8. Menu screens
    p_menu = get_preset_for_file("menu.json")
    assert p_menu.name == "menu"
    assert p_menu.max_lines == 2
    assert p_menu.max_width_px == 200
    assert p_menu.reflow is False
    assert get_preset_for_file("wireless0.json").name == "menu"
    assert get_preset_for_file("ques0.json").name == "dialogue"

    # 9. Small system font files
    p_small = get_preset_for_file("msg/small/system.json")
    assert p_small.name == "small_system"
    assert p_small.max_lines == 1
    assert p_small.max_width_px == 130
    assert p_small.reflow is False
    assert p_small.font_type == "small"

    assert get_preset_for_file(r"msg\small\sfc_item.json").name == "small_system"
    assert get_preset_for_file("sfc_01.json").name == "small_system"
    assert get_preset_for_file("system.json").name == "small_system"

    # Fallback to dialogue
    assert get_preset_for_file("unknown_script.json").name == "dialogue"


def test_get_preset_for_file_explicit():
    """Verify explicit preset override and auto behavior."""
    # Explicit override takes priority over path
    p = get_preset_for_file("msg01.json", explicit_preset="tutorial")
    assert p.name == "tutorial"
    assert p.max_lines == 6

    p2 = get_preset_for_file("tutorial.json", explicit_preset="dialogue")
    assert p2.name == "dialogue"
    assert p2.max_lines == 3

    # explicit_preset="auto" or None uses path pattern matching
    assert get_preset_for_file("tutorial.json", explicit_preset="auto").name == "tutorial"
    assert get_preset_for_file("tutorial.json", explicit_preset=None).name == "tutorial"
    assert get_preset_for_file("msg01.json", explicit_preset="auto").name == "dialogue"

    # Invalid preset raises ValueError
    with pytest.raises(ValueError, match="Unknown window preset"):
        get_preset_for_file("msg01.json", explicit_preset="nonexistent_preset")


def test_validate_file_auto_preset_tutorial(tmp_path):
    """Verify tutorial.json allows up to 6 lines without warnings under auto-detected preset."""
    widths = {'a': 5, ' ': 3}
    data = [{"id": 0, "translation": "line1\n\nline2\n\nline3\n\nline4\n\nline5"}]
    file_path = tmp_path / "tutorial.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    # Auto preset resolves to tutorial (max_lines=6) -> 0 warnings
    res = validate_and_format_file(str(file_path), widths, preset="auto")
    assert res["preset"] == "tutorial"
    assert len(res["warnings"]) == 0

    # Overridden with dialogue preset (max_lines=3) -> warning for 5 lines
    res_dialogue = validate_and_format_file(str(file_path), widths, preset="dialogue")
    assert res_dialogue["preset"] == "dialogue"
    assert any("exceeds max 3" in w for w in res_dialogue["warnings"])



def test_validate_file_auto_preset_item_sub(tmp_path):
    """Verify item_sub.json applies 110px limit and reflow=False under auto-detected preset."""
    # 24 chars * 5px = 120px > 110px limit of item_sub, but < 230px of dialogue
    widths = {'a': 5, ' ': 3}
    data = [{"id": 0, "translation": "a" * 24}]
    file_path = tmp_path / "item_sub.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    # Auto preset resolves to item_sub (max_width_px=110) -> overflow detected
    res = validate_and_format_file(str(file_path), widths, preset="auto")
    assert res["preset"] == "item_sub"
    assert res["overflows_found"] == 1

    # Verify reflow=False preserves non-overflowing line breaks
    data_lines = [{"id": 0, "translation": "short1\nshort2"}]
    file_path_lines = tmp_path / "item_sub_lines.json"
    file_path_lines.write_text(json.dumps(data_lines), encoding="utf-8")
    res_lines = validate_and_format_file(
        str(file_path_lines), widths, preset="item_sub", fix=True
    )
    assert res_lines["modified"] is False
    with open(file_path_lines, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded[0]["translation"] == "short1\nshort2"


def test_validate_directory_auto_presets(tmp_path):
    """Verify validate_and_format_directory applies presets per-file and reports presets used."""
    widths = {'a': 5, ' ': 3}

    # tutorial file with 5 lines
    tut_file = tmp_path / "tutorial.json"
    tut_file.write_text(json.dumps([{"id": 0, "translation": "1\n2\n3\n4\n5"}]), encoding="utf-8")

    # item_sub file with 120px line (exceeds 110px)
    sub_file = tmp_path / "item_sub.json"
    sub_file.write_text(json.dumps([{"id": 0, "translation": "a" * 24}]), encoding="utf-8")

    # normal dialogue file
    msg_file = tmp_path / "msg01.json"
    msg_file.write_text(json.dumps([{"id": 0, "translation": "hello world"}]), encoding="utf-8")

    report = validate_and_format_directory(
        str(tmp_path),
        glyph_widths=widths,
        preset="auto",
    )

    assert report["files_checked"] == 3
    # tutorial has 0 overflows, msg01 has 0 overflows, item_sub has 1 overflow
    assert report["total_overflows"] == 1

    file_presets = {os.path.basename(r["file_path"]): r["preset"] for r in report["file_reports"]}
    assert file_presets["tutorial.json"] == "tutorial"
    assert file_presets["item_sub.json"] == "item_sub"
    assert file_presets["msg01.json"] == "dialogue"

    assert "presets_used" in report
    assert report["presets_used"]["tutorial"] == 1
    assert report["presets_used"]["item_sub"] == 1
    assert report["presets_used"]["dialogue"] == 1


def test_cli_parser_preset_flag():
    """Verify --preset argument choices, default value, and alias support."""
    parser = create_parser()

    # 1. Default should be "auto"
    args_default = parser.parse_args(["validate-text-length"])
    assert args_default.preset == "auto"

    # 2. Specific valid presets
    args_tutorial = parser.parse_args(["validate-text-length", "--preset", "tutorial"])
    assert args_tutorial.preset == "tutorial"

    args_item_sub = parser.parse_args(["validate-text-length", "--preset", "item_sub"])
    assert args_item_sub.preset == "item_sub"

    # 3. Alias validate-text-lenght
    args_alias = parser.parse_args(["validate-text-lenght", "--preset", "menu"])
    assert args_alias.preset == "menu"

    # 4. Invalid preset raises SystemExit (argparse error)
    with pytest.raises(SystemExit):
        parser.parse_args(["validate-text-length", "--preset", "invalid_preset"])


def test_cli_cmd_with_preset_auto(tmp_path, capsys):
    """Verify cmd_validate_text_length runs with --preset auto and outputs preset info."""
    test_dir = tmp_path / "text_dir"
    test_dir.mkdir()
    # tutorial.json: 5 lines (allowed in tutorial preset, which has max_lines=6)
    data_tut = [{"id": 0, "translation": "1\n2\n3\n4\n5"}]
    (test_dir / "tutorial.json").write_text(json.dumps(data_tut), encoding="utf-8")

    # item_sub.json: 24 'a's (120px > 110px limit for item_sub)
    data_sub = [{"id": 0, "translation": "a" * 24}]
    (test_dir / "item_sub.json").write_text(json.dumps(data_sub), encoding="utf-8")

    parser = create_parser()
    args = parser.parse_args([
        "validate-text-length",
        "--json-dir", str(test_dir),
        "--preset", "auto",
    ])
    # Expect return code 1 because item_sub.json overflows
    rc = cmd_validate_text_length(args)
    assert rc == 1

    captured = capsys.readouterr().out
    assert "Window preset          : auto" in captured
    assert "Preset: item_sub" in captured


def test_cli_cmd_with_explicit_override(tmp_path, capsys):
    """Verify explicit --max-width or --max-lines overrides preset defaults."""
    test_dir = tmp_path / "text_dir"
    test_dir.mkdir()
    # item_sub.json: 24 'a's (120px). item_sub default is 110px.
    # If user explicitly passes --max-width 150, 120px should NOT overflow!
    data_sub = [{"id": 0, "translation": "a" * 24}]
    (test_dir / "item_sub.json").write_text(json.dumps(data_sub), encoding="utf-8")

    parser = create_parser()
    args = parser.parse_args([
        "validate-text-length",
        "--json-dir", str(test_dir),
        "--preset", "auto",
        "--max-width", "150",
    ])
    rc = cmd_validate_text_length(args)
    assert rc == 0

    captured = capsys.readouterr().out
    assert "Overlong lines detected: 0" in captured


def test_cli_parser_file_arg():
    """Verify --file and --json-file argument parsing and defaults."""
    parser = create_parser()

    # 1. Default should be None
    args_default = parser.parse_args(["validate-text-length"])
    assert args_default.file is None

    # 2. --file flag
    args_file = parser.parse_args(["validate-text-length", "--file", "translated text/msg/big/tutorial.json"])
    assert args_file.file == "translated text/msg/big/tutorial.json"

    # 3. --json-file alias
    args_json_file = parser.parse_args(["validate-text-length", "--json-file", "translated text/msg/big/tutorial.json"])
    assert args_json_file.file == "translated text/msg/big/tutorial.json"

    # 4. Alias subcommand validate-text-lenght
    args_alias = parser.parse_args(["validate-text-lenght", "--file", "sample.json"])
    assert args_alias.file == "sample.json"

    args_alias_json = parser.parse_args(["validate-text-lenght", "--json-file", "sample.json"])
    assert args_alias_json.file == "sample.json"


def test_cli_cmd_single_file_dry_run_and_fix(tmp_path, capsys):
    """Verify single file validation via CLI handler in dry-run and fix mode with --out."""
    parser = create_parser()

    # 1. Non-existent file returns 1 and error message
    args_missing = parser.parse_args(["validate-text-length", "--file", "nonexistent_file.json"])
    rc_missing = cmd_validate_text_length(args_missing)
    assert rc_missing == 1
    captured_missing = capsys.readouterr().out
    assert "Error: JSON file not found: nonexistent_file.json" in captured_missing

    # 2. Dry-run with overflows on single file
    sample_file = tmp_path / "dialogue.json"
    long_line = "This is an extremely long dialogue line that will certainly exceed the maximum pixel width allowed for standard dialog boxes in the game."
    data = [{"id": 0, "translation": long_line}]
    sample_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    args_dry = parser.parse_args([
        "validate-text-length",
        "--file", str(sample_file),
    ])
    rc_dry = cmd_validate_text_length(args_dry)
    assert rc_dry == 1
    captured_dry = capsys.readouterr().out
    assert "=== Text Length & Dialogue Validation [DRY-RUN CHECK] ===" in captured_dry
    assert f"File: {str(sample_file)}" in captured_dry
    assert "Preset applied: dialogue" in captured_dry
    assert "Total entries checked: 1" in captured_dry
    assert "Overlong lines detected: 1" in captured_dry
    assert "Warnings:" in captured_dry
    assert "File modified: False" in captured_dry
    assert "Detail lines with issues:" in captured_dry

    # Check file was NOT modified on disk
    with open(sample_file, "r", encoding="utf-8") as f:
        disk_data = json.load(f)
    assert disk_data[0]["translation"] == long_line

    # 3. Fix mode with --out
    out_file = tmp_path / "fixed_dialogue.json"
    args_fix = parser.parse_args([
        "validate-text-length",
        "--file", str(sample_file),
        "--fix",
        "--out", str(out_file),
    ])
    rc_fix = cmd_validate_text_length(args_fix)
    assert rc_fix == 0
    captured_fix = capsys.readouterr().out
    assert "=== Text Length & Dialogue Validation [FIX & FORMAT] ===" in captured_fix
    assert "File modified: True" in captured_fix

    # Original file must still be unchanged
    with open(sample_file, "r", encoding="utf-8") as f:
        orig_data = json.load(f)
    assert orig_data[0]["translation"] == long_line

    # Out file must exist and have wrapped lines
    assert out_file.exists()
    with open(out_file, "r", encoding="utf-8") as f:
        fixed_data = json.load(f)
    assert "\n" in fixed_data[0]["translation"] or "{PAGE}" in fixed_data[0]["translation"]

    # 4. Clean file passing validation
    clean_file = tmp_path / "clean.json"
    clean_file.write_text(json.dumps([{"id": 0, "translation": "Short text."}], ensure_ascii=False), encoding="utf-8")
    args_clean = parser.parse_args(["validate-text-length", "--file", str(clean_file)])
    rc_clean = cmd_validate_text_length(args_clean)
    assert rc_clean == 0
    captured_clean = capsys.readouterr().out
    assert "Overlong lines detected: 0" in captured_clean
    assert "Warnings: 0" in captured_clean


def test_new_specialized_file_presets():
    """Verify new specialized presets for tech, monsters, locations, BGM, credits, and zukan."""
    # Tech names & descriptions
    p_tech = get_preset_for_file("tech.json")
    assert p_tech.name == "tech_name"
    assert p_tech.max_width_px == 80
    assert p_tech.max_lines == 1
    assert p_tech.reflow is False

    p_tec_mes = get_preset_for_file("tec_mes.json")
    assert p_tec_mes.name == "tech_desc"
    assert p_tec_mes.max_width_px == 190
    assert p_tec_mes.max_lines == 1
    assert p_tec_mes.reflow is False

    p_mon_tec = get_preset_for_file("mon_tec.json")
    assert p_mon_tec.name == "battle_banner"
    assert p_mon_tec.max_width_px == 238
    assert p_mon_tec.max_lines == 1
    assert p_mon_tec.reflow is False

    # Monster names
    p_mon = get_preset_for_file("monster.json")
    assert p_mon.name == "monster_name"
    assert p_mon.max_width_px == 85
    assert p_mon.max_lines == 1

    # Map locations
    p_map = get_preset_for_file("map.json")
    assert p_map.name == "map_location"
    assert p_map.max_width_px == 140
    assert p_map.max_lines == 1

    p_wmap = get_preset_for_file("w_map.json")
    assert p_wmap.name == "map_location"
    assert p_wmap.max_width_px == 140
    assert p_wmap.max_lines == 1

    # BGM tracks
    p_bgm = get_preset_for_file("bgm.json")
    assert p_bgm.name == "bgm_name"
    assert p_bgm.max_width_px == 145
    assert p_bgm.max_lines == 1

    # Credits & Staff roll
    p_cred = get_preset_for_file("endroll1.json")
    assert p_cred.name == "credits"
    assert p_cred.max_width_px == 180
    assert p_cred.max_lines == 1

    assert get_preset_for_file("endroll2.json").name == "credits"
    assert get_preset_for_file("staf.json").name == "credits"

    # Bestiary UI labels
    p_zukan = get_preset_for_file("zukan.json")
    assert p_zukan.name == "zukan"
    assert p_zukan.max_width_px == 80
    assert p_zukan.max_lines == 1

    # Quiz questions must be dialogue, NOT menu
    p_ques = get_preset_for_file("ques0.json")
    assert p_ques.name == "dialogue"
    assert p_ques.max_width_px == 238
    assert p_ques.max_lines == 3

    # system.json in msg/big must NOT be small_system
    p_sys_big = get_preset_for_file("msg/big/system.json")
    assert p_sys_big.name != "small_system"
    assert p_sys_big.font_type == "big"

    # system.json in msg/small MUST be small_system
    p_sys_small = get_preset_for_file("msg/small/system.json")
    assert p_sys_small.name == "small_system"
    assert p_sys_small.font_type == "small"


def test_entry_sub_preset_resolution():
    """Verify entry-specific UI constraints in menu.json and battle.json."""
    from src.text_validator import get_constraints_for_entry

    # In menu.json:
    # 1. Option labels (Settings 2-column table) -> max 110px, 1 line
    c_speed = get_constraints_for_entry("menu.json", 88)
    assert c_speed.max_width_px == 110
    assert c_speed.max_lines == 1

    # 2. Defaults button ([SELECT] Defaults) -> max 45px, 1 line
    c_defaults = get_constraints_for_entry("menu.json", 100)
    assert c_defaults.max_width_px == 45
    assert c_defaults.max_lines == 1

    # 3. Save & Apply button -> max 95px, 1 line
    c_save = get_constraints_for_entry("menu.json", 101)
    assert c_save.max_width_px == 95
    assert c_save.max_lines == 1

    # 4. Settings toggle (e.g. TYPE A) -> max 50px, 1 line
    c_type_a = get_constraints_for_entry("menu.json", 110)
    assert c_type_a.max_width_px == 50
    assert c_type_a.max_lines == 1

    # 5. Tab header (Battle II) -> max 65px, 1 line
    c_tab = get_constraints_for_entry("menu.json", 114)
    assert c_tab.max_width_px == 65
    assert c_tab.max_lines == 1

    # 6. Bottom screen hint bar -> max 205px, 1 line
    c_hint = get_constraints_for_entry("menu.json", 157)
    assert c_hint.max_width_px == 205
    assert c_hint.max_lines == 1

    # 7. Short stats (LV) -> max 70px, 1 line
    c_lv = get_constraints_for_entry("menu.json", 0)
    assert c_lv.max_width_px <= 70
    assert c_lv.max_lines == 1

    # In battle.json (calibrated against bg_win_btl_dwn_1.png):
    # Action commands -> max 80px, 1 line
    c_atk = get_constraints_for_entry("battle.json", 0)
    assert c_atk.max_width_px == 80
    assert c_atk.max_lines == 1

    # Status effects -> max 75px, 1 line
    c_poi = get_constraints_for_entry("battle.json", 8)
    assert c_poi.max_width_px == 75
    assert c_poi.max_lines == 1

    # Combat messages -> max 180px, 2 lines
    c_exp = get_constraints_for_entry("battle.json", 37)
    assert c_exp.max_width_px == 180
    assert c_exp.max_lines == 2


def test_validate_menu_catches_screenshot_bugs(tmp_path):
    """Verify validator flags the exact truncated strings seen in in-game screenshot."""
    big_metrics = load_glyph_metrics("extracted fonts/msg/big/msgcmn.json", "assets/fonts/cyrillic_big.json")

    # Entry 88: "Скорость Сообщений в Бою" (120px > 110px)
    # Entry 100: "По умолчанию" (62px > 45px)
    menu_data = [
        {"id": 88, "translation": "Скорость Сообщений в Бою"},
        {"id": 100, "translation": "По умолчанию"},
    ]
    menu_file = tmp_path / "menu.json"
    menu_file.write_text(json.dumps(menu_data, ensure_ascii=False, indent=2), encoding="utf-8")

    rep = validate_and_format_file(str(menu_file), glyph_widths=big_metrics, preset="auto")
    assert rep["overflows_found"] == 2
    assert any("Entry 88: line exceeds 110px (120px)" in w for w in rep["warnings"])
    assert any("Entry 100: line exceeds 45px (62px)" in w for w in rep["warnings"])

    # Now verify that shortened/fixed translations pass with 0 overflows:
    menu_data_fixed = [
        {"id": 88, "translation": "Скор. Сообщений"},
        {"id": 100, "translation": "Сброс"},
    ]
    menu_file_fixed = tmp_path / "menu_fixed.json"
    menu_file_fixed.write_text(json.dumps(menu_data_fixed, ensure_ascii=False, indent=2), encoding="utf-8")

    rep_fixed = validate_and_format_file(str(menu_file_fixed), glyph_widths=big_metrics, preset="auto")
    assert rep_fixed["overflows_found"] == 0
    assert len(rep_fixed["warnings"]) == 0


def test_menu_entry_naming_prompt_and_control_help():
    """Verify constraints for menu_naming_prompt (entry 141) and menu_control_help (entries 179..181)."""
    c_name = get_constraints_for_entry("menu.json", 141)
    assert c_name.name == "menu_naming_prompt"
    assert c_name.max_width_px == 220
    assert c_name.max_lines == 2
    assert c_name.reflow is True

    for eid in (179, 180, 181):
        c_help = get_constraints_for_entry("menu.json", eid)
        assert c_help.name == "menu_control_help"
        assert c_help.max_width_px == 224
        assert c_help.max_lines == 1
        assert c_help.reflow is False


def test_glyph_placeholder_width_calculation():
    """Verify {GLYPH:N} placeholder width calculation from glyph_by_idx and fallback."""
    widths = GlyphWidths({'a': 5, 'b': 5, ' ': 3}, glyph_by_idx={10: 14, 25: 20})

    # Exact match from glyph_by_idx
    w10 = calculate_line_width_px("{GLYPH:10}", widths)
    assert w10 == 14

    # Mixed text and glyph placeholder: "a {GLYPH:10} b" -> 5 + 3 + 14 + 3 + 5 = 30px
    w_mixed = calculate_line_width_px("a {GLYPH:10} b", widths)
    assert w_mixed == 30

    # Unmapped glyph index defaults to 5px (DEFAULT_CHAR_WIDTH_PX)
    w_unmapped = calculate_line_width_px("{GLYPH:999}", widths)
    assert w_unmapped == 5

    # Dynamic hero tokens keep width = 30px
    for token in ("{CRONO}", "{MARLE}", "{LUCCA}", "{ROBO}", "{FROG}", "{AYLA}", "{MAGUS}", "{EPOCH}"):
        assert calculate_line_width_px(token, widths) == 30

    # Purely non-visual control tokens have 0px width
    non_visual = "{WAIT_KEY}{PAGE}{LINE}{COLOR:01}{TAG:2B}{EVENT_SYNC:04}{SOUND:02}"
    assert calculate_line_width_px(non_visual, widths) == 0
    assert calculate_line_width_px(f"a{non_visual}b", widths) == 10


def test_split_word_carry_geo_mode():
    """Verify --carry geo word hyphenation behavior."""
    widths = {ch: 5 for ch in "abcdefghijklmnopqrstuvwxyzабвгдеёжзийклмнопрстуфхцчшщъыьэюя- "}

    # 1. Word >= 4 characters splits into prefix >= 2 and remainder >= 2 with hyphen '-'
    # "приключение": len 11, each letter 5px. Hyphen is 5px.
    # If available width is 35px: prefix of 6 letters ("приклю") + "-" = 7 * 5 = 35px.
    res = split_word_carry("приключение", available_width_px=35, glyph_widths=widths, mode="geo")
    assert res == ("приклю-", "чение")

    # 2. Greedy selection of longest valid prefix:
    # If available width is 45px: prefix of 8 letters ("приключе") + "-" = 9 * 5 = 45px.
    res_greedy = split_word_carry("приключение", available_width_px=45, glyph_widths=widths, mode="geo")
    assert res_greedy == ("приключе-", "ние")

    # 3. Available width too small to fit minimum prefix (2 chars) + hyphen (3 chars = 15px)
    res_too_small = split_word_carry("приключение", available_width_px=14, glyph_widths=widths, mode="geo")
    assert res_too_small is None

    # 4. Words < 4 characters are carried whole (return None)
    for short_word in ("кот", "он", "мир", "я", "да"):
        assert split_word_carry(short_word, available_width_px=50, glyph_widths=widths, mode="geo") is None

    # 5. Words with control tokens or placeholders are not split
    for tag_word in ("{CRONO}", "{GLYPH:10}", "{WAIT_KEY}", "ге{TAG}рой"):
        assert split_word_carry(tag_word, available_width_px=50, glyph_widths=widths, mode="geo") is None


def test_split_word_carry_syllable_mode():
    """Verify --carry syllable obeys Russian syllable hyphenation rules."""
    widths = {ch: 5 for ch in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя- "}

    # 1. Both parts must contain at least one vowel
    # "стол" and "всплеск" have only 1 vowel, cannot split
    assert split_word_carry("стол", available_width_px=50, glyph_widths=widths, mode="syllable") is None
    assert split_word_carry("всплеск", available_width_px=50, glyph_widths=widths, mode="syllable") is None

    # 2. Do not detach ь, ъ, й (they stay with the preceding part)
    # "майка" -> "май-ка" (not "ма-йка")
    res_maika = split_word_carry("майка", available_width_px=50, glyph_widths=widths, mode="syllable")
    assert res_maika == ("май-", "ка")

    # "подъезд" -> "подъ-езд" (not "под-ъезд")
    res_pod = split_word_carry("подъезд", available_width_px=50, glyph_widths=widths, mode="syllable")
    assert res_pod == ("подъ-", "езд")

    # "мальчик" -> "маль-чик" (not "мал-ьчик")
    res_mal = split_word_carry("мальчик", available_width_px=50, glyph_widths=widths, mode="syllable")
    assert res_mal == ("маль-", "чик")

    # 3. Double consonants between vowels split between them ("ван-ная", not "ва-нная")
    res_van = split_word_carry("ванная", available_width_px=50, glyph_widths=widths, mode="syllable")
    assert res_van == ("ван-", "ная")

    # 4. Prefix >= 2, remainder >= 2:
    # "окно" -> "ок-но" (both parts len 2, vowels in both)
    res_okno = split_word_carry("окно", available_width_px=50, glyph_widths=widths, mode="syllable")
    assert res_okno == ("ок-", "но")


def test_wrap_text_block_force_repack():
    """Verify --force completely collapses text and repacks into clean lines/pages."""
    widths = {ch: 5 for ch in "abcdefghijklmnopqrstuvwxyz0123456789 "}
    # Text where original lines fit under 220px, but lines are ragged across existing {PAGE}
    text = "Line 1\nLine 2{PAGE}Line 3\nLine 4"

    # force=False preserves existing {PAGE} and line breaks when within width
    formatted_normal, _ = wrap_text_block(text, widths, max_width_px=220, max_lines=2, auto_paginate=True, force=False)
    assert "{PAGE}" in formatted_normal

    # force=True collapses all newlines and {PAGE} into single flow:
    # "Line 1 Line 2 Line 3 Line 4" has 29 chars * 5px = 145px <= 220px -> fits on 1 line!
    formatted_forced, warnings = wrap_text_block(text, widths, max_width_px=220, max_lines=2, auto_paginate=True, force=True)
    assert formatted_forced == "Line 1 Line 2 Line 3 Line 4"
    assert "{PAGE}" not in formatted_forced
    assert "\n" not in formatted_forced
    assert len(warnings) == 0

    # force=True with auto_paginate=True when lines exceed max_lines
    formatted_paged, _ = wrap_text_block(
        "one two three four five six seven eight",
        widths,
        max_width_px=50,
        max_lines=2,
        auto_paginate=True,
        force=True,
    )
    pages = formatted_paged.split("{PAGE}")
    assert len(pages) >= 2
    for page in pages:
        assert len(page.split("\n")) <= 2

    # force=True with auto_paginate=False generates warning if lines exceed max_lines
    formatted_no_paged, warn_no_paged = wrap_text_block(
        "one two three four five six seven eight",
        widths,
        max_width_px=50,
        max_lines=2,
        auto_paginate=False,
        force=True,
    )
    assert "{PAGE}" not in formatted_no_paged
    assert any("exceeds max 2" in w for w in warn_no_paged)


def test_wrap_text_block_carry_integration():
    """Verify wrap_text_block integrates word hyphenation via carry parameter."""
    widths = {ch: 5 for ch in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя- "}
    # "герои приключение"
    # "герои" (5 chars * 5 = 25px) + space (5px) = 30px.
    # max_width_px = 65px -> remaining available width = 35px.
    # "приключение" with carry="geo" in 35px splits into "приклю-" (35px) and remainder "чение".
    text = "герои приключение"
    formatted, warnings = wrap_text_block(text, widths, max_width_px=65, carry="geo", reflow=True)
    lines = formatted.split("\n")
    assert lines[0] == "герои приклю-"
    assert lines[1] == "чение"
    assert len(warnings) == 0


def test_cli_force_and_carry_arguments_and_execution(tmp_path, capsys):
    """Verify CLI parser and execution with --force and --carry flags."""
    parser = create_parser()

    # 1. Defaults
    args_default = parser.parse_args(["validate-text-length"])
    assert args_default.force is False
    assert args_default.carry is None

    # 2. --force flag
    args_force = parser.parse_args(["validate-text-length", "--force"])
    assert args_force.force is True

    # 3. --carry flag alone defaults to const "geo"
    args_carry_default = parser.parse_args(["validate-text-length", "--carry"])
    assert args_carry_default.carry == "geo"

    # 4. --carry with explicit choices
    args_carry_geo = parser.parse_args(["validate-text-length", "--carry", "geo"])
    assert args_carry_geo.carry == "geo"

    args_carry_syl = parser.parse_args(["validate-text-length", "--carry", "syllable"])
    assert args_carry_syl.carry == "syllable"

    # 5. Combined flags on alias
    args_alias = parser.parse_args(["validate-text-lenght", "--force", "--carry"])
    assert args_alias.force is True
    assert args_alias.carry == "geo"

    # 6. Execution logs display Force repacking and Word carry status
    sample_file = tmp_path / "msg01.json"
    sample_file.write_text(json.dumps([{"id": 0, "translation": "привет мир"}]), encoding="utf-8")

    args_run = parser.parse_args([
        "validate-text-length",
        "--file", str(sample_file),
        "--force",
        "--carry", "syllable",
    ])
    rc = cmd_validate_text_length(args_run)
    assert rc == 0
    captured = capsys.readouterr().out
    assert "Force repacking        : Enabled" in captured
    assert "Word carry (hyphen)    : syllable" in captured


def test_collapse_hyphenated_breaks():
    """Verify collapse_hyphenated_breaks properly recombines split words and preserves compounds."""
    # 1. Basic carry hyphen
    assert collapse_hyphenated_breaks("пре-\nкрасный") == "прекрасный"
    assert collapse_hyphenated_breaks("пре-\r\nкрасный") == "прекрасный"

    # 2. Carry across {LINE} and {PAGE}
    assert collapse_hyphenated_breaks("стро-{LINE}ка") == "строка"
    assert collapse_hyphenated_breaks("сло-\n{PAGE}во") == "слово"
    assert collapse_hyphenated_breaks("сло-{PAGE}\nво") == "слово"

    # 3. Preserving genuine compounds
    assert collapse_hyphenated_breaks("что-\nто") == "что-то"
    assert collapse_hyphenated_breaks("из-\nза") == "из-за"
    assert collapse_hyphenated_breaks("из-\nпод") == "из-под"
    assert collapse_hyphenated_breaks("где-\nнибудь") == "где-нибудь"
    assert collapse_hyphenated_breaks("кто-\nлибо") == "кто-либо"
    assert collapse_hyphenated_breaks("по-\nмоему") == "по-моему"
    assert collapse_hyphenated_breaks("во-\nпервых") == "во-первых"
    assert collapse_hyphenated_breaks("в-\nтретьих") == "в-третьих"
    assert collapse_hyphenated_breaks("кое-\nкто") == "кое-кто"
    assert collapse_hyphenated_breaks("смотри-\nка") == "смотри-ка"

    # 4. Standard words that should NOT be hyphenated even if starting with common prefixes
    assert collapse_hyphenated_breaks("по-\nшел") == "пошел"
    assert collapse_hyphenated_breaks("из-\nвестный") == "известный"
    assert collapse_hyphenated_breaks("во-\nрота") == "ворота"
    assert collapse_hyphenated_breaks("в-\nместе") == "вместе"
    assert collapse_hyphenated_breaks("руч-\nка") == "ручка"
    assert collapse_hyphenated_breaks("ле-\nто") == "лето"


def test_wrap_text_block_roundtrip_reflow_force():
    """Verify text split with --carry can be roundtrip re-wrapped with force=True without orphan hyphens."""
    widths = {ch: 5 for ch in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя- "}
    text = "герои приключение"

    # Wrap with carry="geo" and narrow width (65px) so "приключение" gets split:
    formatted, warnings = wrap_text_block(text, widths, max_width_px=65, carry="geo", reflow=True)
    assert formatted == "герои приклю-\nчение"
    assert len(warnings) == 0

    # Re-wrap that result with force=True and a wider max_width_px (100px):
    # The word "приключение" must be recombined without orphan hyphens or stray spaces!
    re_wrapped_wide, _ = wrap_text_block(formatted, widths, max_width_px=100, force=True)
    assert re_wrapped_wide == "герои приключение"
    assert "-" not in re_wrapped_wide

    # Re-wrap with reflow=True and wider max_width_px without force:
    re_wrapped_reflow, _ = wrap_text_block(formatted, widths, max_width_px=100, reflow=True)
    assert re_wrapped_reflow == "герои приключение"
    assert "-" not in re_wrapped_reflow

    # Re-wrap with force=True and same max_width_px (65px) without carry:
    # "приключение" (55px <= 65px) should move to line 2 whole without hyphens
    re_wrapped_same, _ = wrap_text_block(formatted, widths, max_width_px=65, force=True, carry=None)
    assert re_wrapped_same == "герои\nприключение"
    assert "-" not in re_wrapped_same


def test_calibrated_window_presets():
    """Verify calibrated window presets and new preset mappings."""
    # Dialogue: 238px, 3 lines
    p_diag = WINDOW_PRESETS["dialogue"]
    assert p_diag.max_width_px == 238
    assert p_diag.max_lines == 3
    assert p_diag.reflow is True

    # Tutorial: 200px, 6 lines, only tutorial.json
    p_tut = WINDOW_PRESETS["tutorial"]
    assert p_tut.max_width_px == 200
    assert p_tut.max_lines == 6
    assert get_preset_for_file("tutorial.json").name == "tutorial"

    # Chapter Title: 130px, 1 line, ev_title.json
    p_chap = get_preset_for_file("ev_title.json")
    assert p_chap.name == "chapter_title"
    assert p_chap.max_width_px == 130
    assert p_chap.max_lines == 1
    assert p_chap.reflow is False

    # Battle Banner: 238px, 1 line, mon_tec.json
    p_btl_banner = get_preset_for_file("mon_tec.json")
    assert p_btl_banner.name == "battle_banner"
    assert p_btl_banner.max_width_px == 238
    assert p_btl_banner.max_lines == 1

    # Ending Desc: 224px, 2 lines, ex_ending.json
    p_ending = get_preset_for_file("ex_ending.json")
    assert p_ending.name == "ending_desc"
    assert p_ending.max_width_px == 224
    assert p_ending.max_lines == 2

    # Encyclopedia: 136px, 6 lines
    p_encycl = WINDOW_PRESETS["encyclopedia"]
    assert p_encycl.max_width_px == 136
    assert p_encycl.max_lines == 6
    assert get_preset_for_file("player.json").name == "encyclopedia"
    assert get_preset_for_file("ex_mon.json").name == "encyclopedia"

    # Item Desc & Tech Desc: 1 line strict
    p_item = WINDOW_PRESETS["item_desc"]
    assert p_item.max_width_px == 210
    assert p_item.max_lines == 1
    assert p_item.reflow is False

    p_tech = WINDOW_PRESETS["tech_desc"]
    assert p_tech.max_width_px == 190
    assert p_tech.max_lines == 1
    assert p_tech.reflow is False

    # Map location & Zukan
    assert WINDOW_PRESETS["map_location"].max_width_px == 140
    assert WINDOW_PRESETS["zukan"].max_width_px == 80


def test_granular_constraints_start_json():
    from src.text_validator import get_constraints_for_entry

    # Game mode description: 7 lines, 118px (calibrated with symmetric padding)
    c77 = get_constraints_for_entry("start.json", 77)
    assert c77.name == "start_mode_desc"
    assert c77.max_lines == 7
    assert c77.max_width_px == 118
    assert c77.reflow is True

    # Settings explanation: 4 lines, 145px
    c82 = get_constraints_for_entry("start.json", 82)
    assert c82.name == "start_setting_desc"
    assert c82.max_lines == 4
    assert c82.max_width_px == 145
    assert c82.reflow is True

    # Title buttons: 1 line, 100px
    c0 = get_constraints_for_entry("start.json", 0)
    assert c0.name == "start_title_button"
    assert c0.max_lines == 1
    assert c0.max_width_px == 100
    assert c0.reflow is False

    # Settings button: 1 line, 110px
    c74 = get_constraints_for_entry("start.json", 74)
    assert c74.name == "start_setting_button"
    assert c74.max_lines == 1
    assert c74.max_width_px == 110
    assert c74.reflow is False

    # Bottom hint bar: 1 line, 224px
    c91 = get_constraints_for_entry("start.json", 91)
    assert c91.name == "start_bottom_hint"
    assert c91.max_lines == 1
    assert c91.max_width_px == 224
    assert c91.reflow is False

    # Card/save corruption alert: 3 lines, 220px
    c29 = get_constraints_for_entry("start.json", 29)
    assert c29.name == "start_alert_box"
    assert c29.max_lines == 3
    assert c29.max_width_px == 220
    assert c29.reflow is True

    # General start entries fallback
    c50 = get_constraints_for_entry("start.json", 50)
    assert c50.name == "start_general"
    assert c50.max_lines == 2
    assert c50.max_width_px == 200
    assert c50.reflow is False



def test_granular_constraints_ex_item_json():
    from src.text_validator import get_constraints_for_entry

    # Regular item name in ex_item
    c0 = get_constraints_for_entry("ex_item.json", 0)
    assert c0.name == "item_name"
    assert c0.max_width_px == 105
    assert c0.max_lines == 1
    assert c0.reflow is False

    # Extra mode treasure combo in ex_item
    c180 = get_constraints_for_entry("ex_item.json", 180)
    assert c180.name == "ex_item_treasure_choice"
    assert c180.max_width_px == 165
    assert c180.max_lines == 1
    assert c180.reflow is False


def test_granular_constraints_menu_json_buttons():
    from src.text_validator import get_constraints_for_entry

    # Action button expanded to 95px
    c102 = get_constraints_for_entry("menu.json", 102)
    assert c102.max_width_px == 95
    assert c102.name == "menu_action_button"

def test_granular_constraints_shop_ui():
    from src.text_validator import get_constraints_for_entry

    # Shop action button: Buy, Sell, Equip
    c_buy = get_constraints_for_entry("menu.json", 118)
    assert c_buy.name == "shop_action_button"
    assert c_buy.max_width_px == 70
    assert c_buy.max_lines == 1
    assert c_buy.reflow is False

    # Shop funds / price labels
    c_funds = get_constraints_for_entry("menu.json", 121)
    assert c_funds.name == "shop_funds_label"
    assert c_funds.max_width_px == 75
    assert c_funds.max_lines == 1

    # Shop empty notices
    c_empty = get_constraints_for_entry("menu.json", 125)
    assert c_empty.name == "shop_empty_notice"
    assert c_empty.max_width_px == 195
    assert c_empty.max_lines == 2
    assert c_empty.reflow is True

    # Shop stat labels (Attack, Defense, Difference)
    c_stat = get_constraints_for_entry("menu.json", 132)
    assert c_stat.name == "shop_stat_label"
    assert c_stat.max_width_px == 75
    assert c_stat.max_lines == 1


def test_granular_constraints_battle_json():
    from src.text_validator import get_constraints_for_entry

    # Battle command buttons: 80px, 1 line, reflow False
    c_atk = get_constraints_for_entry("battle.json", 0)
    assert c_atk.name == "battle_cmd_button"
    assert c_atk.max_width_px == 80
    assert c_atk.max_lines == 1
    assert c_atk.reflow is False

    # Status conditions: 75px, 1 line, reflow False
    c_psn = get_constraints_for_entry("battle.json", 8)
    assert c_psn.name == "battle_status_condition"
    assert c_psn.max_width_px == 75
    assert c_psn.max_lines == 1
    assert c_psn.reflow is False

    # Battle labels: 60px, 1 line, reflow False
    c_lbl = get_constraints_for_entry("battle.json", 24)
    assert c_lbl.name == "battle_label"
    assert c_lbl.max_width_px == 60
    assert c_lbl.max_lines == 1
    assert c_lbl.reflow is False

    # Battle outcome / level up results: 180px, 2 lines, reflow True
    c_res = get_constraints_for_entry("battle.json", 32)
    assert c_res.name == "battle_result_msg"
    assert c_res.max_width_px == 180
    assert c_res.max_lines == 2
    assert c_res.reflow is True


def test_system_json_charmap_exemption():
    from src.text_validator import get_constraints_for_entry

    # Naming keyboard character table entries exempt from width
    c_big = get_constraints_for_entry("msg/big/system.json", 3)
    assert c_big.name == "system_charmap"
    assert c_big.max_width_px >= 9999
    assert c_big.font_type == "big"

    c_small = get_constraints_for_entry("msg/small/system.json", 6)
    assert c_small.name == "system_charmap"
    assert c_small.max_width_px >= 9999
    assert c_small.font_type == "small"

    # Small system popup test (entries 9..11)
    c_popup = get_constraints_for_entry("msg/small/system.json", 10)
    assert c_popup.name == "small_system_popup"
    assert c_popup.max_width_px == 130
    assert c_popup.max_lines == 2
    assert c_popup.font_type == "small"


def test_field_choice_box_preset_and_constraints():
    """Verify field_choice_box preset parameters and choice tag detection."""
    from src.text_validator import WINDOW_PRESETS, get_constraints_for_entry

    assert "field_choice_box" in WINDOW_PRESETS
    preset = WINDOW_PRESETS["field_choice_box"]
    assert preset.max_width_px == 110
    assert preset.max_lines == 4
    assert preset.reflow is False
    assert preset.font_type == "big"


def test_cmes0_dialogue_page_separation_wait_key():
    """Verify that multi-page dialogues with {WAIT_KEY} split pages correctly without false line overflows."""
    from src.text_validator import wrap_text_block, load_glyph_metrics

    widths = load_glyph_metrics("extracted fonts/msg/big/msgcmn.json", "assets/fonts/cyrillic_big.json")

    # 2-page dialogue separated by {WAIT_KEY} with 3 lines on each page
    text = (
        "Мама: Ты, наверное, так ждал\n"
        "Ярмарку Тысячелетия, что не мог\n"
        "уснуть прошлой ночью, верно?{WAIT_KEY}\n"
        "Ну, смотри, чтобы это легкомыслие\n"
        "не довело тебя до беды!\n"
        "Веди себя сегодня прилично!"
    )
    formatted, warnings = wrap_text_block(text, widths, max_width_px=238, max_lines=3, reflow=True)
    assert warnings == []
    assert "{WAIT_KEY}" in formatted


def test_all_extracted_text_zero_false_warnings():
    """Verify that validating all clean extracted text files produces 0 false warnings for original_en and original_fr."""
    import glob

    big_metrics = load_glyph_metrics("extracted fonts/msg/big/msgcmn.json")
    small_metrics = load_glyph_metrics("extracted fonts/msg/small/msgcmn.json")

    json_files = sorted(glob.glob("extracted text/**/*.json", recursive=True))
    assert len(json_files) >= 70, f"Expected at least 70 text files, found {len(json_files)}"

    all_warnings = []
    for fpath in json_files:
        if "debug_evt.json" in os.path.basename(fpath).lower():
            continue

        for field in ["original_en", "original_fr"]:
            rep = validate_and_format_file(
                fpath,
                font_widths=big_metrics,
                small_widths=small_metrics,
                preset="auto",
                field=field,
                dry_run=True,
            )
            for w in rep.get("warnings", []):
                # Skip start.json entries 77 & 78 on original text: Square Enix original text
                # did not enforce symmetric right padding (lines reached 126px right against the border).
                # The translation uses calibrated symmetric padding (118px).
                if os.path.basename(fpath).lower() == "start.json" and any(
                    f"Entry {eid}:" in w for eid in (77, 78)
                ):
                    continue
                all_warnings.append(f"{os.path.basename(fpath)} [{field}]: {w}")

    assert len(all_warnings) == 0, (
        f"Expected 0 warnings across all original text files, got {len(all_warnings)}:\n"
        + "\n".join(all_warnings[:30])
    )


def test_extras_ui_geometry_and_constraints():
    """Verify calibrated Extras & Media UI presets, constraints and ex_ending formatting."""
    # ex_ending.json
    p_desc = get_constraints_for_entry("ex_ending.json", 0)
    assert p_desc.name == "ending_desc"
    assert p_desc.max_width_px == 224
    assert p_desc.max_lines == 2
    assert p_desc.reflow is True

    p_title = get_constraints_for_entry("ex_ending.json", 26)
    assert p_title.name == "ending_title"
    assert p_title.max_width_px == 180
    assert p_title.max_lines == 1
    assert p_title.reflow is False

    # player.json
    p_pname = get_constraints_for_entry("player.json", 0)
    assert p_pname.name == "player_char_name"
    assert p_pname.max_width_px == 100
    assert p_pname.max_lines == 1
    assert p_pname.reflow is False

    p_prof = get_constraints_for_entry("player.json", 10)
    assert p_prof.name == "player_char_profile"
    assert p_prof.max_width_px == 132
    assert p_prof.max_lines == 6
    assert p_prof.reflow is True

    # bgm.json
    p_bgm = get_constraints_for_entry("bgm.json", 0)
    assert p_bgm.name == "bgm_name"
    assert p_bgm.max_width_px == 145
    assert p_bgm.max_lines == 1

    # Validate ex_ending.json with actual translation file
    big_metrics = load_glyph_metrics(
        "extracted fonts/msg/big/msgcmn.json",
        "assets/fonts/cyrillic_big.json",
    )
    rep = validate_and_format_file(
        "translated text/msg/big/ex_ending.json",
        font_widths=big_metrics,
        small_widths=None,
        preset="auto",
        field="translation",
        dry_run=True,
    )
    assert rep["total_entries"] == 39
    assert rep["overflows_found"] == 0
    assert len(rep["warnings"]) == 0









