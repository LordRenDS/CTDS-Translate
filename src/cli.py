"""Command-line interface (CLI) for Chrono Trigger DS translation toolset."""

import argparse
import os
import sys
import tempfile
from typing import List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.font_engine import (
    build_all_fonts,
    dump_all_fonts,
    inject_cyrillic_into_fnt,
)
from src.graphics_engine import (
    build_all_screens,
    build_screen,
    dump_all_screens,
    dump_screen,
    dump_ncgr_sprite,
    build_ncgr_sprite,
    rebuild_ncer_from_metadata,
    find_cell_bank_for_sprite,
    find_palette_for_screen,
    find_palette_for_sprite,
    find_tiles_for_screen,
)
from src.rom_manager import build_rom, unpack_rom, verify_rom_integrity
from src.text_engine import dump_all_msg, insert_all_msg
from src.text_validator import (
    load_glyph_metrics,
    validate_and_format_directory,
    validate_and_format_file,
    WINDOW_PRESETS,
)


def cmd_unpack(args: argparse.Namespace) -> int:
    """Handles the 'unpack' subcommand."""
    if not os.path.isfile(args.nds):
        print(f"Error: ROM file not found: {args.nds}")
        return 1

    print(f"Unpacking ROM: {args.nds} -> {args.out}")
    info = unpack_rom(args.nds, args.out)
    print(
        f"Successfully unpacked '{info['name']}' (ID: {info['id_code']}) with {info['file_count']} files."
    )
    return 0


def cmd_dump_text(args: argparse.Namespace) -> int:
    """Handles the 'dump-text' subcommand."""
    if not os.path.isdir(args.rom_data):
        print(f"Error: NitroFS data directory not found: {args.rom_data}")
        return 1

    print(f"Dumping text from '{args.rom_data}' -> '{args.out}'...")
    count = dump_all_msg(args.rom_data, args.out)
    print(f"Successfully dumped {count} .msg files to JSON.")
    return 0


def cmd_insert_text(args: argparse.Namespace) -> int:
    """Handles the 'insert-text' subcommand."""
    if not os.path.isdir(args.json_dir):
        print(f"Error: JSON directory not found: {args.json_dir}")
        return 1
    if not os.path.isdir(args.rom_data):
        print(f"Error: NitroFS data directory not found: {args.rom_data}")
        return 1

    print(f"Inserting text from '{args.json_dir}' -> '{args.rom_data}'...")
    count = insert_all_msg(args.json_dir, args.rom_data)
    print(f"Successfully compiled and inserted {count} .msg files.")
    return 0


def cmd_dump_font(args: argparse.Namespace) -> int:
    """Handles the 'dump-font' subcommand."""
    if not os.path.isdir(args.rom_data):
        print(f"Error: NitroFS data directory not found: {args.rom_data}")
        return 1

    grid_mode = getattr(args, "grid", "both")
    print(f"Dumping fonts from '{args.rom_data}' -> '{args.out}' (grid: {grid_mode})...")
    count = dump_all_fonts(args.rom_data, args.out, grid_mode=grid_mode)
    print(f"Successfully dumped {count} font files to PNG + JSON.")
    return 0


def cmd_build_font(args: argparse.Namespace) -> int:
    """Handles the 'build-font' subcommand."""
    if not os.path.isdir(args.font_dir):
        print(f"Error: Font directory not found: {args.font_dir}")
        return 1
    if not os.path.isdir(args.rom_data):
        print(f"Error: NitroFS data directory not found: {args.rom_data}")
        return 1

    print(f"Building fonts from '{args.font_dir}' -> '{args.rom_data}'...")
    count = build_all_fonts(args.font_dir, args.rom_data)
    print(f"Successfully rebuilt {count} font files.")
    return 0


def cmd_inject_cyrillic_font(args: argparse.Namespace) -> int:
    """Handles the 'inject-cyrillic-font' subcommand."""
    if not os.path.isdir(args.rom_data):
        print(f"Error: NitroFS data directory not found: {args.rom_data}")
        return 1

    print(f"Injecting Cyrillic glyphs into font files in '{args.rom_data}'...")
    count = 0
    for root, _, files in os.walk(args.rom_data):
        for file in files:
            if file.lower().endswith(".fnt"):
                fnt_path = os.path.join(root, file)
                with open(fnt_path, "rb") as f:
                    fnt_bytes = f.read()

                extended_fnt = inject_cyrillic_into_fnt(
                    fnt_bytes,
                    ttf_font_path=args.font,
                    assets_dir=getattr(args, "assets_dir", None),
                )

                with open(fnt_path, "wb") as f:
                    f.write(extended_fnt)
                count += 1
                rel = os.path.relpath(fnt_path, args.rom_data)
                print(f"  Injected Cyrillic into: {rel}")

    print(f"Successfully injected Cyrillic glyphs into {count} font files.")
    return 0


def cmd_build_rom(args: argparse.Namespace) -> int:
    """Handles the 'build-rom' subcommand."""
    if not os.path.isdir(args.extracted):
        print(f"Error: Extracted directory not found: {args.extracted}")
        return 1

    print(f"Building ROM: '{args.extracted}' -> '{args.out}' (Base: {args.base})...")
    build_rom(
        extracted_dir=args.extracted,
        output_nds_path=args.out,
        base_nds_path=args.base if args.base and os.path.isfile(args.base) else None,
    )
    print(f"Successfully built ROM: {args.out}")
    return 0


def cmd_roundtrip(args: argparse.Namespace) -> int:
    """Handles the 'roundtrip' subcommand for automated full pipeline verification."""
    if not os.path.isfile(args.nds):
        print(f"Error: Source ROM not found: {args.nds}")
        return 1

    print(f"=== Starting Full Roundtrip Verification on '{args.nds}' ===")

    temp_dir_obj = None
    if args.temp_dir:
        working_dir = args.temp_dir
        os.makedirs(working_dir, exist_ok=True)
    else:
        temp_dir_obj = tempfile.TemporaryDirectory()
        working_dir = temp_dir_obj.name

    try:
        extracted_dir = os.path.join(working_dir, "extracted")
        extracted_data_dir = os.path.join(extracted_dir, "data")
        text_dir = os.path.join(working_dir, "text")
        fonts_dir = os.path.join(working_dir, "fonts")
        rebuilt_rom_path = os.path.join(working_dir, "rebuilt.nds")

        # Step 1: Unpack ROM
        print("[1/6] Unpacking original ROM...")
        unpack_info = unpack_rom(args.nds, extracted_dir)
        print(f"      Unpacked {unpack_info['file_count']} files.")

        # Step 2: Dump all text to JSON
        print("[2/6] Dumping all .msg text files to JSON...")
        msg_count = dump_all_msg(extracted_data_dir, text_dir)
        print(f"      Dumped {msg_count} .msg files.")

        # Step 3: Dump all fonts to PNG + JSON
        print("[3/6] Dumping all font files to PNG + JSON...")
        fnt_count = dump_all_fonts(extracted_data_dir, fonts_dir)
        print(f"      Dumped {fnt_count} .fnt files.")

        # Step 4: Rebuild all fonts from PNG + JSON back to data directory
        print("[4/6] Rebuilding all fonts from PNG + JSON...")
        rebuilt_fnt_count = build_all_fonts(fonts_dir, extracted_data_dir)
        print(f"      Rebuilt {rebuilt_fnt_count} .fnt files.")

        # Step 5: Insert all text from JSON back to data directory
        print("[5/6] Rebuilding and inserting all text files from JSON...")
        inserted_msg_count = insert_all_msg(text_dir, extracted_data_dir)
        print(f"      Inserted {inserted_msg_count} .msg files.")

        # Step 6: Build rebuilt ROM
        print("[6/6] Building rebuilt ROM image...")
        build_rom(
            extracted_dir=extracted_dir,
            output_nds_path=rebuilt_rom_path,
            base_nds_path=args.nds,
        )

        # Verification
        print("=== Verifying ROM Structure & Integrity ===")
        is_valid = verify_rom_integrity(args.nds, rebuilt_rom_path)

        if is_valid:
            print("SUCCESS: Roundtrip verification completed with 100% integrity!")
            return 0
        else:
            print("FAILURE: Rebuilt ROM failed integrity verification against original ROM.")
            return 1
    finally:
        if temp_dir_obj is not None:
            temp_dir_obj.cleanup()


def cmd_validate_text_length(args: argparse.Namespace) -> int:
    """Handles the 'validate-text-length' (and alias 'validate-text-lenght') subcommand."""
    if getattr(args, "file", None):
        if not os.path.isfile(args.file):
            print(f"Error: JSON file not found: {args.file}")
            return 1

        widths = load_glyph_metrics(args.font_json, args.cyrillic_json)
        mode_str = "[FIX & FORMAT]" if args.fix else "[DRY-RUN CHECK]"
        preset_name = getattr(args, "preset", "auto")
        print(f"=== Text Length & Dialogue Validation {mode_str} ===")
        print(f"File: {args.file}")
        print(f"  Window preset          : {preset_name}")
        print(
            f"Max width: {args.max_width or 'auto (preset)'}, Max lines: {args.max_lines or 'auto (preset)'}"
        )
        print(
            f"  Reflow existing breaks : {'Enabled' if args.reflow is None or args.reflow else 'Disabled'}"
        )

        report = validate_and_format_file(
            file_path=args.file,
            glyph_widths=widths,
            max_width_px=args.max_width,
            max_lines=args.max_lines,
            auto_paginate=args.paginate,
            field=args.field,
            fix=args.fix,
            out_path=args.out,
            preset=args.preset,
            reflow=args.reflow,
        )

        print(f"Preset applied: {report['preset']}")
        print(f"Total entries checked: {report['total_entries']}")
        print(f"Overlong lines detected: {report['overflows_found']}")
        print(f"Warnings: {len(report['warnings'])}")
        print(f"File modified: {report['modified']}")

        if report["overflows_found"] > 0 or report["warnings"]:
            print("\nDetail lines with issues:")
            for w in report["warnings"]:
                print(f"  - {w}")

        if not args.fix and (report["overflows_found"] > 0 or report["warnings"]):
            return 1

        return 0

    if not os.path.isdir(args.json_dir):
        print(f"Error: JSON directory not found: {args.json_dir}")
        return 1

    mode_str = "[FIX & FORMAT]" if args.fix else "[DRY-RUN CHECK]"
    preset_name = getattr(args, "preset", "auto")
    print(f"=== Text Length & Dialogue Validation {mode_str} ===")
    print(f"Directory: {args.json_dir}")
    print(f"  Window preset          : {preset_name}")
    width_info = f"{args.max_width} px" if args.max_width is not None else "auto (preset)"
    lines_info = f"{args.max_lines}" if args.max_lines is not None else "auto (preset)"
    print(f"Max width: {width_info}, Max lines: {lines_info}")
    print(
        f"  Reflow existing breaks : {'Disabled' if getattr(args, 'reflow', None) is False else 'Enabled'}"
    )

    report = validate_and_format_directory(
        json_dir=args.json_dir,
        font_json_path=args.font_json,
        cyrillic_json_path=args.cyrillic_json,
        max_width_px=args.max_width,
        max_lines=args.max_lines,
        auto_paginate=args.paginate,
        reflow=getattr(args, "reflow", None),
        field=args.field,
        fix=args.fix,
        out_dir=args.out,
        preset=preset_name,
    )

    print(f"Files inspected: {report['files_checked']}")
    print(f"Total entries checked: {report['total_entries']}")
    print(f"Overlong lines detected: {report['total_overflows']}")
    print(f"Warnings: {report['total_warnings']}")
    print(f"Files modified: {report['files_modified']}")

    if report["total_overflows"] > 0 or report["total_warnings"] > 0:
        print("\nDetail lines for files with issues:")
        for fr in report["file_reports"]:
            if fr["overflows_found"] > 0 or fr["warnings"]:
                print(
                    f"  {fr['file_path']} (Preset: {fr.get('preset', 'dialogue')}, Overflows: {fr['overflows_found']}, Warnings: {len(fr['warnings'])})"
                )
                for w in fr["warnings"]:
                    print(f"    - {w}")

    if not args.fix and (report["total_overflows"] > 0 or report["total_warnings"] > 0):
        return 1

    return 0


def cmd_dump_graphics(args: argparse.Namespace) -> int:
    """Handles the 'dump-graphics' subcommand."""
    if args.screen:
        screen_arg = args.screen
        normalized = screen_arg.replace("\\", "/")

        # Check if screen_arg points to an NCGR sprite file
        ncgr_cand = screen_arg if screen_arg.upper().endswith(".NCGR") else normalized + ".NCGR"
        if os.path.isfile(ncgr_cand):
            rom_data = args.rom_data.replace("\\", "/")
            if ncgr_cand.replace("\\", "/").startswith(rom_data):
                rel = os.path.relpath(ncgr_cand, rom_data)
            else:
                rel = os.path.basename(ncgr_cand)
            rel_stem = os.path.splitext(rel)[0]
            out_png = os.path.join(args.out, rel_stem + ".png")
            out_json = os.path.join(args.out, rel_stem + ".json")

            if getattr(args, "palette", None) and os.path.isfile(args.palette):
                nclr_path = args.palette
            else:
                nclr_path = find_palette_for_sprite(ncgr_cand)

            if getattr(args, "ncer", None) and os.path.isfile(args.ncer):
                ncer_path = args.ncer
            else:
                ncer_path = find_cell_bank_for_sprite(ncgr_cand)

            print(f"Dumping sprite '{ncgr_cand}' -> '{out_png}'...")
            info = dump_ncgr_sprite(ncgr_cand, nclr_path, out_png, out_json, ncer_path=ncer_path)
            print(f"Successfully dumped sprite ({info['num_tiles']} tiles).")
            return 0

        for suffix in ("_nsc.bin", "_ncg.bin", "_ncl.bin", ".bin", ".png", ".json"):
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)]
                break

        nsc_path = normalized + "_nsc.bin"
        if not os.path.isfile(nsc_path):
            print(f"Error: Screen or sprite file not found: {screen_arg}")
            return 1

        ncg_path = find_tiles_for_screen(nsc_path)
        ncl_path = find_palette_for_screen(nsc_path)

        if not ncg_path or not os.path.isfile(ncg_path):
            print(f"Error: Matching NCG tiles not found for: {nsc_path}")
            return 1
        if not ncl_path or not os.path.isfile(ncl_path):
            print(f"Error: Matching NCL palette not found for: {nsc_path}")
            return 1

        rom_data = args.rom_data.replace("\\", "/")
        if normalized.startswith(rom_data):
            rel = os.path.relpath(normalized, rom_data)
        else:
            rel = os.path.basename(normalized)

        out_png = os.path.join(args.out, rel + ".png")
        out_json = os.path.join(args.out, rel + ".json")

        print(f"Dumping screen '{normalized}' -> '{out_png}'...")
        info = dump_screen(ncg_path, ncl_path, nsc_path, out_png, out_json)
        print(
            f"Successfully dumped screen ({info['width_px']}x{info['height_px']} px, {info['tile_count']} tiles)."
        )
        return 0

    if not os.path.isdir(args.rom_data):
        print(f"Error: NitroFS data directory not found: {args.rom_data}")
        return 1

    target_dir = getattr(args, "directory", None) or getattr(args, "category", None)
    dir_str = (
        f" [dir: {target_dir}]"
        if target_dir
        else (" [ALL]" if args.all else " [default categories]")
    )
    print(f"Dumping graphics from '{args.rom_data}' -> '{args.out}'{dir_str}...")
    result = dump_all_screens(
        rom_data_dir=args.rom_data,
        output_image_dir=args.out,
        category=getattr(args, "category", None),
        dump_all=args.all,
        directory=getattr(args, "directory", None),
    )
    print(
        f"Successfully dumped {int(result)} graphics "
        f"({result.screens} screens, {result.slides} slides, {result.sprites} sprites) to PNG + JSON."
    )
    return 0


def cmd_build_graphics(args: argparse.Namespace) -> int:
    """Handles the 'build-graphics' (and alias 'insert-graphics') subcommand."""
    if args.screen:
        screen_path = args.screen
        if not os.path.isfile(screen_path):
            print(f"Error: Image file not found: {screen_path}")
            return 1

        meta_json_path = None
        if screen_path.endswith(".png"):
            cand_json = screen_path[:-4] + ".json"
            if os.path.isfile(cand_json):
                meta_json_path = cand_json

        if not meta_json_path:
            for base_dir in (args.image_dir, args.meta_dir):
                norm_base = base_dir.replace("\\", "/")
                norm_scr = screen_path.replace("\\", "/")
                if norm_scr.startswith(norm_base):
                    rel = os.path.relpath(norm_scr, norm_base)
                    rel_stem = os.path.splitext(rel)[0]
                    cand = os.path.join(args.meta_dir, rel_stem + ".json")
                    if os.path.isfile(cand):
                        meta_json_path = cand
                        break

        if not meta_json_path or not os.path.isfile(meta_json_path):
            base_stem = os.path.splitext(os.path.basename(screen_path))[0]
            cand = os.path.join(args.meta_dir, base_stem + ".json")
            if os.path.isfile(cand):
                meta_json_path = cand
            else:
                print(f"Error: Metadata JSON not found for: {screen_path}")
                return 1

        rel_stem = None
        for base_dir in (args.image_dir, args.meta_dir):
            norm_base = base_dir.replace("\\", "/")
            norm_scr = screen_path.replace("\\", "/")
            if norm_scr.startswith(norm_base):
                rel = os.path.relpath(norm_scr, norm_base)
                rel_stem = os.path.splitext(rel)[0]
                break

        if not rel_stem:
            rel_stem = os.path.splitext(os.path.basename(screen_path))[0]

        import json

        with open(meta_json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        if meta.get("format") == "NCGR":
            out_ncgr = os.path.join(args.rom_data, rel_stem + ".NCGR")
            print(f"Building sprite '{screen_path}' -> '{out_ncgr}'...")
            info = build_ncgr_sprite(screen_path, meta_json_path, out_ncgr)
            print(f"Successfully rebuilt sprite ({info['num_tiles']} tiles).")
            if meta.get("is_cell_sheet") and meta.get("ncer_path"):
                out_ncer = os.path.join(args.rom_data, rel_stem + ".NCER")
                rebuild_ncer_from_metadata(meta_json_path, out_ncer)
                print(f"Successfully rebuilt cell bank '{out_ncer}'.")
            return 0

        out_ncg = os.path.join(args.rom_data, rel_stem + "_ncg.bin")
        out_ncl = os.path.join(args.rom_data, rel_stem + "_ncl.bin")
        out_nsc = os.path.join(args.rom_data, rel_stem + "_nsc.bin")

        print(f"Building screen '{screen_path}' -> '{args.rom_data}'...")
        info = build_screen(screen_path, meta_json_path, out_ncg, out_ncl, out_nsc)
        print(f"Successfully rebuilt screen ({info['unique_tiles']} unique tiles).")
        return 0

    if not os.path.isdir(args.image_dir):
        print(f"Error: Image directory not found: {args.image_dir}")
        return 1

    dir_str = f" [dir: {args.directory}]" if getattr(args, "directory", None) else ""
    print(f"Building graphics from '{args.image_dir}' -> '{args.rom_data}'{dir_str}...")
    count = build_all_screens(
        image_dir=args.image_dir,
        meta_dir=args.meta_dir,
        target_rom_data_dir=args.rom_data,
        sub_dir=getattr(args, "directory", None),
    )
    print(f"Successfully rebuilt and inserted {count} screens/sprites.")
    return 0


def create_parser() -> argparse.ArgumentParser:
    """Constructs and returns the top-level argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="ctds",
        description="Chrono Trigger DS Translation & Reverse Engineering Toolset",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # unpack
    p_unpack = subparsers.add_parser(
        "unpack", help="Unpack clean NDS ROM into filesystem components"
    )
    p_unpack.add_argument(
        "--nds",
        default="rom/Chrono Trigger (Europe) (En,Fr).nds",
        help="Path to clean input .nds ROM (default: 'rom/Chrono Trigger (Europe) (En,Fr).nds')",
    )
    p_unpack.add_argument(
        "--out",
        default="extracted rom",
        help="Output directory for extracted ROM components (default: 'extracted rom')",
    )

    # dump-text
    p_dump_text = subparsers.add_parser(
        "dump-text", help="Dump all .msg dialogue and system text files to JSON"
    )
    p_dump_text.add_argument(
        "--rom-data",
        default="extracted rom/data",
        help="Path to extracted NitroFS data directory (default: 'extracted rom/data')",
    )
    p_dump_text.add_argument(
        "--out",
        default="extracted text",
        help="Destination directory for dumped JSON text files (default: 'extracted text')",
    )

    # insert-text
    p_insert_text = subparsers.add_parser(
        "insert-text", help="Compile and insert JSON translation files into ROM data"
    )
    p_insert_text.add_argument(
        "--json-dir",
        default="translated text",
        help="Directory containing translated JSON files (default: 'translated text')",
    )
    p_insert_text.add_argument(
        "--rom-data",
        default="extracted rom/data",
        help="Path to extracted NitroFS data directory (default: 'extracted rom/data')",
    )

    # dump-font
    p_dump_font = subparsers.add_parser(
        "dump-font", help="Dump proprietary .fnt fonts to editable PNG glyph sheets and JSON"
    )
    p_dump_font.add_argument(
        "--rom-data",
        default="extracted rom/data",
        help="Path to extracted NitroFS data directory (default: 'extracted rom/data')",
    )
    p_dump_font.add_argument(
        "--out",
        default="extracted fonts",
        help="Destination directory for dumped PNG and JSON font assets (default: 'extracted fonts')",
    )
    p_dump_font.add_argument(
        "--grid",
        choices=["both", "cells", "none"],
        default="both",
        help="Visual grid overlay mode: 'both' (cell boundary + glyph width, default), 'cells' (cell boundary only), 'none' (raw background)",
    )

    # build-font
    p_build_font = subparsers.add_parser(
        "build-font", help="Rebuild .fnt binary font files from PNG glyph sheets and JSON"
    )
    p_build_font.add_argument(
        "--font-dir",
        default="extracted fonts",
        help="Directory containing PNG and JSON font sheets (default: 'extracted fonts')",
    )
    p_build_font.add_argument(
        "--rom-data",
        default="extracted rom/data",
        help="Path to extracted NitroFS data directory (default: 'extracted rom/data')",
    )

    # inject-cyrillic-font
    p_inject_cyrillic = subparsers.add_parser(
        "inject-cyrillic-font",
        help="Inject 66 Cyrillic glyphs (А..Я, а..я, Ё, ё) into font files in ROM data",
    )
    p_inject_cyrillic.add_argument(
        "--rom-data",
        default="extracted rom/data",
        help="Path to extracted NitroFS data directory (default: 'extracted rom/data')",
    )
    p_inject_cyrillic.add_argument(
        "--font",
        default=None,
        help="Optional path to TTF font file for Cyrillic glyph rasterization override",
    )
    p_inject_cyrillic.add_argument(
        "--assets-dir",
        default=None,
        help="Optional path to Cyrillic font pixel assets directory (defaults to 'assets/fonts')",
    )

    # build-rom
    p_build_rom = subparsers.add_parser(
        "build-rom", help="Build and align rebuilt .nds ROM image from extracted directory"
    )
    p_build_rom.add_argument(
        "--extracted",
        default="extracted rom",
        help="Path to directory containing extracted ROM assets (default: 'extracted rom')",
    )
    p_build_rom.add_argument(
        "--out",
        default="rom/Chrono Trigger (Russian).nds",
        help="Path for rebuilt output .nds ROM file (default: 'rom/Chrono Trigger (Russian).nds')",
    )
    p_build_rom.add_argument(
        "--base",
        default="rom/Chrono Trigger (Europe) (En,Fr).nds",
        help="Base .nds ROM to preserve original header/timings (default: 'rom/Chrono Trigger (Europe) (En,Fr).nds')",
    )

    # roundtrip
    p_roundtrip = subparsers.add_parser(
        "roundtrip",
        help="Execute full roundtrip pipeline verification on clean ROM (unpack -> dump -> rebuild -> verify)",
    )
    p_roundtrip.add_argument(
        "--nds",
        default="rom/Chrono Trigger (Europe) (En,Fr).nds",
        help="Path to reference clean .nds ROM (default: 'rom/Chrono Trigger (Europe) (En,Fr).nds')",
    )
    p_roundtrip.add_argument(
        "--temp-dir",
        default=None,
        help="Optional custom temporary working directory for roundtrip assets",
    )

    # validate-text-length & validate-text-lenght
    for subcmd_name, subcmd_help in [
        (
            "validate-text-length",
            "Validate dialogue and UI text line pixel widths against font metrics",
        ),
        (
            "validate-text-lenght",
            "Alias for validate-text-length",
        ),
    ]:
        p_val = subparsers.add_parser(subcmd_name, help=subcmd_help)
        p_val.add_argument(
            "--file",
            "--json-file",
            dest="file",
            default=None,
            help="Path to a single JSON translation file to validate (overrides --json-dir)",
        )
        p_val.add_argument(
            "--json-dir",
            default="translated text",
            help="Directory containing translation JSON files (default: 'translated text')",
        )
        p_val.add_argument(
            "--preset",
            choices=["auto"] + list(WINDOW_PRESETS.keys()),
            default="auto",
            help="Dialogue/window preset to apply (default: 'auto' based on file pattern)",
        )
        p_val.add_argument(
            "--fix",
            action="store_true",
            help="Apply fixes and write wrapped text back to JSON files",
        )
        p_val.add_argument(
            "--out",
            default=None,
            help="Optional output directory to save fixed files without overwriting source",
        )
        p_val.add_argument(
            "--max-width",
            type=int,
            default=None,
            help="Maximum allowed line pixel width (overrides preset default if set)",
        )
        p_val.add_argument(
            "--max-lines",
            type=int,
            default=None,
            help="Maximum lines per dialogue box page (overrides preset default if set)",
        )
        p_val.add_argument(
            "--paginate",
            action="store_true",
            help="Automatically split pages with {PAGE} if lines exceed max-lines",
        )
        p_val.add_argument(
            "--no-reflow",
            dest="reflow",
            action="store_false",
            default=None,
            help="Do not collapse existing line breaks within pages before wrapping (default: uses preset setting)",
        )
        p_val.add_argument(
            "--font-json",
            default="extracted fonts/msg/big/msgcmn.json",
            help="Path to base font metrics JSON (default: 'extracted fonts/msg/big/msgcmn.json')",
        )
        p_val.add_argument(
            "--cyrillic-json",
            default="assets/fonts/cyrillic_big.json",
            help="Path to Cyrillic font metrics JSON (default: 'assets/fonts/cyrillic_big.json')",
        )
        p_val.add_argument(
            "--field",
            default="translation",
            help="JSON field to validate (default: 'translation')",
        )

    # dump-graphics
    p_dump_gfx = subparsers.add_parser(
        "dump-graphics",
        help="Dump background screen graphics to PNG and JSON descriptors",
    )
    p_dump_gfx.add_argument(
        "--rom-data",
        default="extracted rom/data",
        help="Path to extracted NitroFS data directory (default: 'extracted rom/data')",
    )
    p_dump_gfx.add_argument(
        "--out",
        default="extracted image",
        help="Destination directory for dumped PNG images (default: 'extracted image')",
    )
    p_dump_gfx.add_argument(
        "--screen",
        default=None,
        help="Optional path or stem of a specific screen to dump (e.g. 'extracted rom/data/title/bg/kenri')",
    )
    p_dump_gfx.add_argument(
        "--palette",
        "--nclr",
        default=None,
        help="Optional path to an explicit NCLR or NCL palette file to use for dumping",
    )
    p_dump_gfx.add_argument(
        "--ncer",
        default=None,
        help="Optional path to an explicit NCER cell bank file to use for dumping",
    )
    p_dump_gfx.add_argument(
        "--dir",
        "--directory",
        dest="directory",
        default=None,
        help="Optional directory or subdirectory within rom-data to dump (e.g. 'menu', 'menu/obj', 'title/bg', 'Ending')",
    )
    p_dump_gfx.add_argument(
        "--category",
        default=None,
        help=argparse.SUPPRESS,  # Deprecated alias for --dir
    )
    p_dump_gfx.add_argument(
        "--all",
        action="store_true",
        help="Dump all graphics (screens, slides, sprites) across all directories in the ROM",
    )

    # build-graphics & insert-graphics
    for subcmd_gfx, help_gfx in [
        (
            "build-graphics",
            "Rebuild background screen binaries from PNG and JSON descriptors",
        ),
        (
            "insert-graphics",
            "Alias for build-graphics",
        ),
    ]:
        p_build_gfx = subparsers.add_parser(subcmd_gfx, help=help_gfx)
        p_build_gfx.add_argument(
            "--image-dir",
            default="translated image",
            help="Directory containing translated PNG files (default: 'translated image')",
        )
        p_build_gfx.add_argument(
            "--meta-dir",
            default="extracted image",
            help="Directory containing original metadata JSON files (default: 'extracted image')",
        )
        p_build_gfx.add_argument(
            "--rom-data",
            default="extracted rom/data",
            help="Path to extracted NitroFS data directory (default: 'extracted rom/data')",
        )
        p_build_gfx.add_argument(
            "--screen",
            default=None,
            help="Optional path to a specific PNG file to rebuild",
        )
        p_build_gfx.add_argument(
            "--dir",
            "--directory",
            dest="directory",
            default=None,
            help="Optional subdirectory within image-dir to rebuild (e.g. 'menu', 'menu/obj')",
        )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint.

    Args:
        argv: Optional list of argument strings. If None, sys.argv[1:] is used.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(errors="backslashreplace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(errors="backslashreplace")
        except Exception:
            pass

    parser = create_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if not args.command:
        parser.print_help()
        return 0

    command_handlers = {
        "unpack": cmd_unpack,
        "dump-text": cmd_dump_text,
        "insert-text": cmd_insert_text,
        "dump-font": cmd_dump_font,
        "build-font": cmd_build_font,
        "inject-cyrillic-font": cmd_inject_cyrillic_font,
        "build-rom": cmd_build_rom,
        "roundtrip": cmd_roundtrip,
        "validate-text-length": cmd_validate_text_length,
        "validate-text-lenght": cmd_validate_text_length,
        "dump-graphics": cmd_dump_graphics,
        "build-graphics": cmd_build_graphics,
        "insert-graphics": cmd_build_graphics,
    }

    handler = command_handlers.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
