"""Tests for Entities, Items, Techs, and Bestiary translation integrity."""

import json
from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_MSG_DIR = REPO_ROOT / "ai translated text" / "msg"
EXTRACTED_MSG_DIR = REPO_ROOT / "extracted text" / "msg"

ENTITY_FILES = [
    "big/item.json",
    "big/item_mes.json",
    "big/item_mes2.json",
    "big/item_sub.json",
    "big/ex_item.json",
    "big/ex_itemget.json",
    "small/sfc_item.json",
    "big/tech.json",
    "big/tec_mes.json",
    "big/mon_tec.json",
    "big/wireless_tec.json",
    "small/sfc_tec.json",
    "big/monster.json",
    "big/ex_mon.json",
    "big/ex_monspot.json",
    "big/ex_montec.json",
    "big/wireless_mon.json",
    "big/wireless_mon2.json",
    "big/zukan.json",
    "small/sfc_mon.json",
    "big/map.json",
    "big/w_map.json",
    "big/bgm.json",
    "big/ev_title.json",
]


@pytest.mark.parametrize("rel_path", ENTITY_FILES)
def test_entities_100_percent_translated(rel_path):
    """Verify that every entry in entity files has a non-empty translation."""
    target_path = AI_MSG_DIR / rel_path
    assert target_path.is_file(), f"File not found: {target_path}"

    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    empty_ids = []
    for item in data:
        trans = item.get("translation", "")
        if item.get("original_en", "").strip() and not trans.strip():
            empty_ids.append(item["id"])

    assert not empty_ids, f"Unfinished translation in {rel_path} for IDs: {empty_ids[:10]} (total: {len(empty_ids)})"


def test_core_item_glossary_adherence():
    """Verify that item.json matches canonical glossary names."""
    from src.text_validator import strip_control_tags
    item_path = AI_MSG_DIR / "big/item.json"
    with open(item_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    item_dict = {
        strip_control_tags(item.get("original_en", "")): strip_control_tags(item.get("translation", ""))
        for item in items
    }

    expected_matches = {
        "Potion": "Зелье",
        "Ether": "Эфир",
        "Elixir": "Эликсир",
        "Shelter": "Убежище",
        "Masamune": "Масамунэ",
        "Gate Key": "Ключ Врат",
        "Chrono Trigger": "Хроно Триггер",
    }

    for en_name, ru_expected in expected_matches.items():
        assert en_name in item_dict, f"Missing item '{en_name}' in item.json"
        assert item_dict[en_name] == ru_expected, (
            f"Expected item '{en_name}' to be '{ru_expected}', got '{item_dict[en_name]}'"
        )
