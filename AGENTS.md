# Chrono Trigger DS (CTDS) Workspace Guidelines

This document establishes the architectural rules, git workflows, testing requirements, graphics integrity policies, script engine parameters, and tooling guidelines for the Chrono Trigger DS (Europe) (En,Fr) localization and reverse-engineering workspace.

---

## 1. Git-flow & Repository Lifecycle

All work within this repository must adhere to structured branch isolation and conventional commit formatting:

### 1.1. Branch Hierarchy
- **`main`**: Production-ready, stable milestone releases and release-tagged ROM builds. Direct commits are strictly prohibited.
- **`dev`**: Primary integration branch for verified features, engine refactors, and pipeline tools. All development branches originate from and merge back into `dev`.
- **`translate`**: Dedicated working branch for script translations, Russian text reflows, dialogue proofreading, and glossary curation.
- **Feature / Bugfix Branches (`feature/*`, `fix/*`)**: Created off `dev` (or `translate` for script-specific fixes). Must pass all automated checks before merging.

### 1.2. Commit Standards
All commit messages must be written in **English**, start with a leading `-`, and follow standard type/scope syntax:

```text
- <type>(<scope>): <short description>
```

- **Supported Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `rules`.
- **Common Scopes**: `graphics`, `text-validator`, `font-engine`, `rom-manager`, `ncer`, `cli`, `rules`.
- **Examples**:
  - `- feat(rules): add CTDS workspace AGENTS.md, adapt title graphics tests for RGBA, and update pipeline skill`
  - `- fix(graphics): support RGBA mode and palette distance matching in build_ncgr_sprite`
  - `- refactor(text-validator): register 24 calibrated window presets with granular sub-presets`

---

## 2. Testing Standards & Quality Assurance

Every modification to code, fonts, graphics, or dialogue scripts must be verified prior to committing:

### 2.1. Automated Unit & Integration Testing (`pytest`)
- Run the full test suite via `pytest` from the workspace root.
- A **100% pass rate** is mandatory. Regressions in NCER roundtripping, font metric tables, text validation, or ROM rebuilding must be resolved immediately.
- Specific test suites:
  - `tests/test_title_graphics.py`: Title menu sprite constraints, OAM boundaries, RGBA/P mode handling, French cell preservation, and roundtrip stability.
  - `tests/test_ncer.py`: NCER binary serialization, CEBK/LABL/TXEU chunk validation, and roundtrip reconstruction.
  - `tests/test_text_validator.py`: VWF width calculation, window preset constraints, and dialogue pagination.
  - `tests/test_graphics_engine.py`: Screen tilemap decompression, LZ10 layers, and tile deduplication.
  - `tests/test_font_engine.py`: 2bpp font parsing, Cyrillic glyph injection, and VWF metric tables.
  - `tests/test_roundtrip.py`: End-to-end ROM unpacking, dumping, inserting, and rebuilding integrity.

### 2.2. Text Validation & Dialogue Budgeting
- Before committing translated JSON scripts, run:
  ```powershell
  python src/cli.py validate-text-length --json-dir "translated text" --fix
  ```
- Use `--file` for single files and optional flags `--paginate`, `--force`, or `--carry geo|syllable` as required by the script structure.

### 2.3. Pristine ROM Non-Destructive Source Policy
- The base ROM dump located at `rom/Chrono Trigger (Europe) (En,Fr).nds` must remain untouched and pristine.
- Modified ROMs are generated strictly to target destinations (e.g., `rom/Chrono Trigger (Russian).nds`).

---

## 3. Graphics & Asset Integrity

Modifying Nintendo DS 2D backgrounds and sprite sheets requires strict adherence to hardware and palette constraints:

### 3.1. Supported Modes & Palette Architecture
- **Modes**: Both **Indexed Mode `P`** (16 colors) and **`RGBA`** (32-bit with alpha channel) are supported for editing in raster packages (Aseprite, Photoshop, GIMP).
- **Quantization & Palette Matching**: When building NCGR files from RGBA images, the pipeline matches non-transparent colors against the 16-color target `.NCLR` palette via minimum Euclidean distance.
- **Transparent Color Index 0**: In Nintendo DS 4bpp sprites, palette index 0 is strictly transparent. Non-transparent pixels (`alpha >= 128`) must never be mapped to index 0; valid visible indices are `1..15`.
- **Palette Length**: Standard sprite sub-palettes contain 16 colors (48 RGB bytes). Full palettes must match original ROM specifications.

### 3.2. 2D OAM & NCER Cell Sheet Architecture
- **12 Hardware OAM Dimensions**:
  - Square: `8×8`, `16×16`, `32×32`, `64×64`.
  - Wide: `16×8`, `32×8`, `32×16`, `64×32`.
  - Tall: `8×16`, `8×32`, `16×32`, `32×64`.
- **1D Mapping Modes (16K–256K)**:
  - Step multiplier: `tile_multiplier = 1 << mapping_mode`.
  - Raw NCGR tile offset: `raw_tile = (attr2 & 0x3FF) * tile_multiplier`.
- **Tile Coverage & Uncovered Blocks**:
  - All 8×8 tiles in NCGR must be accounted for.
  - Tiles unreferenced by cell OAMs are preserved in an auxiliary `uncovered` component (`cell_idx: -1`) to prevent data corruption during sprite rebuilds.
- **Pixel Coordinate Formula**:
  - All canvas bounding calculations use discrete inclusive coordinates:
    $$X_{\text{end}} = X_{\text{start}} + W - 1, \quad Y_{\text{end}} = Y_{\text{start}} + H - 1$$

---

## 4. Script Engine, Control Codes & VWF Metrics

Dialogue scripts contain executable virtual machine bytecode and are displayed through a proportional Variable Width Font (VWF) engine:

### 4.1. Calibrated Window Presets (24 Presets)
The script validator enforces line width and vertical page limits defined in `WINDOW_PRESETS`:

| Preset Name | Max Width (px) | Max Lines | Reflow | Font Type | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `dialogue` | **238** | **3** | `True` | `big` | Standard story and NPC dialogue boxes (`msg*.json`, etc.) |
| `field_choice_box` | **110** | **4** | `False` | `big` | Choice selection boxes on field maps |
| `tutorial` | **200** | **6** | `True` | `big` | Help windows and battle tutorials (`tutorial.json`) |
| `chapter_title` | **130** | **1** | `False` | `big` | Story chapter intro title banners (`ev_title.json`) |
| `battle_banner` | **238** | **1** | `False` | `big` | Monster tech and action announcement banners (`mon_tec.json`) |
| `ending_desc` | **224** | **2** | `True` | `big` | Ending sequence descriptions (`ex_ending.json`) |
| `ending_title` | **180** | **1** | `False` | `big` | Ending sequence title labels |
| `player_char_name` | **100** | **1** | `False` | `big` | Character names in selection and party screens |
| `player_char_profile`| **132** | **6** | `True` | `big` | Character profile description box in status menu |
| `encyclopedia` | **136** | **6** | `True` | `big` | Monster/Item/Arena encyclopedia entries (`player.json`, etc.) |
| `item_desc` | **210** | **1** | `False` | `big` | Item inventory description bar (`item_mes.json`) |
| `item_sub` | **110** | **2** | `False` | `big` | Item additional details / stats (`item_sub.json`) |
| `item_name` | **105** | **1** | `False` | `big` | Inventory item names (`item.json`, `ex_item.json`) |
| `tech_name` | **80** | **1** | `False` | `big` | Tech and magic spell names (`tech.json`) |
| `tech_desc` | **190** | **1** | `False` | `big` | Tech effect descriptions (`tec_mes.json`) |
| `monster_name` | **85** | **1** | `False` | `big` | Enemy combatant names (`monster.json`) |
| `map_location` | **140** | **1** | `False` | `big` | Location name banners (`map.json`, `w_map.json`) |
| `bgm_name` | **145** | **1** | `False` | `big` | Sound test track titles (`bgm.json`) |
| `credits` | **180** | **1** | `False` | `big` | Staff roll credits (`endroll*.json`, `staf.json`) |
| `zukan` | **80** | **1** | `False` | `big` | Bestiary list names (`zukan.json`) |
| `battle` | **180** | **2** | `True` | `big` | In-battle notifications and status messages (`battle.json`) |
| `menu` | **200** | **2** | `False` | `big` | General menu strings fallback (`menu.json`) |
| `system_big` | **200** | **2** | `False` | `big` | Large system UI messages (`big/system.json`) |
| `small_system` | **130** | **1** | `False` | `small` | Compact UI and status bar strings (`small/system.json`) |

### 4.2. Dynamic Variable Tokens & VWF Reservation
- Script tokens substituted at runtime:
  `{CRONO}`, `{MARLE}`, `{LUCCA}`, `{ROBO}`, `{FROG}`, `{AYLA}`, `{MAGUS}`, `{EPOCH}`.
- **Strict Reservation Width**: Dynamic character tokens must **never** be stripped or evaluated as 0-width formatting codes. The VWF engine reserves **`30px`** for each hero token (`DEFAULT_HERO_NAME_WIDTH_PX = 30`) to ensure text boxes never overflow regardless of player name configuration.

### 4.3. Immutability of VM Opcodes & Bytecode Tags
Control codes are executable VM commands. The following tags must be preserved byte-for-byte with identical casing, spacing, and parameters:
- `{PAGE}`: Pagination / dialogue box clear.
- `\n`: Hard line break within dialogue window.
- `{WAIT_KEY}`: Script pause until user button press.
- `{EVENT_SYNC:XX}`: Synchronization barrier with field cutscene events.
- `{SOUND:XX}`: Sound effect trigger.
- Color directives: `{COLOR 0}`, `{COLOR 1}`, etc.

---

## 5. Project Tooling & Pipelines

### 5.1. CTDS NCER Editor (`CTDS_NCER_editor`)
- Sibling workspace located at `d:\Workspace\Programing\Python\CTDS_NCER_editor`.
- Dedicated graphical desktop editor for Nitro Cell Resource (NCER) cell composition, OAM visual layout manipulation, sprite sheet re-packing, and JSON descriptor editing.

### 5.2. Workspace CLI (`python src/cli.py`)
All core pipeline commands are centralized in `src/cli.py`:
- `build-graphics` / `dump-graphics`: Background screens and cell-sheet sprite graphics.
- `validate-text-length`: Proportional VWF calculation, line wrap reflow, and dialogue budgeting.
- `build-font` / `dump-font`: Proprietary 2bpp `.fnt` font serialization and PNG rasterization.
- `inject-cyrillic-font`: Injects authentic 2bpp pixel-art Cyrillic glyphs into all ROM font archives.
- `unpack` / `dump-text` / `insert-text` / `build-rom`: Complete ROM extraction, text serialization, and ROM synthesis.
- `roundtrip`: Automated integrity verification of the entire extraction and reconstruction pipeline.
