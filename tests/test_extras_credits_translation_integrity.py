"""Tests for Task 6: Extras, Endings, Credits, Wireless & Debug translation integrity."""

import json
from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_MSG_DIR = REPO_ROOT / "ai translated text" / "msg" / "big"

TASK6_FILES = [
    "ex_ending.json",
    "tutorial.json",
    "player.json",
    "ex_illust.json",
    "extra.json",
    "wireless1.json",
    "wireless2.json",
    "endroll1.json",
    "endroll2.json",
    "debug_evt.json",
    "debug_map.json",
]


@pytest.mark.parametrize("filename", TASK6_FILES)
def test_task6_100_percent_translated(filename):
    """Verify that every entry in Task 6 files has a non-empty translation if original_en is non-empty."""
    target_path = AI_MSG_DIR / filename
    assert target_path.is_file(), f"File not found: {target_path}"

    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    empty_ids = []
    has_any = False
    for item in data:
        orig = item.get("original_en", "")
        trans = item.get("translation", "")
        if trans.strip():
            has_any = True
        if orig.strip() and not trans.strip():
            empty_ids.append(item["id"])

    if not has_any:
        pytest.skip(f"{filename} has no translations yet")

    assert not empty_ids, (
        f"Unfinished translation in {filename} for IDs: {empty_ids[:10]} (total: {len(empty_ids)})"
    )


@pytest.mark.parametrize("filename", TASK6_FILES)
def test_task6_tag_parity(filename):
    """Verify that all engine tags and hero tokens are preserved byte-for-byte in Task 6 files."""
    target_path = AI_MSG_DIR / filename
    assert target_path.is_file(), f"File not found: {target_path}"

    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    has_any = any(item.get("translation", "").strip() for item in data)
    if not has_any:
        pytest.skip(f"{filename} has no translations yet")

    tag_pattern = re.compile(r"\{[A-Za-z0-9_:]+\}")

    tag_mismatches = []
    for item in data:
        orig = item.get("original_en", "")
        trans = item.get("translation", "")
        if not orig.strip() or not trans.strip():
            continue

        orig_tags = sorted(tag_pattern.findall(orig))
        trans_tags = sorted(tag_pattern.findall(trans))

        if orig_tags != trans_tags:
            tag_mismatches.append((item["id"], orig_tags, trans_tags))

    assert not tag_mismatches, (
        f"Tag parity error in {filename} for IDs: {tag_mismatches[:5]} (total: {len(tag_mismatches)})"
    )
