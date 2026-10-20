# Text Validation Engine Overhaul, Choice Formatting & Localization QA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul the text validator and reflow engine to support sub-page boundaries (`{WAIT_KEY}`, `{PAGE}`) and choice tag invariants (`{GLYPH:394}`..`{GLYPH:403}`), add granular UI presets for Extras and Bestiary, extend the glossary with canonical mechanics and terms, implement a static script QA auditor, and fix all visual and translation defects identified during playtesting.

**Architecture:** A segment-based tokenizer isolates `{WAIT_KEY}`/`{PAGE}` dialogue screens prior to wrapping and resets line counts per screen. Choice tags are locked to dedicated lines with leading `\n{TAG:38}{TAG:38}` and internal line-break stripping to protect bottom-screen touch menus. Granular constraints in `presets.py` restrict narrow UI elements (`extra.json` buttons at 95px, `zukan.json` labels at 48px). A static script QA audit tool scans all 250+ JSON scripts for glossary violations, sub-page overflows, choice formatting bugs, and NPC gender mismatches.

**Tech Stack:** Python 3.12, `pytest`, `ruff`, Pillow, custom NDS font engine, JSON.

**Spec:** `docs/superpowers/specs/2026-10-20-text-validation-and-glossary-design.md`

## Global Constraints

- **Python Version**: Python 3.12+ with strict typing and docstrings.
- **Verification Rule**: 100% pass rate in `pytest -v` and zero errors in `ruff check .`.
- **NDS Hardware Rules**: Choice buttons must not exceed 110px; Bestiary stat labels must not exceed 48px; Extra buttons must not exceed 95px.
- **Git Commit Rule**: English commit messages starting with `- <type>(<scope>): <short description>`.
- **Pristine Base ROM**: `rom/Chrono Trigger (Europe) (En,Fr).nds` must remain untouched.

## Review Focus

- Choice options containing internal newlines (`\n`) must collapse them to spaces so bottom-screen buttons never concatenate words without spaces.
- Sub-pages separated by `{WAIT_KEY}` must calculate line counts independently and never leak accumulated width across `{WAIT_KEY}` boundaries.
- Text blocks matching `Title\n   Description` (status tutorials) must maintain line 1 title isolation and leading 3-space indentation on lines 2..3.
- Banned translation patterns (`техников` for Techs, `уровень владения` for weapon types, `Медленно Увеличивает` for statuses) must be caught by both the validator and auditor.
- Bestiary stat labels in `zukan.json` must strictly fit 48px to prevent hardware display buffer truncation.

---

### Task 1: Core Sub-Page Segmentation & Anchor Protection in `reflow.py`

**Files:**
- Modify: `src/text/reflow.py:38-41, 312-458`
- Test: `tests/test_text_validator.py`

**Interfaces:**
- Consumes: `PAGE_DELIM_PATTERN`, `calculate_line_width_px`, `load_glyph_metrics` from `src.text.metrics`
- Produces: `wrap_text_block(text, glyph_widths, max_width_px, max_lines, auto_paginate, reflow, force, carry)` with sub-page isolation

- [ ] **Step 1: Write failing tests for sub-page boundary isolation**

In `tests/test_text_validator.py`, add tests verifying:
1. `test_subpage_wait_key_resets_line_width`: When `{WAIT_KEY}` occurs after a long line, the text immediately following `{WAIT_KEY}` starts on line 1 of the new sub-page with 0px initial width.
2. `test_subpage_line_count_independent_check`: When a text has two blocks separated by `{WAIT_KEY}`, with 2 lines before and 2 lines after, total lines per sub-page is 2 (fits 3-line max without warning). If the second block has 4 lines, a warning is raised specifically for the second sub-page.
3. `test_wait_key_does_not_collapse_into_space`: When reflow is enabled, `{WAIT_KEY}` is preserved and not replaced with space or merged with surrounding words.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_text_validator.py -k "subpage" -v`
Expected: FAIL (sub-page splitting not implemented, `{WAIT_KEY}` collapsed into space).

- [ ] **Step 3: Implement sub-page segmentation in `src/text/reflow.py`**

1. Define `SUBPAGE_DELIMITER_PATTERN = re.compile(r"(\{WAIT_KEY\}|\{PAGE\}|\{GLYPH:407\}|\{GLYPH:408\})")`.
2. In `wrap_text_block`, split text into alternating text chunks and delimiters.
3. Wrap each non-empty text chunk independently with `wrap_line_to_width`, ensuring `max_lines` checking and pagination evaluate each sub-page independently.
4. Rejoin chunks with their original delimiter tags (`{WAIT_KEY}`, `{PAGE}`, etc.).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_text_validator.py -k "subpage" -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```powershell
git add src/text/reflow.py tests/test_text_validator.py
git commit -m "- feat(text): implement sub-page boundary isolation for WAIT_KEY and PAGE tags"
```

---

### Task 2: Dialogue Choice Tag Invariants & Touch Screen Protection in `reflow.py`

**Files:**
- Modify: `src/text/reflow.py:38-41, 228-360`
- Test: `tests/test_text_validator.py`

**Interfaces:**
- Consumes: `CHOICE_TAG_PATTERN`, `CHOICE_MAX_WIDTH_PX`, `calculate_line_width_px` from `src.text`
- Produces: `format_choice_block(text, glyph_widths, max_width_px)` helper and choice invariant enforcement in `wrap_text_block`

- [ ] **Step 1: Write failing tests for choice formatting and touch button protection**

In `tests/test_text_validator.py`, add tests verifying:
1. `test_choice_options_preceded_by_newline_and_tag38`: A string `Question? {TAG:38}{TAG:38}{GLYPH:394}Yes.{GLYPH:395} {TAG:38}{TAG:38}{GLYPH:396}No.{GLYPH:397}` formats with `\n` before each option:
   `Question?\n{TAG:38}{TAG:38}{GLYPH:394}Yes.{GLYPH:395}\n{TAG:38}{TAG:38}{GLYPH:396}No.{GLYPH:397}`.
2. `test_choice_internal_newline_collapsed_to_space`: If choice text contains an internal newline `{GLYPH:394}Play\nme a sad one!{GLYPH:395}`, it is collapsed to `{GLYPH:394}Play me a sad one!{GLYPH:395}`.
3. `test_choice_width_exceeding_110px_warning`: If a choice option exceeds `CHOICE_MAX_WIDTH_PX = 110`, a validation warning is emitted.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_text_validator.py -k "choice" -v`
Expected: FAIL.

- [ ] **Step 3: Implement choice invariant formatting in `src/text/reflow.py`**

1. In `wrap_text_block`, before word-wrapping, parse out choice blocks matching `{GLYPH:39[4-9]}` / `{GLYPH:40[0-3]}`.
2. Ensure each choice block is preceded by `\n{TAG:38}{TAG:38}` (or preserves existing indentation).
3. Sanitize the inner text of `{GLYPH:39x}...{GLYPH:39y}` by replacing `\r?\n|\{LINE\}` with single spaces.
4. Validate that each choice option's text width does not exceed `CHOICE_MAX_WIDTH_PX` (110px).
5. Wrap preceding prompt text to fit available remaining lines (`max_lines - num_choices`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_text_validator.py -k "choice" -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```powershell
git add src/text/reflow.py tests/test_text_validator.py
git commit -m "- feat(text): enforce choice line separation, indentation, and single-line button invariants"
```

---

### Task 3: Granular UI Presets for `extra.json`, `zukan.json` & Status Tutorials

**Files:**
- Modify: `src/text/presets.py:34-250, 370-460`
- Test: `tests/test_text_validator.py`

**Interfaces:**
- Consumes: `TextWindowPreset`, `WINDOW_PRESETS` in `src.text.presets`
- Produces: Enhanced `get_constraints_for_entry` handling `extra.json`, `zukan.json`, and status tutorials in `cmes0.json`

- [ ] **Step 1: Write failing tests for granular UI presets**

In `tests/test_text_validator.py`, add tests verifying:
1. `test_extra_json_button_constraints`: `get_constraints_for_entry('msg/big/extra.json', entry_id=11)` returns preset with `max_width_px=95, max_lines=1, reflow=False`.
2. `test_extra_json_desc_constraints`: `get_constraints_for_entry('msg/big/extra.json', entry_id=20)` returns preset with `max_width_px=224, max_lines=2`.
3. `test_zukan_json_stat_labels_constraints`: `get_constraints_for_entry('msg/big/zukan.json', entry_id=10)` (Weak) returns preset with `max_width_px=48, max_lines=1`.
4. `test_status_tutorial_constraints`: `get_constraints_for_entry('msg/big/cmes0.json', entry_id=106)` (Slow) returns appropriate status tutorial constraints.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_text_validator.py -k "constraints" -v`
Expected: FAIL (presets return default dialogue or general menu limits).

- [ ] **Step 3: Implement granular constraints in `src/text/presets.py`**

1. In `WINDOW_PRESETS`, register:
   - `extra_button`: `max_width_px=95, max_lines=1, reflow=False, font_type="big"`.
   - `extra_desc`: `max_width_px=224, max_lines=2, reflow=True, font_type="big"`.
   - `zukan_stat_label`: `max_width_px=48, max_lines=1, reflow=False, font_type="big"`.
   - `zukan_discovered`: `max_width_px=65, max_lines=1, reflow=False, font_type="big"`.
2. In `get_constraints_for_entry()`:
   - Handle `base_name == "extra.json"`: entries `0..15` $\rightarrow$ `extra_button`, `16..31` $\rightarrow$ `extra_desc`.
   - Handle `base_name == "zukan.json"`: entries `10..13` $\rightarrow$ `zukan_stat_label`, entry `16` $\rightarrow$ `zukan_discovered`.
   - Handle `base_name == "cmes0.json"`: entries `98..114` $\rightarrow$ preserve title and indent description.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_text_validator.py -k "constraints" -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```powershell
git add src/text/presets.py tests/test_text_validator.py
git commit -m "- feat(text-validator): register granular presets for extra.json, zukan.json, and status tutorials"
```

---

### Task 4: Project Glossary Expansion & Terminology Synchronization

**Files:**
- Modify: `glossary/ctds_terms.json`
- Test: `tests/test_glossary.py` (new test file)

**Interfaces:**
- Consumes: JSON array of term definitions `{source, ru, category, notes, ...}`
- Produces: Comprehensive canonical glossary entries for currencies, stats, combat mechanics, status effects, and NPC genders

- [ ] **Step 1: Write glossary verification test**

Create `tests/test_glossary.py` verifying:
1. `test_glossary_valid_json_and_keys`: All entries have required fields (`source`, `ru`, `category`).
2. `test_glossary_has_required_canonical_terms`: Asserts presence of `G` (`З`), `HP` (`ОЗ`), `MP` (`ОМ`), `Techs` (`Техники`), `Lock` (`Блок техник`), `Slow` (`Замедление`), `Weak` (`Слаб.`), `Absorbs` (`Поглощ.`), `Immune` (`Иммун.`), `Music Box` (`Фонограф`).
3. `test_no_duplicate_source_terms`: Ensures no contradictory duplicate entries.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_glossary.py -v`
Expected: FAIL (missing new terms in `ctds_terms.json`).

- [ ] **Step 3: Update `glossary/ctds_terms.json` with canonical entries**

Add entries:
- Currency: `"source": "G", "ru": "З", "category": "system", "notes": "Gold / Золото"`
- Stats: `"source": "HP", "ru": "ОЗ", "category": "system"`, `"source": "MP", "ru": "ОМ", "category": "system"`
- Mechanics: `"source": "Techs", "ru": "Техники", "category": "mechanic", "notes": "Genitive: техник. Never техников"`
- Weapon types: `"source": "Proficiencies", "ru": "Типы оружия", "category": "mechanic", "notes": "Never уровень владения"`
- Status effects: `"Slow" -> "Замедление"`, `"Lock" -> "Блок техник"`, `"Stop" -> "Стоп"`, `"Sleep" -> "Сон"`, `"Chaos" -> "Смятение"`, `"Poison" -> "Яд"`
- Bestiary labels: `"Weak" -> "Слаб."`, `"Absorbs" -> "Поглощ."`, `"Immune" -> "Иммун."`, `"Discovered" -> "Найдено:"`
- UI buttons: `"Music Box" -> "Фонограф"`, `"Item Encyclopedia" -> "Каталог предметов"`
- Truce NPC: `"source": "Truce Inn Patron", "ru": "Посетитель таверны Труса", "category": "npc", "gender": "m"`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_glossary.py -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```powershell
git add glossary/ctds_terms.json tests/test_glossary.py
git commit -m "- feat(glossary): add canonical terms for currency, stats, combat mechanics, and UI labels"
```

---

### Task 5: Static Script QA Auditor Tool & CLI Integration

**Files:**
- Create: `scripts/audit_script_translations.py`
- Modify: `src/cli.py`
- Test: `tests/test_script_auditor.py` (new test file)

**Interfaces:**
- Consumes: All JSON files in `translated text/` and `ai translated text/`, `glossary/ctds_terms.json`
- Produces: `audit_script_file(file_path)` and CLI command `python src/cli.py audit-scripts`

- [ ] **Step 1: Write unit tests for script auditor logic**

Create `tests/test_script_auditor.py` verifying:
1. `test_detects_banned_terms`: Flags strings containing `техников` (when referring to techs) or `уровень владения` (referring to weapon types).
2. `test_detects_choice_tag_violations`: Flags choices missing leading `\n` or containing internal `\n`.
3. `test_detects_subpage_line_overflow`: Flags sub-pages between `{WAIT_KEY}` having > 3 lines.
4. `test_detects_male_npc_female_verb_endings`: Flags feminine past-tense verbs in designated male speech.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_script_auditor.py -v`
Expected: FAIL (`audit_script_translations.py` does not exist).

- [ ] **Step 3: Implement `scripts/audit_script_translations.py` and integrate into `src/cli.py`**

1. Write `scripts/audit_script_translations.py` with:
   - Sub-page parser checking line count `<= max_lines` between `{WAIT_KEY}` / `{PAGE}`.
   - Choice checker verifying `\n{TAG:38}{TAG:38}` before `{GLYPH:394}`, no internal `\n`, width $\le 110\text{px}$.
   - Forbidden regex scanner for MT artifacts (`техников`, `уровень владения`, `Медленно Увеличивает`).
   - Summary report output (total files scanned, anomalies found, detailed violation log).
2. In `src/cli.py`, add `audit-scripts` command invoking the audit scanner with optional `--fix` or `--json-dir` arguments.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_script_auditor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```powershell
git add scripts/audit_script_translations.py src/cli.py tests/test_script_auditor.py
git commit -m "- feat(tools): implement static script QA auditor and audit-scripts CLI command"
```

---

### Task 6: Playtest Issues Remediation, Global Re-Validation & Test Suite Verification

**Files:**
- Modify:
  - `translated text/msg/big/cmes0.json` (and `ai translated text/msg/big/cmes0.json`)
  - `translated text/msg/big/mess0.json` (and `ai translated text/msg/big/mess0.json`)
  - `translated text/msg/big/extra.json` (and `ai translated text/msg/big/extra.json`)
  - `translated text/msg/big/zukan.json` (and `ai translated text/msg/big/zukan.json`)
  - `translated text/msg/big/w_map.json`, `map.json`
- Test: Full test suite (`pytest -v`, `ruff check .`)

**Interfaces:**
- Consumes: All updated tools, presets, reflow engine, and glossary rules
- Produces: Fully corrected, validated JSON script files and clean automated test report

- [ ] **Step 1: Fix identified strings across translation files**

In `cmes0.json`:
- #75 (Truce Inn choice): Ensure choice options are separated by `\n` and have proper tags.
- #77 (Truce Inn patron): Fix feminine past tense to masculine: *«я никогда не видел такого фестиваля!»*.
- #78 (Truce Inn choice): Format `10 З` currency and ensure `\n` before options.
- #92 (Mayor's Manor weapon tutorial): Fix weapon specialization terminology (replace *«уровень владения»* with *«каждый персонаж специализируется на своём виде оружия»*) and ensure each sub-page between `{WAIT_KEY}` fits $\le 3$ lines.
- #106 (Slow status): Fix title to `Замедление\n   Увеличивает время между ходами.`.
- #110 (Lock status): Fix to `Блок техник\n   Запрещает использование техник.`.

In `mess0.json`:
- #46 (Pianist choice): Ensure choices are on separate lines without internal `\n` (`Сыграй грустное!` / `Что-нибудь весёлое!`).

In `extra.json`:
- #11: Set to `Фонограф` (fits 95px button).
- #14: Set to `Каталог предметов` (or `Энциклопедия`).

In `zukan.json`:
- #10: Set to `Слаб.` (fits 48px column).
- #11: Set to `Поглощ.` (fits 48px column).
- #12: Set to `Иммун.` (fits 48px column).
- #16: Set to `Найдено:`.

- [ ] **Step 2: Run `audit-scripts` to discover and fix any other occurrences**

Run: `python src/cli.py audit-scripts --json-dir "translated text" --json-dir "ai translated text"`
Expected: Report output listing zero critical violations (or fix any newly flagged entries).

- [ ] **Step 3: Run full text validation rewrap**

Run: `python src/cli.py validate-text-length --json-dir "translated text" --fix`
Run: `python src/cli.py validate-text-length --json-dir "ai translated text" --fix`
Expected: All files validate cleanly with 0 overflow errors.

- [ ] **Step 4: Run full test suite and linters**

Run:
```powershell
pytest -v
ruff check .
```
Expected: 100% test pass rate, 0 linting warnings.

- [ ] **Step 5: Commit changes**

```powershell
git add "translated text" "ai translated text"
git commit -m "- fix(text): resolve dialogue choices, WAIT_KEY overflows, UI button widths, and translation errors"
```
