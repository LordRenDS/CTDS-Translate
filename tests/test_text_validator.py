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
    validate_and_format_file,
    validate_and_format_directory,
    HERO_TOKENS,
    TextWindowPreset,
    WINDOW_PRESETS,
    get_preset_for_file,
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
    assert p_tut.max_width_px == 230
    assert p_tut.reflow is True
    assert p_tut.font_type == "big"
    assert get_preset_for_file("start.json").name == "tutorial"
    assert get_preset_for_file("ev_title.json").name == "tutorial"

    # 3. Encyclopedia / Character bio files
    p_encyclopedia = get_preset_for_file("player.json")
    assert p_encyclopedia.name == "encyclopedia"
    assert p_encyclopedia.max_lines == 6
    assert p_encyclopedia.max_width_px == 215
    assert get_preset_for_file("ex_montec.json").name == "encyclopedia"
    assert get_preset_for_file("ex_itemget.json").name == "encyclopedia"
    assert get_preset_for_file("ex_illust.json").name == "encyclopedia"
    assert get_preset_for_file("ex_ending.json").name == "encyclopedia"

    # 4. Item descriptions
    p_item_desc = get_preset_for_file("item_mes.json")
    assert p_item_desc.name == "item_desc"
    assert p_item_desc.max_lines == 2
    assert p_item_desc.max_width_px == 195
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
    assert p_battle.max_width_px == 210
    assert p_battle.reflow is True

    # 8. Menu screens
    p_menu = get_preset_for_file("menu.json")
    assert p_menu.name == "menu"
    assert p_menu.max_lines == 2
    assert p_menu.max_width_px == 200
    assert p_menu.reflow is False
    assert get_preset_for_file("wireless0.json").name == "menu"
    assert get_preset_for_file("ques0.json").name == "menu"

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


