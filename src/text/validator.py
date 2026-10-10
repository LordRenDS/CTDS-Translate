"""Validation and batch formatting for dialogue and UI translation files."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any

from src.text.metrics import (
    DEFAULT_HERO_NAME_WIDTH_PX,
    calculate_line_width_px,
    load_glyph_metrics,
)
from src.text.presets import (
    get_constraints_for_entry,
    get_preset_for_file,
)
from src.text.reflow import (
    wrap_text_block,
)

__all__ = [
    "validate_and_format_directory",
    "validate_and_format_file",
]


def validate_and_format_file(
    file_path: str | Path,
    glyph_widths: dict[str, int] | None = None,
    max_width_px: int | None = None,
    max_lines: int | None = None,
    auto_paginate: bool = False,
    field: str = "translation",
    fix: bool = False,
    out_path: str | Path | None = None,
    hero_name_width_px: int = DEFAULT_HERO_NAME_WIDTH_PX,
    reflow: bool | None = None,
    preset: str = "auto",
    force: bool = False,
    carry: str | None = None,
    font_widths: dict[str, int] | None = None,
    small_widths: dict[str, int] | None = None,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """Validates and formats dialogue or UI text within a single JSON file.

    Checks line pixel widths against effective max_width_px, collects warnings, and optionally
    rewraps/paginates text and writes back in-place or to out_path.

    Args:
        file_path: Path to the JSON file to inspect.
        glyph_widths: Mapping from character to pixel width.
        max_width_px: Maximum pixel width allowed per line (overrides preset if not None).
        max_lines: Maximum lines allowed per page/dialog box (overrides preset if not None).
        auto_paginate: If True, automatically splits pages exceeding max_lines.
        field: Name of string field to validate (default "translation").
        fix: If True, writes rewrapped text back to JSON file.
        out_path: Destination path for fixed JSON file (if None, writes in-place).
        hero_name_width_px: Estimated pixel width for dynamic hero tokens.
        reflow: If True, collapse ragged single line breaks and re-wrap paragraphs.
                If False, preserve existing line breaks if within width.
                (overrides preset if not None).
        preset: Window preset name or "auto" for filename-based detection.
        force: If True, force recalculation and repacking of all text even if lines fit.
        carry: Optional word hyphenation mode ("geo" or "syllable").
        font_widths: Alias for glyph_widths.
        small_widths: Optional metrics for small-font entries.
        dry_run: If True, do not write changes to disk even if fix=True.

    Returns:
        Dict with keys: file_path, total_entries, overflows_found, warnings, modified, changes_count, preset.
    """
    if dry_run is not None and dry_run:
        fix = False

    effective_preset = get_preset_for_file(str(file_path), explicit_preset=preset)
    effective_max_width_px = (
        max_width_px if max_width_px is not None else effective_preset.max_width_px
    )
    effective_max_lines = (
        max_lines if max_lines is not None else effective_preset.max_lines
    )
    effective_reflow = reflow if reflow is not None else effective_preset.reflow

    active_base_widths = font_widths if font_widths is not None else glyph_widths
    if active_base_widths is None:
        active_base_widths = load_glyph_metrics(
            "extracted fonts/msg/big/msgcmn.json",
            "assets/fonts/cyrillic_big.json" if os.path.isfile("assets/fonts/cyrillic_big.json") else None,
        )

    if small_widths is None and os.path.isfile("extracted fonts/msg/small/msgcmn.json"):
        try:
            small_widths = load_glyph_metrics(
                "extracted fonts/msg/small/msgcmn.json",
                "assets/fonts/cyrillic_small.json" if os.path.isfile("assets/fonts/cyrillic_small.json") else None,
            )
        except Exception:
            small_widths = None

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        if "entries" in data and isinstance(data["entries"], list):
            entries = data["entries"]
        elif any(isinstance(v, dict) for v in data.values()):
            entries = [v for v in data.values() if isinstance(v, dict)]
        else:
            entries = [data]
    else:
        entries = []

    total_entries = len(entries)
    overflows_count = 0
    warnings: list[str] = []
    changes_count = 0

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id", i)
        text = entry.get(field)
        if not text or not isinstance(text, str):
            continue

        entry_preset = get_constraints_for_entry(str(file_path), entry_id, explicit_preset=preset)
        entry_max_width_px = (
            max_width_px if max_width_px is not None else entry_preset.max_width_px
        )
        entry_max_lines = (
            max_lines if max_lines is not None else entry_preset.max_lines
        )
        entry_reflow = reflow if reflow is not None else entry_preset.reflow
        active_widths = (
            small_widths
            if (entry_preset.font_type == "small" and small_widths is not None)
            else active_base_widths
        )

        # Check overflows in original lines
        raw_pages = text.split("{PAGE}")
        for raw_page in raw_pages:
            raw_lines = re.split(r"\r?\n|\{LINE\}", raw_page)
            if field in ("original_en", "original_fr") and entry_max_lines == 1 and len(raw_lines) > 1:
                overflows_count += 1
                warnings.append(
                    f"Entry {entry_id}: Page has {len(raw_lines)} lines (exceeds max 1)"
                )
            for raw_line in raw_lines:
                if not raw_line.strip():
                    continue
                line_width = calculate_line_width_px(
                    raw_line, active_widths, hero_name_width_px=hero_name_width_px
                )
                if line_width > entry_max_width_px:
                    overflows_count += 1
                    warnings.append(
                        f"Entry {entry_id}: line exceeds {entry_max_width_px}px ({line_width}px): '{raw_line}'"
                    )

        if fix or field not in ("original_en", "original_fr"):
            wrapped_text, block_warnings = wrap_text_block(
                text,
                active_widths,
                max_width_px=entry_max_width_px,
                max_lines=entry_max_lines,
                auto_paginate=auto_paginate,
                hero_name_width_px=hero_name_width_px,
                reflow=entry_reflow,
                force=force,
                carry=carry,
            )
            for bw in block_warnings:
                warnings.append(f"Entry {entry_id}: {bw}")

            if wrapped_text != text:
                changes_count += 1
                if fix:
                    entry[field] = wrapped_text

    modified = False
    if fix and (changes_count > 0 or out_path is not None):
        target_path = out_path if out_path is not None else file_path
        parent_dir = os.path.dirname(str(target_path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        modified = True

    return {
        "file_path": str(file_path),
        "total_entries": total_entries,
        "overflows_found": overflows_count,
        "warnings": warnings,
        "modified": modified,
        "changes_count": changes_count,
        "preset": effective_preset.name,
    }


def validate_and_format_directory(
    json_dir: str | Path,
    font_json_path: str | Path = "extracted fonts/msg/big/msgcmn.json",
    cyrillic_json_path: str | Path | None = "assets/fonts/cyrillic_big.json",
    max_width_px: int | None = None,
    max_lines: int | None = None,
    auto_paginate: bool = False,
    field: str = "translation",
    fix: bool = False,
    out_dir: str | Path | None = None,
    hero_name_width_px: int = DEFAULT_HERO_NAME_WIDTH_PX,
    glyph_widths: dict[str, int] | None = None,
    reflow: bool | None = None,
    preset: str = "auto",
    force: bool = False,
    carry: str | None = None,
) -> dict[str, Any]:
    """Recursively validates and formats all JSON translation files in a directory.

    Args:
        json_dir: Root directory containing JSON translation files.
        font_json_path: Path to base font JSON (default extracted fonts/msg/big/msgcmn.json).
        cyrillic_json_path: Path to Cyrillic font JSON overlay.
        max_width_px: Maximum pixel width allowed per line (overrides presets if specified).
        max_lines: Maximum lines allowed per page/dialog box (overrides presets if specified).
        auto_paginate: If True, automatically splits pages exceeding max_lines.
        field: Name of string field to validate (default "translation").
        fix: If True, writes rewrapped text back.
        out_dir: Optional destination directory mirroring input hierarchy.
        hero_name_width_px: Estimated pixel width for dynamic hero tokens.
        glyph_widths: Optional preloaded glyph widths dictionary.
        reflow: If True, collapse ragged single line breaks and re-wrap paragraphs.
                If False, preserve existing line breaks if within width.
        preset: Window preset name or "auto" for automatic per-file detection.
        force: If True, force recalculation and repacking of all text even if lines fit.
        carry: Optional word hyphenation mode ("geo" or "syllable").

    Returns:
        Dict with keys: files_checked, files_modified, total_entries, total_overflows,
        total_warnings, presets_used, file_reports.
    """
    if glyph_widths is None:
        glyph_widths = load_glyph_metrics(font_json_path, cyrillic_json_path)

    # Lazily preload small font metrics if present
    small_glyph_widths = None
    small_font_path = "extracted fonts/msg/small/msgcmn.json"
    small_cyr_path = "assets/fonts/cyrillic_small.json"
    if os.path.isfile(small_font_path):
        try:
            cyr_opt = small_cyr_path if os.path.isfile(small_cyr_path) else None
            small_glyph_widths = load_glyph_metrics(small_font_path, cyr_opt)
        except Exception:
            small_glyph_widths = None

    if not os.path.isdir(json_dir):
        raise FileNotFoundError(f"JSON directory not found: {json_dir}")

    json_files: list[str] = []
    for root, _dirs, files in os.walk(json_dir):
        for file in files:
            if file.lower().endswith(".json"):
                json_files.append(os.path.join(root, file))

    json_files.sort()

    file_reports: list[dict[str, Any]] = []
    for file_path in json_files:
        if out_dir is not None:
            rel_path = os.path.relpath(file_path, json_dir)
            target_out_path = os.path.join(str(out_dir), rel_path)
        else:
            target_out_path = None

        target_preset = get_preset_for_file(file_path, explicit_preset=preset)
        file_metrics = (
            small_glyph_widths
            if (target_preset.font_type == "small" and small_glyph_widths is not None)
            else glyph_widths
        )

        report = validate_and_format_file(
            file_path,
            glyph_widths=file_metrics,
            max_width_px=max_width_px,
            max_lines=max_lines,
            auto_paginate=auto_paginate,
            field=field,
            fix=fix,
            out_path=target_out_path,
            hero_name_width_px=hero_name_width_px,
            reflow=reflow,
            preset=preset,
            force=force,
            carry=carry,
        )
        file_reports.append(report)

    files_checked = len(json_files)
    files_modified = sum(1 for r in file_reports if r["modified"])
    total_entries = sum(r["total_entries"] for r in file_reports)
    total_overflows = sum(r["overflows_found"] for r in file_reports)
    total_warnings = sum(len(r["warnings"]) for r in file_reports)

    presets_used: dict[str, int] = {}
    for r in file_reports:
        p_name = r.get("preset", "dialogue")
        presets_used[p_name] = presets_used.get(p_name, 0) + 1

    return {
        "files_checked": files_checked,
        "files_modified": files_modified,
        "total_entries": total_entries,
        "total_overflows": total_overflows,
        "total_warnings": total_warnings,
        "presets_used": presets_used,
        "file_reports": file_reports,
    }
