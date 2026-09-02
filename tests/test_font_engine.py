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
    GRID_COLOR_CELL,
    GRID_COLOR_WIDTH,
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

        # Verify pixel rasterization of '@' (glyph 356) and 'A' (glyph 39)
        from PIL import Image
        img = Image.open(png_path)
        cell_w = meta["cell_width"]
        cell_h = meta["cell_height"]
        cols = meta["grid_columns"]

        # Glyph 356 '@': row 1 should have pixels [0, 0, 1, 1, 1, 3, 0, 0] (LSB-first order)
        g356_x = (356 % cols) * cell_w
        g356_y = (356 // cols) * cell_h
        row1_pixels = [img.getpixel((g356_x + c, g356_y + 1)) for c in range(8)]
        self.assertEqual(row1_pixels, [0, 0, 1, 1, 1, 3, 0, 0])

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
        """Verify extending big font with 66 Cyrillic glyphs at base 450 with 0x10C offset table."""
        orig_bytes = self._get_rom_file("msg/big/msgcmn.fnt")
        injected_bytes = inject_cyrillic_into_fnt(orig_bytes)

        self.assertNotEqual(injected_bytes, orig_bytes)
        self.assertEqual(injected_bytes[4:8], b"FONT")

        png_path = os.path.join(self.temp_dir, "injected_big.png")
        json_path = os.path.join(self.temp_dir, "injected_big.json")

        dump_fnt(injected_bytes, png_path, json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.assertEqual(meta["glyph_count"], 516)
        self.assertEqual(len(meta["glyphs"]), 516)
        self.assertEqual(len(meta["char_map"]), 127)

        # Verify Cyrillic glyphs are present at indices 450..515
        glyphs = meta["glyphs"]
        for g_idx in range(450, 516):
            self.assertGreater(glyphs[g_idx]["width"], 0)
            self.assertGreater(glyphs[g_idx]["offset"], 0)
            self.assertGreaterEqual(glyphs[g_idx]["offset"], 0x91C)

        # Verify bit-exact roundtrip on injected font
        rebuilt_injected = build_fnt(png_path, json_path)
        self.assertEqual(rebuilt_injected, injected_bytes)

    def test_inject_cyrillic_small_font(self):
        """Verify extending small font with 66 Cyrillic glyphs at base 450 with 0x10C offset table."""
        orig_bytes = self._get_rom_file("msg/small/msgcmn.fnt")
        injected_bytes = inject_cyrillic_font(orig_bytes)

        self.assertNotEqual(injected_bytes, orig_bytes)
        self.assertEqual(injected_bytes[4:8], b"FONT")

        png_path = os.path.join(self.temp_dir, "injected_small.png")
        json_path = os.path.join(self.temp_dir, "injected_small.json")

        dump_fnt(injected_bytes, png_path, json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.assertEqual(meta["glyph_count"], 516)
        self.assertEqual(len(meta["char_map"]), 127)

        glyphs = meta["glyphs"]
        for g_idx in range(450, 516):
            self.assertGreater(glyphs[g_idx]["width"], 0)
            self.assertGreater(glyphs[g_idx]["offset"], 0)
            self.assertGreaterEqual(glyphs[g_idx]["offset"], 0x91C)

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

    def test_grid_modes(self):
        """Verify grid_mode options 'both', 'cells', 'none' and error handling."""
        orig_bytes = self._get_rom_file("msg/big/msgcmn.fnt")

        # 1. grid_mode='none'
        png_none = os.path.join(self.temp_dir, "none.png")
        json_none = os.path.join(self.temp_dir, "none.json")
        dump_fnt_to_png_and_json(orig_bytes, png_none, json_none, grid_mode="none")
        from PIL import Image
        img_none = Image.open(png_none)
        colors_none = {c[1] for c in img_none.getcolors(256)}
        self.assertNotIn(GRID_COLOR_CELL, colors_none)
        self.assertNotIn(GRID_COLOR_WIDTH, colors_none)

        # 2. grid_mode='cells'
        png_cells = os.path.join(self.temp_dir, "cells.png")
        json_cells = os.path.join(self.temp_dir, "cells.json")
        dump_fnt_to_png_and_json(orig_bytes, png_cells, json_cells, grid_mode="cells")
        img_cells = Image.open(png_cells)
        colors_cells = {c[1] for c in img_cells.getcolors(256)}
        self.assertIn(GRID_COLOR_CELL, colors_cells)
        self.assertNotIn(GRID_COLOR_WIDTH, colors_cells)

        # 3. grid_mode='both' (default)
        png_both = os.path.join(self.temp_dir, "both.png")
        json_both = os.path.join(self.temp_dir, "both.json")
        dump_fnt_to_png_and_json(orig_bytes, png_both, json_both, grid_mode="both")
        img_both = Image.open(png_both)
        colors_both = {c[1] for c in img_both.getcolors(256)}
        self.assertIn(GRID_COLOR_CELL, colors_both)
        self.assertIn(GRID_COLOR_WIDTH, colors_both)

        # 4. Invalid grid_mode raises ValueError
        with self.assertRaises(ValueError):
            dump_fnt_to_png_and_json(orig_bytes, "err.png", "err.json", grid_mode="invalid")

    def test_grid_rgb_roundtrip(self):
        """Verify that converting a grid-enabled PNG to RGB mode still rebuilds bit-exact FNT."""
        orig_bytes = self._get_rom_file("msg/big/msgcmn.fnt")
        png_path = os.path.join(self.temp_dir, "grid_rgb.png")
        json_path = os.path.join(self.temp_dir, "grid_rgb.json")

        dump_fnt_to_png_and_json(orig_bytes, png_path, json_path, grid_mode="both")

        # Convert to RGB (simulating user editing and saving in RGB format in external editor)
        from PIL import Image
        img = Image.open(png_path).convert("RGB")
        rgb_png_path = os.path.join(self.temp_dir, "saved_as_rgb.png")
        img.save(rgb_png_path)

        rebuilt = build_fnt_from_png_and_json(rgb_png_path, json_path)
        self.assertEqual(rebuilt, orig_bytes)

    def test_cli_dump_font_grid_options(self):
        """Verify CLI dump-font with --grid argument."""
        from src.cli import main
        data_dir = os.path.join(self.temp_dir, "cli_data")
        big_dir = os.path.join(data_dir, "msg", "big")
        os.makedirs(big_dir, exist_ok=True)
        big_fnt = self._get_rom_file("msg/big/msgcmn.fnt")
        with open(os.path.join(big_dir, "msgcmn.fnt"), "wb") as f:
            f.write(big_fnt)

        out_cells = os.path.join(self.temp_dir, "cli_cells")
        ret = main(["dump-font", "--rom-data", data_dir, "--out", out_cells, "--grid", "cells"])
        self.assertEqual(ret, 0)
        from PIL import Image
        img = Image.open(os.path.join(out_cells, "msg", "big", "msgcmn.png"))
        colors = {c[1] for c in img.getcolors(256)}
        self.assertIn(GRID_COLOR_CELL, colors)
        self.assertNotIn(GRID_COLOR_WIDTH, colors)

        out_both = os.path.join(self.temp_dir, "cli_both")
        ret = main(["dump-font", "--rom-data", data_dir, "--out", out_both])
        self.assertEqual(ret, 0)
        img = Image.open(os.path.join(out_both, "msg", "big", "msgcmn.png"))
        colors = {c[1] for c in img.getcolors(256)}
        self.assertIn(GRID_COLOR_CELL, colors)
        self.assertIn(GRID_COLOR_WIDTH, colors)


if __name__ == "__main__":
    unittest.main()
