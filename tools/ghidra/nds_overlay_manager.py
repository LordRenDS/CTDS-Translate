#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NDS ARM9 Overlay Manager for Ghidra.

Automatically creates Overlay Memory Blocks (isOverlay=True) in Ghidra's Main RAM
address space from the Nintendo DS ARM9 Overlay Table (y9.bin or ROM).

NDS Overlay Table Entry Format (32 bytes per entry):
  - Offset 0x00 (4B): Overlay ID
  - Offset 0x04 (4B): RAM Address (Target Load Address)
  - Offset 0x08 (4B): RAM Size (Bytes loaded from ROM)
  - Offset 0x0C (4B): BSS Size (Uninitialized zero-filled section)
  - Offset 0x10 (4B): Static Initializer Start Address
  - Offset 0x14 (4B): Static Initializer End Address
  - Offset 0x18 (4B): File ID (NitroFS FAT File ID)
  - Offset 0x1C (4B): Compressed Size (bits 0-23) & Flags (bit 24: 1=Compressed)

Compatible with:
  - Ghidra GUI Script Manager (Jython / PyGhidra)
  - Ghidra Headless Analyzer (analyzeHeadless ... -postScript nds_overlay_manager.py [y9.bin] [overlays_dir])
  - Standalone Python CLI: python nds_overlay_manager.py [y9.bin | --rom game.nds]

@author CTDS Translation Team
@category NDS.Overlays
@keybinding
@menupath Tools.NDS.Import Overlays from y9
@toolbar
"""

from __future__ import print_function
import os
import sys
import struct
import argparse
import json


class OverlayEntry(object):
    """Represents a single parsed 32-byte record from NDS ARM9 y9.bin overlay table."""

    def __init__(self, ov_id, ram_address, ram_size, bss_size, sinit_init, sinit_end, file_id, flags):
        self.id = ov_id
        self.ram_address = ram_address
        self.ram_size = ram_size
        self.bss_size = bss_size
        self.sinit_init = sinit_init
        self.sinit_end = sinit_end
        self.file_id = file_id
        self.flags = flags

    @property
    def is_compressed(self):
        """Returns True if bit 24 of flags is set (standard NitroSDK compression flag)."""
        return bool((self.flags >> 24) & 1)

    @property
    def compressed_size(self):
        """Returns the lower 24 bits of flags indicating compressed payload size."""
        return self.flags & 0x00FFFFFF

    @property
    def total_ram_size(self):
        """Total memory consumed in RAM (RAM Size + BSS Size)."""
        return self.ram_size + self.bss_size

    def to_dict(self):
        return {
            "id": self.id,
            "ram_address": "0x%08X" % self.ram_address,
            "ram_size": "0x%X" % self.ram_size,
            "ram_size_bytes": self.ram_size,
            "bss_size": "0x%X" % self.bss_size,
            "bss_size_bytes": self.bss_size,
            "total_ram_size": self.total_ram_size,
            "sinit_init": "0x%08X" % self.sinit_init if self.sinit_init else None,
            "sinit_end": "0x%08X" % self.sinit_end if self.sinit_end else None,
            "file_id": self.file_id,
            "compressed": self.is_compressed,
            "compressed_size": self.compressed_size if self.is_compressed else None,
        }

    def __repr__(self):
        return (
            "<Overlay #%d: RAM=0x%08X Size=0x%X BSS=0x%X FileID=%d Comp=%s>"
            % (self.id, self.ram_address, self.ram_size, self.bss_size, self.file_id, self.is_compressed)
        )


def parse_overlay_table(table_data):
    """
    Parses an ARM9 overlay table buffer (y9.bin) into a list of OverlayEntry objects.

    Args:
        table_data: bytes-like object containing 32-byte records.

    Returns:
        list of OverlayEntry objects.
    """
    if len(table_data) % 32 != 0:
        print("[!] Warning: Overlay table length (%d bytes) is not a multiple of 32." % len(table_data))

    entries = []
    num_entries = len(table_data) // 32
    for i in range(num_entries):
        fields = struct.unpack_from("<8I", table_data, i * 32)
        entries.append(OverlayEntry(*fields))
    return entries


def load_overlay_table_from_file(filepath):
    """Reads and parses an overlay table file (y9.bin)."""
    with open(filepath, "rb") as f:
        data = f.read()
    return parse_overlay_table(data)


def load_overlay_table_from_rom(rom_path):
    """Extracts overlay table and returns entries directly from an NDS ROM."""
    try:
        import ndspy.rom
        rom = ndspy.rom.NintendoDSRom.fromFile(rom_path)
        if not rom.arm9OverlayTable:
            print("[-] ROM does not contain an ARM9 overlay table.")
            return []
        return parse_overlay_table(rom.arm9OverlayTable)
    except ImportError:
        raise RuntimeError("ndspy library is required to extract overlay table directly from .nds ROM file.")


def print_overlay_summary(entries):
    """Displays a formatted table of all overlay entries."""
    print("=" * 96)
    print("Nintendo DS ARM9 Overlay Table Summary (%d overlays)" % len(entries))
    print("=" * 96)
    print(" %-6s %-12s %-12s %-10s %-8s %-12s %-20s" % (
        "ID", "RAM Address", "RAM Size", "BSS Size", "FileID", "Compressed", "Static Init Range"
    ))
    print(" " + "-" * 92)

    total_code_size = 0
    total_bss_size = 0
    compressed_count = 0

    for entry in entries:
        total_code_size += entry.ram_size
        total_bss_size += entry.bss_size
        if entry.is_compressed:
            compressed_count += 1

        sinit_str = "-"
        if entry.sinit_init or entry.sinit_end:
            sinit_str = "0x%08X-0x%08X" % (entry.sinit_init, entry.sinit_end)

        comp_str = "Yes (0x%X)" % entry.compressed_size if entry.is_compressed else "No"

        print(" #%-5d 0x%08X   0x%-10X 0x%-8X %-8d %-12s %s" % (
            entry.id, entry.ram_address, entry.ram_size, entry.bss_size,
            entry.file_id, comp_str, sinit_str
        ))

    print(" " + "-" * 92)
    print(" Total: %d overlays | Code Size: 0x%X (%d KB) | BSS Size: 0x%X (%d KB) | Compressed: %d" % (
        len(entries),
        total_code_size, total_code_size // 1024,
        total_bss_size, total_bss_size // 1024,
        compressed_count
    ))
    print("=" * 96)


# ==============================================================================
# Ghidra Integration Logic
# ==============================================================================

def create_ghidra_overlay_blocks(program, overlay_entries, overlays_dir=None):
    """
    Creates Overlay Memory Blocks in Ghidra with isOverlay=True.

    Args:
        program: ghidra.program.model.listing.Program instance.
        overlay_entries: List of OverlayEntry objects.
        overlays_dir: Optional path to directory containing extracted overlay binaries.
    """
    memory = program.getMemory()
    addr_factory = program.getAddressFactory()
    default_space = addr_factory.getDefaultAddressSpace()
    symbol_table = program.getSymbolTable()

    source_type = None
    try:
        from ghidra.program.model.symbol import SourceType
        source_type = SourceType.USER_DEFINED
    except ImportError:
        pass

    # Monitor instance (Ghidra GUI / headless provides monitor in globals)
    task_monitor = globals().get("monitor", None)
    if task_monitor is None:
        try:
            from ghidra.util.task import TaskMonitor
            task_monitor = TaskMonitor.DUMMY
        except ImportError:
            pass

    tx_id = program.startTransaction("NDS Setup ARM9 Overlays")
    success = False

    print("=" * 78)
    print("Ghidra Overlay Manager: Creating %d Overlay Memory Blocks" % len(overlay_entries))
    print("Program: %s" % program.getName())
    print("Overlays Directory: %s" % (overlays_dir if overlays_dir else "None (Uninitialized blocks)"))
    print("=" * 78)

    created_blocks = 0
    created_bss = 0
    created_symbols = 0

    try:
        for entry in overlay_entries:
            block_name = "ov_%04d" % entry.id
            existing = memory.getBlock(block_name)
            if existing is not None:
                print("  [=] Overlay block '%s' already exists at %s (size 0x%X)" % (
                    block_name, existing.getStart(), existing.getSize()
                ))
                continue

            start_addr = default_space.getAddress(entry.ram_address)

            # Search for candidate overlay binary file if overlays_dir is specified
            file_bytes = None
            if overlays_dir and os.path.isdir(overlays_dir):
                candidate_filenames = [
                    "overlay9_%04d.bin" % entry.id,
                    "overlay_%04d.bin" % entry.id,
                    "ov_%04d.bin" % entry.id,
                    "overlay9_%d.bin" % entry.id,
                    "overlay_%d.bin" % entry.id,
                    "file_%04d.bin" % entry.file_id,
                ]
                for cand in candidate_filenames:
                    cand_path = os.path.join(overlays_dir, cand)
                    if os.path.isfile(cand_path):
                        with open(cand_path, "rb") as f:
                            raw = f.read()

                        # If marked as compressed, decompress using ndspy if available
                        if entry.is_compressed:
                            try:
                                import ndspy.code.codeCompression
                                file_bytes = ndspy.code.codeCompression.decompress(raw)
                                print("  [+] Decompressed %s (%d -> %d bytes)" % (cand, len(raw), len(file_bytes)))
                            except Exception:
                                file_bytes = raw
                        else:
                            file_bytes = raw
                        break

            # Create overlay block with isOverlay=True
            block = None
            if file_bytes is not None and len(file_bytes) > 0:
                try:
                    from java.io import ByteArrayInputStream
                    stream = ByteArrayInputStream(file_bytes)
                    block = memory.createInitializedBlock(
                        block_name, start_addr, stream, len(file_bytes), task_monitor, True
                    )
                    print("  [+] Created initialized overlay '%s' [0x%08X, size 0x%X]" % (
                        block_name, entry.ram_address, len(file_bytes)
                    ))
                except Exception as e:
                    print("  [!] Initialized overlay block creation failed (%s), using uninitialized: %s" % (
                        block_name, e
                    ))
                    block = memory.createUninitializedBlock(block_name, start_addr, entry.ram_size, True)
            else:
                block = memory.createUninitializedBlock(block_name, start_addr, entry.ram_size, True)
                print("  [+] Created uninitialized overlay '%s' [0x%08X, size 0x%X]" % (
                    block_name, entry.ram_address, entry.ram_size
                ))

            # Set execution permissions
            block.setRead(True)
            block.setWrite(True)
            block.setExecute(True)
            block.setComment("NDS Overlay #%d (RAM: 0x%08X, FileID: %d, BSS: 0x%X, Comp: %s)" % (
                entry.id, entry.ram_address, entry.file_id, entry.bss_size, entry.is_compressed
            ))
            created_blocks += 1

            # Overlay Address Space for this specific block
            ov_space = block.getStart().getAddressSpace()

            # Create separate BSS section in the overlay space if bss_size > 0
            if entry.bss_size > 0:
                bss_name = "%s_bss" % block_name
                if memory.getBlock(bss_name) is None:
                    bss_start_addr = ov_space.getAddress(entry.ram_address + entry.ram_size)
                    try:
                        bss_block = memory.createUninitializedBlock(bss_name, bss_start_addr, entry.bss_size, True)
                        bss_block.setRead(True)
                        bss_block.setWrite(True)
                        bss_block.setExecute(False)
                        bss_block.setComment("NDS Overlay #%d BSS section" % entry.id)
                        created_bss += 1
                    except Exception as err:
                        print("  [!] Error creating BSS block '%s': %s" % (bss_name, err))

            # Create labels for static initializer functions
            if entry.sinit_init:
                try:
                    sinit_addr = ov_space.getAddress(entry.sinit_init)
                    sinit_name = "ov_%04d_sinit_init" % entry.id
                    if source_type is not None:
                        symbol_table.createLabel(sinit_addr, sinit_name, source_type)
                    else:
                        try:
                            createLabel(sinit_addr, sinit_name, True)  # type: ignore[name-defined]
                        except NameError:
                            pass
                    created_symbols += 1
                except Exception:
                    pass

            if entry.sinit_end:
                try:
                    sinit_end_addr = ov_space.getAddress(entry.sinit_end)
                    sinit_end_name = "ov_%04d_sinit_end" % entry.id
                    if source_type is not None:
                        symbol_table.createLabel(sinit_end_addr, sinit_end_name, source_type)
                    else:
                        try:
                            createLabel(sinit_end_addr, sinit_end_name, True)  # type: ignore[name-defined]
                        except NameError:
                            pass
                    created_symbols += 1
                except Exception:
                    pass

        print("\n[+] Done! Created %d overlay blocks, %d BSS blocks, and %d symbols." % (
            created_blocks, created_bss, created_symbols
        ))
        success = True

    finally:
        program.endTransaction(tx_id, success)
        print("=" * 78)


def find_default_y9_path(program):
    """Attempts to locate y9.bin automatically near the imported program."""
    try:
        exec_path = program.getExecutablePath()
        if exec_path:
            base_dir = os.path.dirname(exec_path)
            for candidate in ["y9.bin", "arm9_overlay_table.bin", "y9_table.bin"]:
                p = os.path.join(base_dir, candidate)
                if os.path.isfile(p):
                    return p
    except Exception:
        pass
    return None


def run_in_ghidra():
    """Execution entry point when running inside Ghidra."""
    prog = globals().get("currentProgram", None)
    if prog is None:
        print("[-] Error: 'currentProgram' is not defined.")
        return

    # 1. Check if args passed via headless mode or ScriptArgs
    y9_path = None
    overlays_dir = None

    args = globals().get("getScriptArgs", lambda: [])()
    if args and len(args) >= 1:
        y9_path = args[0]
        if len(args) >= 2:
            overlays_dir = args[1]

    # 2. Try default location near program
    if not y9_path or not os.path.isfile(y9_path):
        y9_path = find_default_y9_path(prog)

    # 3. GUI askFile prompt if still not found
    if not y9_path or not os.path.isfile(y9_path):
        ask_file_func = globals().get("askFile", None)
        if ask_file_func is not None:
            try:
                selected = ask_file_func("Select NDS ARM9 Overlay Table (y9.bin)", "Select")
                if selected is not None:
                    y9_path = selected.getAbsolutePath()
            except Exception:
                pass

    if not y9_path or not os.path.isfile(y9_path):
        print("[-] Could not locate y9.bin. Please specify path via script arguments or GUI file picker.")
        return

    # Guess overlays directory if not explicitly provided
    if not overlays_dir:
        y9_dir = os.path.dirname(y9_path)
        cand_ov_dir = os.path.join(y9_dir, "overlays")
        if os.path.isdir(cand_ov_dir):
            overlays_dir = cand_ov_dir
        elif os.path.isdir(y9_dir):
            overlays_dir = y9_dir

    print("[*] Loading overlay table from: %s" % y9_path)
    entries = load_overlay_table_from_file(y9_path)
    print_overlay_summary(entries)
    create_ghidra_overlay_blocks(prog, entries, overlays_dir)


def main():
    """CLI Entry point for standalone execution outside Ghidra."""
    # Check if running within Ghidra environment
    if "currentProgram" in globals() and currentProgram is not None:  # type: ignore[name-defined]
        run_in_ghidra()
        return

    parser = argparse.ArgumentParser(
        description="NDS ARM9 Overlay Manager & Ghidra Table Parser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python nds_overlay_manager.py y9.bin
  python nds_overlay_manager.py y9.bin --export-json overlays.json
  python nds_overlay_manager.py --rom game.nds
        """
    )
    parser.add_argument("table", nargs="?", help="Path to y9.bin (ARM9 overlay table)")
    parser.add_argument("--rom", help="Path to clean .nds ROM file (extracts table automatically)")
    parser.add_argument("--export-json", help="Export parsed overlay entries to JSON file")
    parser.add_argument("--overlays-dir", help="Directory containing extracted overlay9_XXXX.bin files")

    args = parser.parse_args()

    if not args.table and not args.rom:
        parser.print_help()
        print("\n[!] Error: Please provide either a y9.bin file or --rom <file.nds>.")
        sys.exit(1)

    if args.rom:
        print("[*] Extracting overlay table from ROM: %s" % args.rom)
        entries = load_overlay_table_from_rom(args.rom)
    else:
        if not os.path.isfile(args.table):
            print("[-] Error: File not found: %s" % args.table)
            sys.exit(1)
        print("[*] Parsing overlay table: %s" % args.table)
        entries = load_overlay_table_from_file(args.table)

    print_overlay_summary(entries)

    if args.export_json:
        out_path = args.export_json
        data = [e.to_dict() for e in entries]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print("[+] Exported %d overlay records to %s" % (len(entries), out_path))


if __name__ == "__main__":
    main()
