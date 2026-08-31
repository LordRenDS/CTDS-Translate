# Chrono Trigger DS Translation Toolset Design

## 1. Overview
The goal of this toolset is to provide a complete, robust, and automated reverse engineering and localization pipeline for the Nintendo DS game *Chrono Trigger* (`Chrono Trigger (Europe) (En,Fr).nds`).

The toolset consists of four core subsystems:
1. **ROM Manager (`src/rom_manager.py`)**: Unpacks and rebuilds the `.nds` ROM image, extracting and repacking the NitroFS filesystem while preserving ARM9/ARM7 binaries, overlays, and headers.
2. **Character & Token Engine (`src/char_map.py`)**: Manages character tables, ASCII/Cyrillic encodings, and bidirectional parsing of game control codes (`{LINE}`, `{PAGE}`, `{CRONO}`, `{WAIT_KEY}`, etc.).
3. **Text Script Engine (`src/text_engine.py`)**: Dumps all `.msg` binary files into structured, human-readable JSON files with control tokens and anchors, and re-compiles JSON files back into binary `.msg` files with exact recalculated pointer tables.
4. **Font Engine (`src/font_engine.py`)**: Dumps proprietary `.fnt` font files (`msg/big/msgcmn.fnt`, `msg/small/msgcmn.fnt`) into editable PNG glyph sheets and JSON metric descriptors, and builds new `.fnt` binary files with Cyrillic glyphs and updated width tables.
5. **Unified CLI & Roundtrip Verification (`src/cli.py` & `tests/test_roundtrip.py`)**: Provides command-line access to all pipeline operations and automates bit-exact / structural roundtrip tests.

---

## 2. Architecture & File Layout

### Directory Layout
```
CTDS/
├── rom/
│   ├── Chrono Trigger (Europe) (En,Fr).nds   # Pristine clean ROM
│   └── Chrono Trigger (Russian).nds           # Patched / Rebuilt ROM
├── extracted rom/
│   ├── arm9.bin
│   ├── arm7.bin
│   ├── banner.bin
│   ├── header.bin
│   └── data/                                  # NitroFS filesystem
├── extracted text/                            # Original extracted JSON files
├── translated text/                           # Localized JSON files for insertion
├── extracted fonts/                           # Dumped PNG glyph sheets & metric JSONs
├── src/
│   ├── __init__.py
│   ├── rom_manager.py
│   ├── char_map.py
│   ├── text_engine.py
│   ├── font_engine.py
│   └── cli.py
└── tests/
    ├── __init__.py
    ├── test_rom_manager.py
    ├── test_text_engine.py
    ├── test_font_engine.py
    └── test_roundtrip.py
```

---

## 3. Detailed Component Specifications

### 3.1 ROM Manager (`src/rom_manager.py`)
- **Library**: `ndspy.rom.NintendoDSRom`
- **Functions**:
  - `unpack_rom(nds_path: str, output_dir: str) -> None`:
    Extracts all NitroFS files into `output_dir/data/`, ARM9 binary to `output_dir/arm9.bin`, ARM7 to `output_dir/arm7.bin`, banner to `output_dir/banner.bin`, and saves ROM metadata.
  - `build_rom(extracted_dir: str, output_nds_path: str) -> None`:
    Reads files from `extracted_dir/data/`, initializes `NintendoDSRom` with original header/ARM9/ARM7 binaries, writes all NitroFS files, recalculates FAT/FNT tables, and writes out the aligned `.nds` file.
  - `verify_rom_rebuild(original_nds_path: str, rebuilt_nds_path: str) -> bool`:
    Compares internal NitroFS files and structure between original and rebuilt ROM.

### 3.2 Character Map & Tokenizer (`src/char_map.py`)
- **Encoding Details**:
  - Text in `.msg` uses a shifted character table relative to ASCII: ASCII `0x20..0x7E` characters map to bytes `c - 1` (where `0x1F` = Space, `0x20` = `!`, `0x40` = `@`, `0x60` = `` ` ``, etc.).
  - Cyrillic letters (`А..Я`, `а..я`, `Ё`, `ё`) are mapped to custom byte codes in the extended range (`0x80..0xBF` or dedicated font glyph indices).
- **Special Opcodes & Anchors**:
  - `\x00` -> `{NULL}`
  - `\x01` -> `{LINE}` (or `\n`)
  - `\x02` -> `{PAGE}` (or delimiter)
  - `\xC5\xB7` -> `{CRONO}`
  - `\xC5\xBF` -> `{WAIT_KEY}`
  - `\xC6\x95[XX]\xC6\x96` -> `{SOUND:XX}` / `{EVENT_SYNC:XX}`
  - Unknown bytes -> `{TAG:XX}` or `\xXX`

### 3.3 Text Script Engine (`src/text_engine.py`)
- **File Structure of `.msg`**:
  - `0x00..0x03`: Zeros (`00 00 00 00`)
  - `0x04..0x07`: ASCII `"TEXT"`
  - `0x08`: Number of language slots (e.g., `4` for English & French variants)
  - `0x09..0x0A`: 16-bit little-endian entry count `N`
  - `0x0B`: Reserved / zero
  - `0x0C..0x0F`: 32-bit little-endian file size
  - `0x10..0x10 + N*16 - 1`: Pointer table of `N * 4` 32-bit offsets.
  - `0x10 + N*16..end`: String payload block.
- **Functions**:
  - `dump_msg_to_json(msg_bytes: bytes) -> list[dict]`:
    Extracts all entries with their English (`original_en`) and French (`original_fr`) text into a JSON-serializable list of dictionaries.
  - `build_msg_from_json(json_entries: list[dict], base_msg_bytes: bytes = None) -> bytes`:
    Rebuilds `.msg` binary with exact headers and updated pointer table, placing translated text into the designated language slot(s).
  - `dump_all_msg(data_dir: str, output_json_dir: str) -> int`:
    Dumps all 75 `.msg` files from `msg/big/` and `msg/small/`.
  - `insert_all_msg(json_dir: str, target_data_dir: str) -> int`:
    Reinserts all translated JSON files back into the NitroFS `data/msg/` directory.

### 3.4 Font Engine (`src/font_engine.py`)
- **File Structure of `.fnt`**:
  - `0x00..0x03`: Zeros
  - `0x04..0x07`: ASCII `"FONT"`
  - `0x08`: Glyph default width (e.g. 10 or 8)
  - `0x09`: Glyph height words / depth info
  - `0x0A..0x0B`: 16-bit glyph count `M` (e.g. 366)
  - `0x0C..0x0D`: Reserved
  - `0x0E..0x10D`: 128 `uint16` character-to-glyph mapping table
  - `0x10E..0x10E + M*4 - 1`: 32-bit offsets to each glyph data block
  - `Glyph Data Block`: `[width: 1 byte, word_count: 1 byte, 16-bit 2bpp scanlines...]`
- **Functions**:
  - `dump_fnt_to_png_and_json(fnt_bytes: bytes, output_png: str, output_json: str) -> None`:
    Extracts 2bpp glyph bitmaps into a grid PNG image and character metrics/mappings to JSON.
  - `build_fnt_from_png_and_json(input_png: str, input_json: str) -> bytes`:
    Generates a valid `.fnt` binary from the image sheet and metrics JSON.
  - `inject_cyrillic_into_fnt(original_fnt_bytes: bytes, ttf_font_path: str = None) -> bytes`:
    Adds Cyrillic character mappings and renders Russian letters into the font table.

---

## 4. Verification & Testing Strategy
- **Unit Tests**:
  - `test_rom_manager.py`: Tests ROM unpacking and packing, checks structure integrity.
  - `test_text_engine.py`: Tests 1:1 roundtrip of `.msg` files (`.msg -> JSON -> .msg == original .msg`).
  - `test_font_engine.py`: Tests 1:1 roundtrip of `.fnt` files (`.fnt -> PNG+JSON -> .fnt == original .fnt`).
  - `test_roundtrip.py`: Full end-to-end pipeline test (Unpack ROM -> Dump text & font -> Rebuild text & font -> Repack ROM -> Verify bootable ROM).
