#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Setup Nintendo DS (NDS) ARM9 Memory Map & Hardware I/O Registers.

This Ghidra script maps standard Nintendo DS memory regions (ITCM, DTCM, Hardware I/O, BIOS)
and sets up descriptive symbols/labels on critical hardware I/O registers (including REG_ROMCTRL
and REG_EXMEMCNT used in anti-piracy checks).

Compatible with:
- Ghidra GUI Script Manager (Jython / PyGhidra)
- Ghidra Headless Analyzer (analyzeHeadless ... -postScript nds_setup_memory.py)
- Ghidra MCP Bridge / pyghidra
- Standalone Python CLI (prints memory layout and register specifications)

@author CTDS Translation Team
@category NDS.Memory
@keybinding
@menupath Tools.NDS.Setup Memory Map
@toolbar
"""

from __future__ import print_function
import sys

# Memory block definitions for ARM9 on Nintendo DS:
# Format: (name, start_addr, size, read, write, execute, is_volatile, description)
NDS_MEMORY_BLOCKS = [
    ("itcm",     0x01000000, 0x00008000, True, True,  True,  False, "Instruction Tightly-Coupled Memory (32 KB)"),
    ("dtcm",     0x027E0000, 0x00004000, True, True,  False, False, "Data Tightly-Coupled Memory (16 KB)"),
    ("io_regs",  0x04000000, 0x00010000, True, True,  False, True,  "Hardware I/O Registers (64 KB, volatile)"),
    ("io_exmem", 0x04100000, 0x00001000, True, True,  False, True,  "Cartridge EXMEM Control Registers (volatile)"),
    ("bios",     0xFFFF0000, 0x00008000, True, False, True,  False, "ARM9 BIOS ROM (32 KB)"),
]

# Standard Nintendo DS Hardware I/O Registers:
# Format: (address, symbol_name, description)
NDS_IO_REGISTERS = [
    # Display & Graphics Registers
    (0x04000000, "REG_DISPCNT",     "Display Control Register (Main Engine)"),
    (0x04000004, "REG_DISPSTAT",    "Display Status & Interrupt Control Register"),
    (0x04000006, "REG_VCOUNT",      "Vertical Line Counter (Scanline 0-262)"),
    (0x04000010, "REG_BG0CNT",      "BG0 Control (Main Engine)"),
    (0x04000012, "REG_BG1CNT",      "BG1 Control (Main Engine)"),
    (0x04000014, "REG_BG2CNT",      "BG2 Control (Main Engine)"),
    (0x04000016, "REG_BG3CNT",      "BG3 Control (Main Engine)"),

    # DMA Channels
    (0x040000B0, "REG_DMA0SAD",     "DMA 0 Source Address"),
    (0x040000B4, "REG_DMA0DAD",     "DMA 0 Destination Address"),
    (0x040000B8, "REG_DMA0CNT",     "DMA 0 Control Register"),
    (0x040000BC, "REG_DMA1SAD",     "DMA 1 Source Address"),
    (0x040000C0, "REG_DMA1DAD",     "DMA 1 Destination Address"),
    (0x040000C4, "REG_DMA1CNT",     "DMA 1 Control Register"),
    (0x040000C8, "REG_DMA2SAD",     "DMA 2 Source Address"),
    (0x040000CC, "REG_DMA2DAD",     "DMA 2 Destination Address"),
    (0x040000D0, "REG_DMA2CNT",     "DMA 2 Control Register"),
    (0x040000D4, "REG_DMA3SAD",     "DMA 3 Source Address"),
    (0x040000D8, "REG_DMA3DAD",     "DMA 3 Destination Address"),
    (0x040000DC, "REG_DMA3CNT",     "DMA 3 Control Register"),

    # Timers
    (0x04000100, "REG_TM0CNT_L",    "Timer 0 Counter / Low"),
    (0x04000102, "REG_TM0CNT_H",    "Timer 0 Control / High"),
    (0x04000104, "REG_TM1CNT_L",    "Timer 1 Counter / Low"),
    (0x04000106, "REG_TM1CNT_H",    "Timer 1 Control / High"),

    # Key Input & RTC
    (0x04000130, "REG_KEYINPUT",    "Key / Button Input Status"),
    (0x04000132, "REG_KEYCNT",      "Key Interrupt Control"),

    # Cartridge Bus / Anti-Piracy Registers (Critical for NDS AP Analysis)
    (0x040001A0, "REG_AUXSPICNT",   "Game Cartridge Aux SPI Bus Control"),
    (0x040001A2, "REG_AUXSPIDATA",  "Game Cartridge Aux SPI Data (EEPROM/Flash/FRAM)"),
    (0x040001A4, "REG_ROMCTRL",     "Game Cartridge ROM Bus Control (Anti-Piracy Check Target)"),
    (0x040001A8, "REG_ROMCMD",      "Game Cartridge 8-Byte Command Buffer"),

    # Interrupts & System Control
    (0x04000204, "REG_IME",         "Interrupt Master Enable Register (0=Disable, 1=Enable)"),
    (0x04000208, "REG_IE",          "Interrupt Enable Register"),
    (0x04000210, "REG_IF",          "Interrupt Flag / Request Acknowledge"),
    (0x04000240, "REG_VRAMCNT",     "VRAM Allocation Control Bank A"),
    (0x04000300, "REG_POSTFLG",     "Post-Boot / Power Status Flag"),
    (0x04000304, "REG_POWCNT1",     "Power Control Main Register"),

    # External Memory Control (Anti-Piracy & Slot-1 Timings)
    (0x04100010, "REG_EXMEMCNT",    "External Memory & Cartridge Bus Timing Control Register"),
]


def setup_nds_memory(program=None):
    """
    Configures NDS memory blocks and I/O register symbols in a Ghidra program.

    Args:
        program: ghidra.program.model.listing.Program instance (defaults to currentProgram)
    """
    if program is None:
        try:
            program = currentProgram  # type: ignore[name-defined]
        except NameError:
            raise RuntimeError(
                "No active Ghidra program found. Run this script inside Ghidra or pass a Program object."
            )

    memory = program.getMemory()
    addr_factory = program.getAddressFactory()
    default_space = addr_factory.getDefaultAddressSpace()
    symbol_table = program.getSymbolTable()
    listing = program.getListing()

    # Determine SourceType for label creation
    source_type = None
    try:
        from ghidra.program.model.symbol import SourceType
        source_type = SourceType.USER_DEFINED
    except ImportError:
        pass

    # Determine CodeUnit for comments
    code_unit_plate = None
    code_unit_eol = None
    try:
        from ghidra.program.model.listing import CodeUnit
        code_unit_plate = CodeUnit.PLATE_COMMENT
        code_unit_eol = CodeUnit.EOL_COMMENT
    except ImportError:
        pass

    tx_id = program.startTransaction("NDS Setup Memory & I/O Symbols")
    success = False

    print("=" * 70)
    print("NDS Memory Setup: Configuring ARM9 Memory Map & I/O Registers")
    print("Program: %s" % program.getName())
    print("=" * 70)

    try:
        # Step 1: Create Memory Blocks
        print("\n[Step 1] Creating Hardware Memory Blocks...")
        for name, start_addr, size, read, write, execute, is_volatile, desc in NDS_MEMORY_BLOCKS:
            existing = memory.getBlock(name)
            if existing is not None:
                print("  [=] Block '%s' already exists at %s (size 0x%X)" % (
                    name, existing.getStart(), existing.getSize()
                ))
                continue

            addr = default_space.getAddress(start_addr)
            existing_at_addr = memory.getBlock(addr)
            if existing_at_addr is not None:
                print("  [!] Address 0x%08X already part of block '%s' - skipping '%s'" % (
                    start_addr, existing_at_addr.getName(), name
                ))
                continue

            try:
                block = memory.createUninitializedBlock(name, addr, size, False)
                block.setRead(read)
                block.setWrite(write)
                block.setExecute(execute)
                block.setVolatile(is_volatile)
                block.setComment("NDS: " + desc)

                perm_str = "%s%s%s%s" % (
                    "R" if read else "-",
                    "W" if write else "-",
                    "X" if execute else "-",
                    " (Volatile)" if is_volatile else ""
                )
                print("  [+] Created block '%s' [0x%08X - 0x%08X] (%s) - %s" % (
                    name, start_addr, start_addr + size - 1, perm_str, desc
                ))
            except Exception as e:
                print("  [-] Error creating block '%s' at 0x%08X: %s" % (name, start_addr, e))

        # Step 2: Create I/O Register Labels and Comments
        print("\n[Step 2] Labeling Hardware I/O Registers...")
        created_labels = 0
        for reg_addr, reg_name, reg_desc in NDS_IO_REGISTERS:
            addr = default_space.getAddress(reg_addr)
            if not memory.contains(addr):
                print("  [?] Address 0x%08X not in memory - skipping %s" % (reg_addr, reg_name))
                continue

            try:
                # Create or update label
                if source_type is not None:
                    symbol_table.createLabel(addr, reg_name, source_type)
                else:
                    # FlatProgramAPI fallback
                    try:
                        createLabel(addr, reg_name, True)  # type: ignore[name-defined]
                    except NameError:
                        pass

                # Set documentation comments
                if code_unit_plate is not None:
                    listing.setComment(addr, code_unit_plate, "%s: %s" % (reg_name, reg_desc))
                elif code_unit_eol is not None:
                    listing.setComment(addr, code_unit_eol, reg_desc)

                print("  [+] Labeled 0x%08X -> %s (%s)" % (reg_addr, reg_name, reg_desc))
                created_labels += 1
            except Exception as e:
                print("  [-] Error labeling 0x%08X (%s): %s" % (reg_addr, reg_name, e))

        print("\n[+] Done! Created/verified %d memory blocks and %d register symbols." % (
            len(NDS_MEMORY_BLOCKS), created_labels
        ))
        success = True

    finally:
        program.endTransaction(tx_id, success)
        print("=" * 70)


def print_standalone_info():
    """Prints memory map and register table when run outside Ghidra."""
    print("=" * 78)
    print("Nintendo DS (ARM9) Memory Map & Hardware Register Reference")
    print("=" * 78)
    print("\nTarget Memory Blocks:")
    print("  %-12s %-12s %-10s %-8s %-12s %s" % (
        "Name", "Start Addr", "Size", "Perms", "Volatile", "Description"
    ))
    print("  " + "-" * 74)
    for name, start, size, r, w, x, vol, desc in NDS_MEMORY_BLOCKS:
        perms = "%s%s%s" % ("R" if r else "-", "W" if w else "-", "X" if x else "-")
        print("  %-12s 0x%08X   0x%-8X %-8s %-12s %s" % (
            name, start, size, perms, "Yes" if vol else "No", desc
        ))

    print("\nKey Hardware I/O Registers:")
    print("  %-12s %-16s %s" % ("Address", "Symbol", "Description"))
    print("  " + "-" * 74)
    for addr, sym, desc in NDS_IO_REGISTERS:
        print("  0x%08X   %-16s %s" % (addr, sym, desc))

    print("\nUsage in Ghidra:")
    print("  1. GUI: Window -> Script Manager -> NDS -> nds_setup_memory.py -> Run")
    print("  2. Headless: analyzeHeadless <proj_dir> <proj_name> -process <file> -postScript nds_setup_memory.py")
    print("  3. PyGhidra / MCP: from nds_setup_memory import setup_nds_memory; setup_nds_memory(currentProgram)")
    print("=" * 78)


# Entry point
if __name__ == "__main__":
    if "currentProgram" in globals() and currentProgram is not None:  # type: ignore[name-defined]
        setup_nds_memory(currentProgram)  # type: ignore[name-defined]
    else:
        print_standalone_info()
