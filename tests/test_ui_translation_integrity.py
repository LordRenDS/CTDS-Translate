"""Tests for System UI and Menu translations integrity."""

import json
from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_MSG_DIR = REPO_ROOT / "ai translated text" / "msg"
EXTRACTED_MSG_DIR = REPO_ROOT / "extracted text" / "msg"

TARGET_FILES = [
    "big/menu.json",
    "big/start.json",
    "big/battle.json",
    "big/system.json",
    "small/sfc_btl.json",
    "small/small.json",
    "small/system.json",
]


@pytest.mark.parametrize("rel_path", TARGET_FILES)
def test_ui_files_100_percent_translated(rel_path):
    """Verify that every entry in target UI files has a non-empty translation."""
    target_path = AI_MSG_DIR / rel_path
    assert target_path.is_file(), f"File not found: {target_path}"

    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    empty_ids = []
    for item in data:
        trans = item.get("translation", "")
        # Note: in keyboard charmap tables, original might be empty or control codes;
        # if original_en is non-empty, translation must be non-empty.
        if item.get("original_en", "").strip() and not trans.strip():
            empty_ids.append(item["id"])

    assert not empty_ids, f"Unfinished translation in {rel_path} for IDs: {empty_ids[:10]} (total: {len(empty_ids)})"


@pytest.mark.parametrize("rel_path", TARGET_FILES)
def test_ui_tag_parity(rel_path):
    """Verify that all control tags {...} are preserved in translation."""
    src_path = EXTRACTED_MSG_DIR / rel_path
    dst_path = AI_MSG_DIR / rel_path

    with open(src_path, "r", encoding="utf-8") as f:
        src_data = json.load(f)
    with open(dst_path, "r", encoding="utf-8") as f:
        dst_data = json.load(f)

    tag_regex = re.compile(r"\{[^}]+\}")

    for src_item, dst_item in zip(src_data, dst_data):
        src_text = src_item.get("original_en", "")
        dst_text = dst_item.get("translation", "")

        if not dst_text:
            continue

        # Known exception: IDs 27-29 in menu.json are English-specific ligature glyphs for LV, HP, MP
        if rel_path == "big/menu.json" and src_item["id"] in (27, 28, 29):
            continue

        src_tags = sorted(tag_regex.findall(src_text))
        dst_tags = sorted(tag_regex.findall(dst_text))

        assert src_tags == dst_tags, (
            f"Tag mismatch in {rel_path} ID {src_item['id']}: expected {src_tags}, got {dst_tags}"
        )
