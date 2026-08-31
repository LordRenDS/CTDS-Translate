"""Unit tests for the Font Engine (src/font_engine.py)."""

import json
import os
import shutil
import tempfile
import unittest
import ndspy.rom
from src.font_engine import (
    dump_fnt_to_png_and_json,
    build_fnt_from_png_and_json,
    dump_fnt,
    build_fnt,
    inject_cyrillic_into_fnt,
    inject_cyrillic_font,
    dump_all_fonts,
    build_all_fonts,
)

ORIGINAL_ROM = os.path.join("rom", "Chrono Trigger (Europe) (En,Fr).nds")


class TestFontEngine(unittest.TestCase):
    """Test suite for .fnt parsing, 2bpp PNG sheet extraction, bit-exact rebuilding, and Cyrillic font injection."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _get_rom_file(self, file_path: str) -> bytes:
        """Helper to retrieve raw file bytes from original clean ROM."""
        if not os.path.isfile(ORIGINAL_ROM):
            self.skipTest(f"Original ROM not found at {ORIGINAL_ROM}")
        rom = ndspy.rom.NintendoDSRom.fromFile(ORIGINAL_ROM)
        return rom.getFileByName(file_path)

    def test_font_roundtrip_big(self):
        """Verify 1:1 bit-exact roundtrip on msg/big/msgcmn.fnt."""
        orig_bytes = self._get_rom_file("msg/big/msgcmn.fnt")

        png_path = os.path.join(self.temp_dir, "msgcmn_big.png")
        json_path = os.path.join(self.temp_dir, "msgcmn_big.json")

        dump_fnt_to_png_and_json(orig_bytes, png_path, json_path)
        self.assertTrue(os.path.isfile(png_path))
        self.assertTrue(os.path.isfile(json_path))

        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.assertEqual(meta["magic"], "FONT")
        self.assertEqual(meta["default_width"], 10)
        self.assertEqual(meta["glyph_count"], 366)
        self.assertEqual(len(meta["glyphs"]), 366)

        rebuilt_bytes = build_fnt_from_png_and_json(png_path, json_path)
        self.assertEqual(len(rebuilt_bytes), len(orig_bytes))
        self.assertEqual(rebuilt_bytes, orig_bytes)

    def test_font_roundtrip_small(self):
        """Verify 1:1 bit-exact roundtrip on msg/small/msgcmn.fnt."""
        orig_bytes = self._get_rom_file("msg/small/msgcmn.fnt")

        png_path = os.path.join(self.temp_dir, "msgcmn_small.png")
        json_path = os.path.join(self.temp_dir, "msgcmn_small.json")

        dump_fnt(orig_bytes, png_path, json_path)
        self.assertTrue(os.path.isfile(png_path))
        self.assertTrue(os.path.isfile(json_path))

        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.assertEqual(meta["magic"], "FONT")
        self.assertEqual(meta["default_width"], 8)
        self.assertEqual(meta["glyph_count"], 359)
        self.assertEqual(len(meta["glyphs"]), 359)

        rebuilt_bytes = build_fnt(png_path, json_path)
        self.assertEqual(len(rebuilt_bytes), len(orig_bytes))
        self.assertEqual(rebuilt_bytes, orig_bytes)

    def test_inject_cyrillic_big_font(self):
        """Verify extending big font with 66 Cyrillic glyphs."""
        orig_bytes = self._get_rom_file("msg/big/msgcmn.fnt")
        injected_bytes = inject_cyrillic_into_fnt(orig_bytes)

        self.assertNotEqual(injected_bytes, orig_bytes)
        self.assertEqual(injected_bytes[4:8], b"FONT")

        png_path = os.path.join(self.temp_dir, "injected_big.png")
        json_path = os.path.join(self.temp_dir, "injected_big.json")

        dump_fnt(injected_bytes, png_path, json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        orig_glyph_count = 366
        self.assertEqual(meta["glyph_count"], orig_glyph_count + 66)
        self.assertEqual(len(meta["glyphs"]), orig_glyph_count + 66)

        char_map = meta["char_map"]
        # Verify uppercase Cyrillic (0x80..0x9F)
        for code in range(0x80, 0xA0):
            g_idx = char_map[code]
            self.assertNotEqual(g_idx, 0xFFFF)
            self.assertGreaterEqual(g_idx, orig_glyph_count)
            self.assertLess(g_idx, meta["glyph_count"])

        # Verify lowercase Cyrillic (0xA0..0xBF)
        for code in range(0xA0, 0xC0):
            g_idx = char_map[code]
            self.assertNotEqual(g_idx, 0xFFFF)
            self.assertGreaterEqual(g_idx, orig_glyph_count)
            self.assertLess(g_idx, meta["glyph_count"])

        # Verify Ё and ё (0xC0, 0xC1)
        for code in (0xC0, 0xC1):
            g_idx = char_map[code]
            self.assertNotEqual(g_idx, 0xFFFF)
            self.assertGreaterEqual(g_idx, orig_glyph_count)
            self.assertLess(g_idx, meta["glyph_count"])

        # Verify bit-exact roundtrip on injected font
        rebuilt_injected = build_fnt(png_path, json_path)
        self.assertEqual(rebuilt_injected, injected_bytes)

    def test_inject_cyrillic_small_font(self):
        """Verify extending small font with 66 Cyrillic glyphs."""
        orig_bytes = self._get_rom_file("msg/small/msgcmn.fnt")
        injected_bytes = inject_cyrillic_font(orig_bytes)

        self.assertNotEqual(injected_bytes, orig_bytes)
        self.assertEqual(injected_bytes[4:8], b"FONT")

        png_path = os.path.join(self.temp_dir, "injected_small.png")
        json_path = os.path.join(self.temp_dir, "injected_small.json")

        dump_fnt(injected_bytes, png_path, json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        orig_glyph_count = 359
        self.assertEqual(meta["glyph_count"], orig_glyph_count + 66)

        char_map = meta["char_map"]
        for code in range(0x80, 0xC2):
            g_idx = char_map[code]
            self.assertNotEqual(g_idx, 0xFFFF)
            self.assertGreaterEqual(g_idx, orig_glyph_count)
            self.assertLess(g_idx, meta["glyph_count"])

        rebuilt_injected = build_fnt(png_path, json_path)
        self.assertEqual(rebuilt_injected, injected_bytes)

    def test_dump_and_build_all_fonts_filesystem(self):
        """Verify batch font dumping and rebuilding across directories."""
        data_dir = os.path.join(self.temp_dir, "data")
        big_dir = os.path.join(data_dir, "msg", "big")
        small_dir = os.path.join(data_dir, "msg", "small")
        os.makedirs(big_dir, exist_ok=True)
        os.makedirs(small_dir, exist_ok=True)

        big_fnt = self._get_rom_file("msg/big/msgcmn.fnt")
        small_fnt = self._get_rom_file("msg/small/msgcmn.fnt")

        with open(os.path.join(big_dir, "msgcmn.fnt"), "wb") as f:
            f.write(big_fnt)
        with open(os.path.join(small_dir, "msgcmn.fnt"), "wb") as f:
            f.write(small_fnt)

        out_dir = os.path.join(self.temp_dir, "fonts_out")
        dumped_count = dump_all_fonts(data_dir, out_dir)
        self.assertEqual(dumped_count, 2)

        target_dir = os.path.join(self.temp_dir, "target_data")
        built_count = build_all_fonts(out_dir, target_dir)
        self.assertEqual(built_count, 2)

        with open(os.path.join(target_dir, "msg", "big", "msgcmn.fnt"), "rb") as f:
            rebuilt_big = f.read()
        with open(os.path.join(target_dir, "msg", "small", "msgcmn.fnt"), "rb") as f:
            rebuilt_small = f.read()

        self.assertEqual(rebuilt_big, big_fnt)
        self.assertEqual(rebuilt_small, small_fnt)

    def test_invalid_fnt_raises(self):
        """Verify corrupted or invalid binary raises ValueError."""
        with self.assertRaises(ValueError):
            dump_fnt_to_png_and_json(b"\x00\x00\x00\x00INVALID", "out.png", "out.json")

        with self.assertRaises(ValueError):
            inject_cyrillic_into_fnt(b"SHORT")


if __name__ == "__main__":
    unittest.main()
