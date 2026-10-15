"""Tests for AI translation text scaffolding and template initialization."""

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTED_MSG_DIR = REPO_ROOT / "extracted text" / "msg"
AI_MSG_DIR = REPO_ROOT / "ai translated text" / "msg"
EXPECTED_TOTAL_ENTRIES = 16334
EXPECTED_FILE_COUNT = 75


def test_ai_translated_directories_exist():
    """Verify that ai translated text/msg/big and ai translated text/msg/small directories exist."""
    big_dir = AI_MSG_DIR / "big"
    small_dir = AI_MSG_DIR / "small"

    assert big_dir.is_dir(), f"Expected directory does not exist: {big_dir}"
    assert small_dir.is_dir(), f"Expected directory does not exist: {small_dir}"


def test_ai_translated_file_count_matches_extracted():
    """Verify exact count of 75 JSON files in ai translated text/msg matches extracted text/msg."""
    extracted_files = sorted(EXTRACTED_MSG_DIR.glob("**/*.json"))
    ai_files = sorted(AI_MSG_DIR.glob("**/*.json"))

    assert len(extracted_files) == EXPECTED_FILE_COUNT, (
        f"Expected {EXPECTED_FILE_COUNT} extracted files, found {len(extracted_files)}"
    )
    assert len(ai_files) == EXPECTED_FILE_COUNT, (
        f"Expected {EXPECTED_FILE_COUNT} ai translated files, found {len(ai_files)}"
    )

    extracted_rel = [p.relative_to(EXTRACTED_MSG_DIR).as_posix() for p in extracted_files]
    ai_rel = [p.relative_to(AI_MSG_DIR).as_posix() for p in ai_files]
    assert ai_rel == extracted_rel, "Relative paths of ai translated files do not match extracted files"


def test_ai_translated_entries_and_schema():
    """Verify schema, id, original_en, original_fr parity, string translation field, and total count."""
    extracted_files = sorted(EXTRACTED_MSG_DIR.glob("**/*.json"))
    total_entries = 0

    for ext_path in extracted_files:
        rel_path = ext_path.relative_to(EXTRACTED_MSG_DIR)
        ai_path = AI_MSG_DIR / rel_path

        assert ai_path.is_file(), f"Missing template file: {ai_path}"

        with open(ext_path, "r", encoding="utf-8") as f:
            ext_entries = json.load(f)
        with open(ai_path, "r", encoding="utf-8") as f:
            ai_entries = json.load(f)

        assert len(ai_entries) == len(ext_entries), (
            f"Entry count mismatch in {rel_path}: {len(ai_entries)} vs {len(ext_entries)}"
        )

        for idx, (ext_item, ai_item) in enumerate(zip(ext_entries, ai_entries)):
            assert ai_item["id"] == ext_item["id"], (
                f"ID mismatch in {rel_path} item {idx}: {ai_item['id']} vs {ext_item['id']}"
            )
            assert ai_item["original_en"] == ext_item["original_en"], (
                f"original_en mismatch in {rel_path} item {idx}"
            )
            assert ai_item["original_fr"] == ext_item["original_fr"], (
                f"original_fr mismatch in {rel_path} item {idx}"
            )
            assert isinstance(ai_item.get("translation"), str), (
                f"Invalid or missing translation string in {rel_path} item {idx}"
            )

        total_entries += len(ai_entries)

    assert total_entries == EXPECTED_TOTAL_ENTRIES, (
        f"Total entry count is {total_entries}, expected {EXPECTED_TOTAL_ENTRIES}"
    )
