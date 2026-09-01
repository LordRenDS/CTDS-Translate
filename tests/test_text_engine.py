"""Unit tests for the Text Script Engine (src/text_engine.py)."""

import os
import json
import shutil
import tempfile
import unittest
import ndspy.rom
from src.rom_manager import get_nitrofs_paths
from src.text_engine import (
    dump_msg,
    build_msg,
    dump_all_msg,
    insert_all_msg,
)

ORIGINAL_ROM = os.path.join("rom", "Chrono Trigger (Europe) (En,Fr).nds")


class TestTextEngine(unittest.TestCase):
    """Test suite for .msg binary parsing, building, and directory batch operations."""

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

    def test_msg_roundtrip_system(self):
        """Verify 1:1 bit-exact roundtrip on msg/big/system.msg."""
        orig_bytes = self._get_rom_file("msg/big/system.msg")
        entries = dump_msg(orig_bytes, font_type="big")
        self.assertGreater(len(entries), 0)
        self.assertIn("original_en", entries[0])
        self.assertIn("original_fr", entries[0])

        rebuilt_bytes = build_msg(entries, original_msg_bytes=orig_bytes, font_type="big")
        self.assertEqual(len(rebuilt_bytes), len(orig_bytes))
        self.assertEqual(rebuilt_bytes, orig_bytes)

    def test_msg_roundtrip_cmes0(self):
        """Verify 1:1 bit-exact roundtrip and human-readable text on msg/big/cmes0.msg."""
        orig_bytes = self._get_rom_file("msg/big/cmes0.msg")
        entries = dump_msg(orig_bytes, font_type="big")
        self.assertEqual(len(entries), 256)

        # Verify human-readable dialogue
        self.assertIn("Mother: Come on, sleepyhead!", entries[1]["original_en"])
        self.assertIn("Leene's Bell", entries[2]["original_en"])

        rebuilt_bytes = build_msg(entries, original_msg_bytes=orig_bytes, font_type="big")
        self.assertEqual(rebuilt_bytes, orig_bytes)

    def test_msg_roundtrip_cmes1(self):
        """Verify human-readable dialogue on msg/big/cmes1.msg."""
        orig_bytes = self._get_rom_file("msg/big/cmes1.msg")
        entries = dump_msg(orig_bytes, font_type="big")
        self.assertEqual(entries[0]["original_en"], "Hold it right there!")
        self.assertEqual(entries[1]["original_en"], "Robots: Oh!")
        self.assertEqual(entries[2]["original_en"], "Robots: Bro!")

        rebuilt_bytes = build_msg(entries, original_msg_bytes=orig_bytes, font_type="big")
        self.assertEqual(rebuilt_bytes, orig_bytes)

    def test_msg_roundtrip_item(self):
        """Verify 1:1 bit-exact roundtrip and item names on msg/big/item.msg."""
        orig_bytes = self._get_rom_file("msg/big/item.msg")
        entries = dump_msg(orig_bytes, font_type="big")
        self.assertEqual(len(entries), 347)
        self.assertIn("Wooden Sword", entries[1]["original_en"])
        self.assertIn("Bronze Blade", entries[2]["original_en"])

        rebuilt_bytes = build_msg(entries, original_msg_bytes=orig_bytes, font_type="big")
        self.assertEqual(rebuilt_bytes, orig_bytes)

    def test_msg_roundtrip_bgm(self):
        """Verify 1:1 bit-exact roundtrip on msg/big/bgm.msg."""
        orig_bytes = self._get_rom_file("msg/big/bgm.msg")
        entries = dump_msg(orig_bytes, font_type="big")
        self.assertEqual(len(entries), 69)

        rebuilt_bytes = build_msg(entries, original_msg_bytes=orig_bytes, font_type="big")
        self.assertEqual(rebuilt_bytes, orig_bytes)

    def test_msg_roundtrip_small(self):
        """Verify 1:1 bit-exact roundtrip on msg/small/small.msg."""
        orig_bytes = self._get_rom_file("msg/small/small.msg")
        entries = dump_msg(orig_bytes, font_type="small")
        self.assertEqual(len(entries), 48)

        rebuilt_bytes = build_msg(entries, original_msg_bytes=orig_bytes, font_type="small")
        self.assertEqual(rebuilt_bytes, orig_bytes)

    def test_all_rom_msg_files_roundtrip(self):
        """Verify 1:1 bit-exact roundtrip across all 75 .msg files in the ROM."""
        if not os.path.isfile(ORIGINAL_ROM):
            self.skipTest(f"Original ROM not found at {ORIGINAL_ROM}")
        rom = ndspy.rom.NintendoDSRom.fromFile(ORIGINAL_ROM)
        msg_paths = [p for p in get_nitrofs_paths(rom) if p.endswith(".msg")]
        self.assertEqual(len(msg_paths), 75)

        for p in msg_paths:
            orig_bytes = rom.getFileByName(p)
            font_type = "small" if "small" in p.lower() else "big"
            entries = dump_msg(orig_bytes, font_type=font_type)
            rebuilt_bytes = build_msg(entries, original_msg_bytes=orig_bytes, font_type=font_type)
            self.assertEqual(
                rebuilt_bytes,
                orig_bytes,
                f"Roundtrip failed for {p}",
            )

    def test_translation_injection(self):
        """Verify Cyrillic translation replacement and roundtrip."""
        orig_bytes = self._get_rom_file("msg/big/cmes0.msg")
        entries = dump_msg(orig_bytes, font_type="big")

        cyrillic_text = "Привет, Хроно!\nТы проснулся?"
        entries[0]["translation"] = cyrillic_text

        rebuilt_bytes = build_msg(entries, original_msg_bytes=orig_bytes, font_type="big")
        self.assertNotEqual(rebuilt_bytes, orig_bytes)

        re_dumped = dump_msg(rebuilt_bytes, font_type="big")
        self.assertEqual(re_dumped[0]["original_en"], cyrillic_text)

    def test_build_from_scratch(self):
        """Verify building .msg without original base binary."""
        entries = [
            {"id": 0, "original_en": "Wake up, Crono!", "original_fr": "Reveille-toi, Crono!", "translation": ""},
            {"id": 1, "original_en": "Hello world!", "original_fr": "Bonjour monde!", "translation": "Привет мир!"},
        ]
        msg_bytes = build_msg(entries, original_msg_bytes=None, font_type="big")
        self.assertGreater(len(msg_bytes), 16)

        re_dumped = dump_msg(msg_bytes, font_type="big")
        self.assertEqual(len(re_dumped), 2)
        self.assertEqual(re_dumped[0]["original_en"], "Wake up, Crono!")
        self.assertEqual(re_dumped[1]["original_en"], "Привет мир!")

    def test_dump_and_insert_all_msg_filesystem(self):
        """Verify batch dumping and insertion across directory tree."""
        data_dir = os.path.join(self.temp_dir, "data")
        msg_big_dir = os.path.join(data_dir, "msg", "big")
        msg_small_dir = os.path.join(data_dir, "msg", "small")
        os.makedirs(msg_big_dir, exist_ok=True)
        os.makedirs(msg_small_dir, exist_ok=True)

        system_bytes = self._get_rom_file("msg/big/system.msg")
        small_bytes = self._get_rom_file("msg/small/small.msg")

        with open(os.path.join(msg_big_dir, "system.msg"), "wb") as f:
            f.write(system_bytes)
        with open(os.path.join(msg_small_dir, "small.msg"), "wb") as f:
            f.write(small_bytes)

        json_dir = os.path.join(self.temp_dir, "json_out")
        dumped_count = dump_all_msg(data_dir, json_dir)
        self.assertEqual(dumped_count, 2)

        sys_json_path = os.path.join(json_dir, "msg", "big", "system.json")
        small_json_path = os.path.join(json_dir, "msg", "small", "small.json")
        self.assertTrue(os.path.isfile(sys_json_path))
        self.assertTrue(os.path.isfile(small_json_path))

        with open(sys_json_path, "r", encoding="utf-8") as f:
            sys_entries = json.load(f)
        sys_entries[0]["translation"] = "Новый системный текст"
        with open(sys_json_path, "w", encoding="utf-8") as f:
            json.dump(sys_entries, f, ensure_ascii=False, indent=2)

        inserted_count = insert_all_msg(json_dir, data_dir)
        self.assertEqual(inserted_count, 2)

        # Verify updated msg
        with open(os.path.join(msg_big_dir, "system.msg"), "rb") as f:
            updated_sys_bytes = f.read()
        re_dumped_sys = dump_msg(updated_sys_bytes, font_type="big")
        self.assertEqual(re_dumped_sys[0]["original_en"], "Новый системный текст")

    def test_invalid_magic_raises(self):
        """Verify passing corrupted or non-TEXT binary raises ValueError."""
        invalid_bytes = b"\x00\x00\x00\x00INVALID_DATA"
        with self.assertRaises(ValueError):
            dump_msg(invalid_bytes)


if __name__ == "__main__":
    unittest.main()
