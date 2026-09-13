"""
Unit tests for Ghidra NDS memory setup and overlay manager tools.
"""

import os
import struct
import tempfile
import json
import pytest

from tools.ghidra.nds_setup_memory import (
    NDS_MEMORY_BLOCKS,
    NDS_IO_REGISTERS,
    print_standalone_info,
)
from tools.ghidra.nds_overlay_manager import (
    OverlayEntry,
    parse_overlay_table,
    load_overlay_table_from_file,
    print_overlay_summary,
)


def test_nds_memory_blocks_structure():
    """Verify that all required memory blocks are properly defined."""
    block_names = {b[0]: b for b in NDS_MEMORY_BLOCKS}

    # ITCM: 0x01000000, 0x8000 (32 KB), R/W/X
    assert "itcm" in block_names
    itcm = block_names["itcm"]
    assert itcm[1] == 0x01000000
    assert itcm[2] == 0x8000
    assert itcm[3] is True  # Read
    assert itcm[4] is True  # Write
    assert itcm[5] is True  # Execute

    # DTCM: 0x027E0000, 0x4000 (16 KB), R/W
    assert "dtcm" in block_names
    dtcm = block_names["dtcm"]
    assert dtcm[1] == 0x027E0000
    assert dtcm[2] == 0x4000
    assert dtcm[3] is True
    assert dtcm[4] is True
    assert dtcm[5] is False

    # Hardware I/O: 0x04000000, 0x10000 (64 KB), R/W, Volatile
    assert "io_regs" in block_names
    io = block_names["io_regs"]
    assert io[1] == 0x04000000
    assert io[2] == 0x10000
    assert io[3] is True
    assert io[4] is True
    assert io[6] is True  # Volatile

    # BIOS: 0xFFFF0000, 0x8000 (32 KB), R/X
    assert "bios" in block_names
    bios = block_names["bios"]
    assert bios[1] == 0xFFFF0000
    assert bios[2] == 0x8000
    assert bios[3] is True
    assert bios[4] is False
    assert bios[5] is True


def test_nds_io_registers():
    """Verify presence and addresses of critical I/O registers."""
    reg_map = {reg[0]: reg[1] for reg in NDS_IO_REGISTERS}

    assert 0x04000000 in reg_map
    assert reg_map[0x04000000] == "REG_DISPCNT"

    assert 0x040001A4 in reg_map
    assert reg_map[0x040001A4] == "REG_ROMCTRL"

    assert 0x04000208 in reg_map
    assert reg_map[0x04000208] == "REG_IE"

    assert 0x04000210 in reg_map
    assert reg_map[0x04000210] == "REG_IF"

    assert 0x04100010 in reg_map
    assert reg_map[0x04100010] == "REG_EXMEMCNT"


def test_overlay_entry_dataclass():
    """Verify OverlayEntry field access and helper properties."""
    # Create uncompressed overlay entry
    entry = OverlayEntry(
        ov_id=0,
        ram_address=0x02100000,
        ram_size=0x4000,
        bss_size=0x1000,
        sinit_init=0x02100100,
        sinit_end=0x02100120,
        file_id=12,
        flags=0x00000000,
    )
    assert entry.id == 0
    assert entry.ram_address == 0x02100000
    assert entry.ram_size == 0x4000
    assert entry.bss_size == 0x1000
    assert entry.total_ram_size == 0x5000
    assert entry.is_compressed is False
    assert entry.compressed_size == 0

    # Create compressed overlay entry (flag 0x01002000 -> compressed, comp_size 0x2000)
    comp_entry = OverlayEntry(
        ov_id=1,
        ram_address=0x02180000,
        ram_size=0x8000,
        bss_size=0x500,
        sinit_init=0,
        sinit_end=0,
        file_id=15,
        flags=0x01002000,
    )
    assert comp_entry.id == 1
    assert comp_entry.is_compressed is True
    assert comp_entry.compressed_size == 0x2000


def test_parse_overlay_table():
    """Verify binary parsing of 32-byte y9.bin overlay records."""
    # Pack two 32-byte entries
    rec1 = struct.pack(
        "<8I",
        0,          # ID
        0x02100000, # RAM Address
        0x5000,     # RAM Size
        0x800,      # BSS Size
        0x02100050, # Sinit Start
        0x02100060, # Sinit End
        10,         # FileID
        0x00000000  # Flags (uncompressed)
    )
    rec2 = struct.pack(
        "<8I",
        1,          # ID
        0x02100000, # Same RAM Address (overlay mechanism test)
        0x6200,     # RAM Size
        0x1000,     # BSS Size
        0,          # Sinit Start
        0,          # Sinit End
        11,         # FileID
        0x01003400  # Flags (compressed, size 0x3400)
    )
    raw_data = rec1 + rec2
    entries = parse_overlay_table(raw_data)

    assert len(entries) == 2
    assert entries[0].id == 0
    assert entries[0].ram_address == 0x02100000
    assert entries[0].ram_size == 0x5000
    assert entries[0].is_compressed is False

    assert entries[1].id == 1
    assert entries[1].ram_address == 0x02100000
    assert entries[1].ram_size == 0x6200
    assert entries[1].is_compressed is True
    assert entries[1].compressed_size == 0x3400


def test_load_overlay_table_from_file(tmp_path):
    """Verify file loading and JSON export."""
    rec = struct.pack(
        "<8I",
        42,
        0x02200000,
        0x1000,
        0x200,
        0,
        0,
        99,
        0,
    )
    y9_file = tmp_path / "y9.bin"
    y9_file.write_bytes(rec)

    entries = load_overlay_table_from_file(str(y9_file))
    assert len(entries) == 1
    assert entries[0].id == 42
    assert entries[0].file_id == 99

    d = entries[0].to_dict()
    assert d["id"] == 42
    assert d["ram_address"] == "0x02200000"
