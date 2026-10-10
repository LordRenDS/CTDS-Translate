# Chrono Trigger DS (CTDS) Translation Toolset

A comprehensive translation and romhacking toolset for **Chrono Trigger DS** (Nintendo DS, European En/Fr release).

## Features

- **ROM Management**: Unpack and rebuild Nintendo DS `.nds` ROM images with NitroFS filesystem integrity.
- **Text Engine**: Extract script dialogue from binary `.msg` files to structured JSON and compile translated JSON back to binary.
- **Font Engine**: Extract 2bpp `.fnt` font files to PNG glyph sheets and JSON metrics, inject custom Cyrillic pixel-art glyphs, and compile fonts back to binary.
- **Text Validator & Reflow**: Calibrated variable-width font (VWF) pixel width validator with 24 window presets, automatic dialogue line breaking, hyphenation, and pagination (`{PAGE}`).
- **Graphics Engine**: Full support for Nintendo DS 2D graphics formats:
  - **NCGR**: Character / Tile Graphics (4bpp & 8bpp tiles)
  - **NSCR**: Screen Tilemaps (background plane assembly)
  - **NCLR**: Color Palettes (BGR555 / RGB conversions)
  - **NCER**: Cell / Sprite Bank metadata and OAM piece layout reconstruction
  - **LZ10**: Bios decompression and byte-aligned compression

## Requirements

- Python 3.10 or newer
- Dependencies:
  - `ndspy>=4.0.0`
  - `pillow>=9.5.0`
- Development dependencies:
  - `pytest>=7.0.0`
  - `ruff>=0.1.0`
  - `mypy>=1.0.0`

## Installation

Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/your-username/CTDS.git
cd CTDS
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Architecture

The codebase is organized into modular subpackages under `src/`:

- `src/core/`: Domain exceptions and base types (`CtdsError`, `RomError`, `GraphicsError`, `FontError`, `ValidationError`).
- `src/rom/`: ROM unpacking, rebuilding, and integrity verification.
- `src/font/`: Font binary parsing, PNG rasterization, and glyph injection.
- `src/text/`: Dialogue script extraction, VWF metrics calculation, window presets, and reflow algorithms.
- `src/graphics/`: LZ10 compression, NCLR palette matching, NCGR/NSCR tilemaps, and NCER sprite engines.
- `src/cli.py`: Unified command-line interface entry point.

## CLI Usage

Run the CLI using `python src/cli.py <subcommand> [options]`.

### ROM Operations

- **Unpack ROM**:
  ```bash
  python src/cli.py unpack --nds "rom/Chrono Trigger (Europe) (En,Fr).nds" --out "extracted rom"
  ```

- **Build Patched ROM**:
  ```bash
  python src/cli.py build-rom --base-nds "rom/Chrono Trigger (Europe) (En,Fr).nds" --rom-data "extracted rom" --out "build/ctds_ru.nds"
  ```

### Script & Dialogue Operations

- **Dump Text to JSON**:
  ```bash
  python src/cli.py dump-text --rom-data "extracted rom/data" --out "extracted text"
  ```

- **Insert Translated Text**:
  ```bash
  python src/cli.py insert-text --json-dir "translated text" --rom-data "extracted rom/data"
  ```

- **Validate & Reflow Dialogue Length**:
  ```bash
  python src/cli.py validate-text-length --json-dir "translated text" --font-metrics "extracted fonts/font_metrics.json" --preset standard_dialogue --auto-fix
  ```

### Font Operations

- **Dump Fonts to PNG & JSON**:
  ```bash
  python src/cli.py dump-font --rom-data "extracted rom/data" --out "extracted fonts" --grid both
  ```

- **Build Fonts from PNG & JSON**:
  ```bash
  python src/cli.py build-font --font-dir "extracted fonts" --rom-data "extracted rom/data"
  ```

- **Inject Cyrillic Glyphs**:
  ```bash
  python src/cli.py inject-cyrillic-font --rom-data "extracted rom/data"
  ```

### Graphics Operations

- **Dump Screen & Sprite Graphics**:
  ```bash
  python src/cli.py dump-graphics --rom-data "extracted rom/data" --out "extracted image"
  ```

- **Build Graphics**:
  ```bash
  python src/cli.py build-graphics --img-dir "translated image" --rom-data "extracted rom/data"
  ```

### Verification & Roundtrip

- **Run Roundtrip Test**:
  ```bash
  python src/cli.py roundtrip --nds "rom/Chrono Trigger (Europe) (En,Fr).nds"
  ```

## Running Tests

Run the full pytest suite from the repository root:

```bash
pytest
```

Run specific test modules:

```bash
pytest tests/test_core_exceptions.py -v
pytest tests/test_char_map.py -v
pytest tests/test_text_validator.py -v
```

## Linting and Type Checking

```bash
ruff check .
mypy src
```
