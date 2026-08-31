"""Unit tests for the ROM Manager module."""

import os
import shutil
import tempfile
import unittest
import ndspy.fnt
import ndspy.rom
from src.rom_manager import (
    build_rom,
    get_nitrofs_paths,
    unpack_rom,
    verify_rom_integrity,
)

ORIGINAL_ROM = os.path.join("rom", "Chrono Trigger (Europe) (En,Fr).nds")


class TestRomManager(unittest.TestCase):
    """Test suite for ROM unpacking, building, and integrity verification."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sample_rom(self, rom_path: str) -> ndspy.rom.NintendoDSRom:
        """Helper to create a small, valid synthetic NDS ROM for fast unit testing."""
        rom = ndspy.rom.NintendoDSRom()
        rom.name = bytearray(b"TEST_ROM\x00\x00\x00\x00")
        rom.idCode = bytearray(b"TEST")
        rom.arm9 = bytearray(b"\x00\x10\xa0\xe3\x1e\xff\x2f\xe1" * 64)
        rom.arm7 = bytearray(b"\x00\x10\xa0\xe3\x1e\xff\x2f\xe1" * 32)
        rom.iconBanner = bytearray(b"\x01\x00" + b"\x00" * 0x83E)

        sub_folder = ndspy.fnt.Folder(files=["dialogue.msg", "config.bin"], firstID=1)
        root_folder = ndspy.fnt.Folder(
            folders=[("msg", sub_folder)],
            files=["title.bin"],
            firstID=0,
        )
        rom.filenames = root_folder
        rom.files = [
            b"Title Screen Binary Data",
            b"Hello Chrono Trigger World!",
            b"Configuration Settings",
        ]
        os.makedirs(os.path.dirname(os.path.abspath(rom_path)), exist_ok=True)
        rom.saveToFile(rom_path)
        return rom

    def test_sample_rom_unpack_rebuild_integrity(self):
        """Test full unpack, rebuild, and integrity verification on a sample ROM."""
        sample_rom_path = os.path.join(self.temp_dir, "sample.nds")
        self._create_sample_rom(sample_rom_path)

        unpack_dir = os.path.join(self.temp_dir, "extracted")
        metadata = unpack_rom(sample_rom_path, unpack_dir)

        self.assertEqual(metadata["name"], "TEST_ROM")
        self.assertEqual(metadata["id_code"], "TEST")
        self.assertEqual(metadata["file_count"], 3)
        self.assertGreater(metadata["arm9_size"], 0)
        self.assertGreater(metadata["arm7_size"], 0)

        # Check extracted files exist on disk
        self.assertTrue(os.path.isfile(os.path.join(unpack_dir, "arm9.bin")))
        self.assertTrue(os.path.isfile(os.path.join(unpack_dir, "arm7.bin")))
        self.assertTrue(os.path.isfile(os.path.join(unpack_dir, "banner.bin")))
        self.assertTrue(os.path.isfile(os.path.join(unpack_dir, "data", "title.bin")))
        self.assertTrue(os.path.isfile(os.path.join(unpack_dir, "data", "msg", "dialogue.msg")))
        self.assertTrue(os.path.isfile(os.path.join(unpack_dir, "data", "msg", "config.bin")))

        # Rebuild ROM
        rebuilt_rom_path = os.path.join(self.temp_dir, "rebuilt.nds")
        build_rom(unpack_dir, rebuilt_rom_path, base_nds_path=sample_rom_path)

        self.assertTrue(os.path.isfile(rebuilt_rom_path))
        self.assertTrue(verify_rom_integrity(sample_rom_path, rebuilt_rom_path))

    def test_scratch_build_without_base(self):
        """Test building a ROM from scratch when base_nds_path is None."""
        scratch_dir = os.path.join(self.temp_dir, "scratch")
        os.makedirs(os.path.join(scratch_dir, "data", "sub"), exist_ok=True)

        with open(os.path.join(scratch_dir, "arm9.bin"), "wb") as f:
            f.write(b"arm9 code" * 16)
        with open(os.path.join(scratch_dir, "arm7.bin"), "wb") as f:
            f.write(b"arm7 code" * 16)
        with open(os.path.join(scratch_dir, "data", "root.txt"), "wb") as f:
            f.write(b"root file data")
        with open(os.path.join(scratch_dir, "data", "sub", "child.txt"), "wb") as f:
            f.write(b"child file data")

        output_rom = os.path.join(self.temp_dir, "scratch.nds")
        build_rom(scratch_dir, output_rom, base_nds_path=None)

        self.assertTrue(os.path.isfile(output_rom))
        loaded_rom = ndspy.rom.NintendoDSRom.fromFile(output_rom)
        paths = get_nitrofs_paths(loaded_rom)
        self.assertIn("root.txt", paths)
        self.assertIn("sub/child.txt", paths)
        self.assertEqual(loaded_rom.getFileByName("sub/child.txt"), b"child file data")

    def test_verify_rom_integrity_negative(self):
        """Test that verify_rom_integrity returns False when ROMs differ."""
        rom1_path = os.path.join(self.temp_dir, "rom1.nds")
        rom2_path = os.path.join(self.temp_dir, "rom2.nds")
        self._create_sample_rom(rom1_path)
        self._create_sample_rom(rom2_path)

        # Modify a file in rom2
        rom2 = ndspy.rom.NintendoDSRom.fromFile(rom2_path)
        rom2.setFileByName("title.bin", b"Tampered Title Screen Data")
        rom2.saveToFile(rom2_path)

        self.assertFalse(verify_rom_integrity(rom1_path, rom2_path))

    def test_clean_rom_metadata_and_inspection(self):
        """Test inspecting clean Chrono Trigger ROM if available."""
        if not os.path.isfile(ORIGINAL_ROM):
            self.skipTest(f"Original ROM not found at {ORIGINAL_ROM}")

        rom = ndspy.rom.NintendoDSRom.fromFile(ORIGINAL_ROM)
        paths = get_nitrofs_paths(rom)

        self.assertGreater(len(paths), 10000)
        self.assertIn("msg/big/system.msg", paths)
        self.assertIn("msg/big/cmes0.msg", paths)
        self.assertIn("msg/big/msgcmn.fnt", paths)

        # Verify ID code
        id_code = rom.idCode.decode("latin-1", errors="ignore").rstrip("\x00")
        self.assertEqual(id_code, "YQUP")


if __name__ == "__main__":
    unittest.main()
