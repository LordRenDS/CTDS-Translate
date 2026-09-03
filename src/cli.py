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
from src.rom_manager import build_rom, unpack_rom, verify_rom_integrity
from src.text_engine import dump_all_msg, insert_all_msg


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

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint.

    Args:
        argv: Optional list of argument strings. If None, sys.argv[1:] is used.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
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
    }

    handler = command_handlers.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
