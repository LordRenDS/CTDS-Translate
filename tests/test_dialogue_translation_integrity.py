"""Tests for Story Dialogue & Scenario Script Clusters translation integrity."""

import json
from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_MSG_DIR = REPO_ROOT / "ai translated text" / "msg" / "big"

DIALOGUE_FILES = [
    # Block 5.1 (Prologue & Fair)
    "msg01.json",
    "cmes0.json",
    "cmes1.json",
    # Block 5.2 (Middle Ages 600 A.D.)
    "msg02.json",
    "cmes2.json",
    "kmes0.json",
    "kmes1.json",
    "kmes2.json",
    # Block 5.3 (Future 2300 A.D.)
    "msg03.json",
    "cmes3.json",
    "mesi0.json",
    # Block 5.4 (Prehistory & Zeal)
    "msg04.json",
    "cmes4.json",
    "mesk0.json",
    "mesk1.json",
    "mesk2.json",
    "mesk3.json",
    "mesk4.json",
    "mess0.json",
    "mest0.json",
    "mest1.json",
    "mest2.json",
    "mest3.json",
    "mest4.json",
    "mest5.json",
    # Block 5.5 (End of Time & Side Quests)
    "cmes5.json",
    "comu0.json",
    "ques0.json",
    "exms0.json",
    "exms1.json",
    "exms2.json",
    "exms3.json",
]


@pytest.mark.parametrize("filename", DIALOGUE_FILES)
def test_dialogue_100_percent_translated(filename):
    """Verify that every entry in dialogue files has a non-empty translation."""
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
        pytest.skip(f"{filename} has no translations yet (future task block)")

    assert not empty_ids, (
        f"Unfinished translation in {filename} for IDs: {empty_ids[:10]} (total: {len(empty_ids)})"
    )


@pytest.mark.parametrize("filename", DIALOGUE_FILES)
def test_dialogue_tag_parity(filename):
    """Verify that all engine tags and hero tokens are preserved byte-for-byte."""
    target_path = AI_MSG_DIR / filename
    assert target_path.is_file(), f"File not found: {target_path}"

    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    has_any = any(item.get("translation", "").strip() for item in data)
    if not has_any:
        pytest.skip(f"{filename} has no translations yet (future task block)")

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
