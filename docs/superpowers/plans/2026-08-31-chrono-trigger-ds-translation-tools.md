# Chrono Trigger DS Translation Toolset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete, modular, and fully tested translation toolset for *Chrono Trigger (NDS)*, enabling unpacking/rebuilding the ROM, dumping/inserting dialog & UI text in JSON format with control code preservation, and extracting/rebuilding fonts with Cyrillic support.

**Architecture:** The project is split into four decoupled Python modules: `rom_manager.py` (NDS NitroFS lifecycle), `char_map.py` & `text_engine.py` (text and control token parsing/serialization), `font_engine.py` (2bpp font bitmap and width metric processing), and `cli.py` (command-line entry point).

**Tech Stack:** Python 3.12, `ndspy` (NDS container and filesystem manipulation), `Pillow` (glyph rasterization and font sheets), `pytest` (automated testing).

**Spec:** `docs/superpowers/specs/2026-08-31-chrono-trigger-ds-translation-tools-design.md`

## Global Constraints
- Python 3.12+ compatible.
- Preserve 4-byte ARM alignment and recalculate FAT/FNT coherently upon ROM rebuild.
- Preserve all control codes and opcodes (`{LINE}`, `{PAGE}`, `{CRONO}`, `{WAIT_KEY}`, `{TAG:XX}`) during JSON dumping and re-insertion.
- Guarantee 100% roundtrip fidelity: dumping unmodified JSON and reinserting yields a functional, valid binary.

---

### Task 1: ROM Manager (`src/rom_manager.py`)

**Files:**
- Create: `src/rom_manager.py`
- Test: `tests/test_rom_manager.py`

**Interfaces:**
- Produces:
  - `unpack_rom(nds_path: str, output_dir: str) -> dict`
  - `build_rom(extracted_dir: str, output_nds_path: str, base_nds_path: str = None) -> None`
  - `verify_rom_integrity(original_nds_path: str, rebuilt_nds_path: str) -> bool`

- [x] **Step 1: Write test for ROM unpack and repack**
- [x] **Step 2: Run test to verify it fails**
- [x] **Step 3: Implement `src/rom_manager.py`**
- [x] **Step 4: Run test to verify it passes**
- [x] **Step 5: Commit**
`git add src/rom_manager.py tests/test_rom_manager.py && git commit -m "feat: implement NDS ROM unpacker and repacker"`

---

### Task 2: Character Mapping & Token Engine (`src/char_map.py`)

**Files:**
- Create: `src/char_map.py`
- Test: `tests/test_char_map.py`

**Interfaces:**
- Produces:
  - `decode_char(byte_val: int) -> str`
  - `encode_char(char: str) -> int`
  - `tokenize_bytes(raw_bytes: bytes) -> str`
  - `detokenize_string(text: str) -> bytes`

- [x] **Step 1: Write tests for character encoding/decoding and control tokens**

```python
import pytest
from src.char_map import tokenize_bytes, detokenize_string

def test_char_roundtrip_ascii():
    sample_text = "Chrono Trigger: Awakening!"
    encoded = detokenize_string(sample_text)
    decoded = tokenize_bytes(encoded)
    assert decoded == sample_text

def test_control_tokens_roundtrip():
    sample_text = "{CRONO}...\n{WAIT_KEY}\nAre you sleeping?"
    encoded = detokenize_string(sample_text)
    decoded = tokenize_bytes(encoded)
    assert decoded == sample_text
```

- [x] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_char_map.py -v`

- [x] **Step 3: Implement `src/char_map.py`**
Implement character frequency lookup, Caesar shift adjustment, and token parser/regex detokenizer.

- [x] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_char_map.py -v`

- [x] **Step 5: Commit**
`git add src/char_map.py tests/test_char_map.py && git commit -m "feat: implement character mapping and control tokenizer"`

---

### Task 3: Text Script Engine (`src/text_engine.py`)

**Files:**
- Create: `src/text_engine.py`
- Test: `tests/test_text_engine.py`

**Interfaces:**
- Consumes: `char_map.tokenize_bytes`, `char_map.detokenize_string`
- Produces:
  - `dump_msg(msg_bytes: bytes) -> list[dict]`
  - `build_msg(entries: list[dict], original_msg_bytes: bytes = None) -> bytes`
  - `dump_all_msg(nitrofs_dir: str, output_json_dir: str) -> int`
  - `insert_all_msg(json_dir: str, target_nitrofs_dir: str) -> int`

- [x] **Step 1: Write tests for `.msg` parsing and roundtrip compilation**

```python
import os
import ndspy.rom
from src.text_engine import dump_msg, build_msg

ORIGINAL_ROM = "rom/Chrono Trigger (Europe) (En,Fr).nds"

def test_msg_roundtrip_system():
    rom = ndspy.rom.NintendoDSRom.fromFile(ORIGINAL_ROM)
    orig_bytes = rom.getFileByName("msg/big/system.msg")
    
    entries = dump_msg(orig_bytes)
    assert len(entries) > 0
    assert "original_en" in entries[0]
    
    rebuilt_bytes = build_msg(entries, original_msg_bytes=orig_bytes)
    assert rebuilt_bytes == orig_bytes

def test_msg_roundtrip_cmes0():
    rom = ndspy.rom.NintendoDSRom.fromFile(ORIGINAL_ROM)
    orig_bytes = rom.getFileByName("msg/big/cmes0.msg")
    
    entries = dump_msg(orig_bytes)
    rebuilt_bytes = build_msg(entries, original_msg_bytes=orig_bytes)
    assert rebuilt_bytes == orig_bytes
```

- [x] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_text_engine.py -v`

- [x] **Step 3: Implement `src/text_engine.py`**
Implement `.msg` binary reader and serializer with multi-language offset table generation.

- [x] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_text_engine.py -v`

- [x] **Step 5: Commit**
`git add src/text_engine.py tests/test_text_engine.py && git commit -m "feat: implement .msg text dumper and compiler"`

---

### Task 4: Font Engine (`src/font_engine.py`)

**Files:**
- Create: `src/font_engine.py`
- Test: `tests/test_font_engine.py`

**Interfaces:**
- Produces:
  - `dump_fnt(fnt_bytes: bytes, output_png_path: str, output_json_path: str) -> None`
  - `build_fnt(input_png_path: str, input_json_path: str) -> bytes`
  - `inject_cyrillic_font(original_fnt_bytes: bytes) -> bytes`

- [ ] **Step 1: Write test for `.fnt` font dumping, bitmap rasterization, and rebuilding**

```python
import os
import ndspy.rom
from src.font_engine import dump_fnt, build_fnt

ORIGINAL_ROM = "rom/Chrono Trigger (Europe) (En,Fr).nds"

def test_font_dump_and_rebuild(tmp_path):
    rom = ndspy.rom.NintendoDSRom.fromFile(ORIGINAL_ROM)
    fnt_bytes = rom.getFileByName("msg/big/msgcmn.fnt")
    
    png_path = str(tmp_path / "msgcmn.png")
    json_path = str(tmp_path / "msgcmn.json")
    
    dump_fnt(fnt_bytes, png_path, json_path)
    assert os.path.exists(png_path)
    assert os.path.exists(json_path)
    
    rebuilt_fnt = build_fnt(png_path, json_path)
    assert len(rebuilt_fnt) == len(fnt_bytes)
    assert rebuilt_fnt == fnt_bytes
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_font_engine.py -v`

- [ ] **Step 3: Implement `src/font_engine.py`**
Implement 2bpp bitmap reader/writer, character width table parser, and Cyrillic character injection logic.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_font_engine.py -v`

- [ ] **Step 5: Commit**
`git add src/font_engine.py tests/test_font_engine.py && git commit -m "feat: implement .fnt font dumper and compiler with Cyrillic support"`

---

### Task 5: Unified CLI & End-to-End Roundtrip Tests (`src/cli.py` & `tests/test_roundtrip.py`)

**Files:**
- Create: `src/cli.py`
- Create: `tests/test_roundtrip.py`

**Interfaces:**
- CLI Commands:
  - `unpack` -> Unpack ROM to `extracted rom/`
  - `dump-text` -> Dump all text to `extracted text/`
  - `insert-text` -> Insert text from `translated text/` into `extracted rom/data/`
  - `dump-font` -> Dump fonts to `extracted fonts/`
  - `build-font` -> Rebuild fonts from `extracted fonts/`
  - `build-rom` -> Pack `extracted rom/` into `rom/Chrono Trigger (Russian).nds`
  - `roundtrip` -> Execute full test suite

- [ ] **Step 1: Write end-to-end roundtrip test**

```python
import subprocess
import os

def test_full_pipeline_roundtrip():
    # Test full CLI pipeline execution
    result = subprocess.run(["python", "-m", "src.cli", "roundtrip"], capture_output=True, text=True)
    assert result.returncode == 0
```

- [ ] **Step 2: Implement `src/cli.py` and `tests/test_roundtrip.py`**

- [ ] **Step 3: Run full test suite to verify everything passes**
Run: `pytest tests/ -v`

- [ ] **Step 4: Commit**
`git add src/cli.py tests/test_roundtrip.py && git commit -m "feat: implement CLI interface and full pipeline roundtrip tests"`
