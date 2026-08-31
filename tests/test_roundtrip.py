"""End-to-End Roundtrip and CLI Integration Tests for Chrono Trigger DS translation toolset."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import ndspy.rom
from src.cli import create_parser, main
from src.font_engine import dump_fnt_to_png_and_json
from src.text_engine import dump_msg

ORIGINAL_ROM = "rom/Chrono Trigger (Europe) (En,Fr).nds"


class TestCLIAndRoundtrip(unittest.TestCase):
    """Test suite for CLI subcommands and full end-to-end translation pipeline."""

    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(ORIGINAL_ROM):
            raise unittest.SkipTest(f"Original clean ROM not found at '{ORIGINAL_ROM}'")

    def test_cli_help_all_subcommands(self):
        """Verify that --help works without error for the main CLI and all subcommands."""
        parser = create_parser()
        self.assertIsNotNone(parser)

        # Test main parser help
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            with self.assertRaises(SystemExit) as cm:
                parser.parse_args(["--help"])
            self.assertEqual(cm.exception.code, 0)
            self.assertIn("Chrono Trigger DS Translation", fake_out.getvalue())

        # Test each subcommand's help
        subcommands = [
            "unpack",
            "dump-text",
            "insert-text",
            "dump-font",
            "build-font",
            "inject-cyrillic-font",
            "build-rom",
            "roundtrip",
        ]
        for subcmd in subcommands:
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                with self.assertRaises(SystemExit) as cm:
                    parser.parse_args([subcmd, "--help"])
                self.assertEqual(cm.exception.code, 0)
                self.assertIn(f"ctds {subcmd}", fake_out.getvalue())

    def test_cli_no_args_shows_help(self):
        """Verify that invoking main() with no arguments shows help and returns 0."""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            ret = main([])
            self.assertEqual(ret, 0)
            self.assertIn("Available commands", fake_out.getvalue())

    def test_full_pipeline_roundtrip_cli(self):
        """Verify that running the roundtrip CLI command executes cleanly and verifies integrity."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ret = main(["roundtrip", "--nds", ORIGINAL_ROM, "--temp-dir", temp_dir])
            self.assertEqual(ret, 0)

    def test_full_pipeline_roundtrip_subprocess(self):
        """Verify that running python -m src.cli roundtrip via subprocess succeeds with exit code 0."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cmd = [
                sys.executable,
                "-m",
                "src.cli",
                "roundtrip",
                "--nds",
                ORIGINAL_ROM,
                "--temp-dir",
                temp_dir,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(
                result.returncode,
                0,
                f"CLI roundtrip failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
            )
            self.assertIn("SUCCESS: Roundtrip verification completed", result.stdout)

    def test_e2e_translation_and_font_injection(self):
        """Verify full workflow: Unpack -> Translate dialogue -> Inject Cyrillic font -> Rebuild ROM -> Validate."""
        with tempfile.TemporaryDirectory() as temp_dir:
            extracted_dir = os.path.join(temp_dir, "extracted")
            extracted_data_dir = os.path.join(extracted_dir, "data")
            text_dump_dir = os.path.join(temp_dir, "text_dump")
            translated_dir = os.path.join(temp_dir, "translated")
            rebuilt_nds_path = os.path.join(temp_dir, "Chrono_Trigger_Russian.nds")

            # 1. Unpack ROM via CLI
            ret = main(["unpack", "--nds", ORIGINAL_ROM, "--out", extracted_dir])
            self.assertEqual(ret, 0)
            self.assertTrue(os.path.isdir(extracted_data_dir))
            self.assertTrue(os.path.isfile(os.path.join(extracted_dir, "arm9.bin")))

            # 2. Dump text via CLI
            ret = main(["dump-text", "--rom-data", extracted_data_dir, "--out", text_dump_dir])
            self.assertEqual(ret, 0)

            cmes0_json_path = os.path.join(text_dump_dir, "msg", "big", "cmes0.json")
            self.assertTrue(os.path.isfile(cmes0_json_path))

            # 3. Modify dialogue with Russian text and control codes
            with open(cmes0_json_path, "r", encoding="utf-8") as f:
                entries = json.load(f)

            self.assertGreater(len(entries), 0)
            russian_dialogue = "Проснись, {CRONO}!\n{WAIT_KEY}\nСолнце уже встало!"
            entries[0]["translation"] = russian_dialogue

            translated_cmes0_path = os.path.join(translated_dir, "msg", "big", "cmes0.json")
            os.makedirs(os.path.dirname(translated_cmes0_path), exist_ok=True)
            with open(translated_cmes0_path, "w", encoding="utf-8") as f:
                json.dump(entries, f, ensure_ascii=False, indent=2)

            # 4. Insert translated text via CLI
            ret = main(["insert-text", "--json-dir", translated_dir, "--rom-data", extracted_data_dir])
            self.assertEqual(ret, 0)

            # 5. Inject Cyrillic font via CLI
            ret = main(["inject-cyrillic-font", "--rom-data", extracted_data_dir])
            self.assertEqual(ret, 0)

            # 6. Build rebuilt ROM via CLI
            ret = main([
                "build-rom",
                "--extracted",
                extracted_dir,
                "--out",
                rebuilt_nds_path,
                "--base",
                ORIGINAL_ROM,
            ])
            self.assertEqual(ret, 0)
            self.assertTrue(os.path.isfile(rebuilt_nds_path))
            self.assertGreater(os.path.getsize(rebuilt_nds_path), 0)

            # 7. Inspect and validate rebuilt ROM contents
            rebuilt_rom = ndspy.rom.NintendoDSRom.fromFile(rebuilt_nds_path)

            # Verify translated .msg file in rebuilt ROM
            cmes0_bytes = rebuilt_rom.getFileByName("msg/big/cmes0.msg")
            self.assertIsNotNone(cmes0_bytes)
            rebuilt_entries = dump_msg(cmes0_bytes)
            self.assertEqual(rebuilt_entries[0]["original_en"], russian_dialogue)

            # Verify injected font file in rebuilt ROM
            fnt_bytes = rebuilt_rom.getFileByName("msg/big/msgcmn.fnt")
            self.assertIsNotNone(fnt_bytes)
            font_png = os.path.join(temp_dir, "verified_font.png")
            font_json = os.path.join(temp_dir, "verified_font.json")
            dump_fnt_to_png_and_json(fnt_bytes, font_png, font_json)
            with open(font_json, "r", encoding="utf-8") as f:
                font_meta = json.load(f)
            # Original glyph count is 366; extended with 66 Cyrillic glyphs = 432 glyphs
            self.assertGreaterEqual(font_meta["glyph_count"], 432)

            # Verify untranslated file integrity (e.g. system.msg)
            orig_rom = ndspy.rom.NintendoDSRom.fromFile(ORIGINAL_ROM)
            orig_system_bytes = orig_rom.getFileByName("msg/big/system.msg")
            rebuilt_system_bytes = rebuilt_rom.getFileByName("msg/big/system.msg")
            self.assertEqual(rebuilt_system_bytes, orig_system_bytes)

    def test_cli_dump_and_build_font(self):
        """Verify CLI subcommands dump-font and build-font."""
        with tempfile.TemporaryDirectory() as temp_dir:
            extracted_dir = os.path.join(temp_dir, "extracted")
            extracted_data_dir = os.path.join(extracted_dir, "data")
            fonts_dump_dir = os.path.join(temp_dir, "fonts_dump")

            # Unpack first
            main(["unpack", "--nds", ORIGINAL_ROM, "--out", extracted_dir])

            # Dump fonts
            ret = main(["dump-font", "--rom-data", extracted_data_dir, "--out", fonts_dump_dir])
            self.assertEqual(ret, 0)
            self.assertTrue(os.path.isfile(os.path.join(fonts_dump_dir, "msg", "big", "msgcmn.png")))
            self.assertTrue(os.path.isfile(os.path.join(fonts_dump_dir, "msg", "big", "msgcmn.json")))

            # Build fonts back
            ret = main(["build-font", "--font-dir", fonts_dump_dir, "--rom-data", extracted_data_dir])
            self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()
