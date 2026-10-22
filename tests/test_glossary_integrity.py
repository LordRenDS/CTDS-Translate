"""Tests for Chrono Trigger DS master glossary integrity and canon adherence."""

import json
from pathlib import Path
import pytest
import sys

# Ensure plugin scripts can be imported
PLUGIN_SCRIPTS = Path(r"C:\Users\serge\.gemini\config\plugins\game-localization-plugin\scripts")
if str(PLUGIN_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SCRIPTS))

from glossary_tool import Glossary

REPO_ROOT = Path(__file__).resolve().parent.parent
GLOSSARY_PATH = REPO_ROOT / "glossary" / "ctds_terms.json"


def test_glossary_file_exists_and_loads():
    """Verify that glossary file exists and is parseable by Glossary engine."""
    assert GLOSSARY_PATH.is_file(), f"Glossary not found at: {GLOSSARY_PATH}"

    glossary = Glossary(str(GLOSSARY_PATH))
    assert len(glossary.terms) >= 30, f"Expected at least 30 terms, got {len(glossary.terms)}"


def test_glossary_categories():
    """Verify presence of core categories in glossary."""
    with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    terms = data if isinstance(data, list) else data.get("terms", [])
    categories = {t.get("category") for t in terms}

    expected_categories = {"character", "location", "item", "skill", "system"}
    assert expected_categories.issubset(categories), (
        f"Missing categories: {expected_categories - categories}"
    )


def test_core_canon_characters():
    """Verify official canon character names."""
    with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    terms = {t["source"].lower(): t for t in data if isinstance(t, dict)}

    expected_chars = {
        "crono": "Кроно",
        "marle": "Марле",
        "lucca": "Лукка",
        "robo": "Робо",
        "frog": "Фрог",
        "ayla": "Эйла",
        "magus": "Магус",
        "schala": "Шала",
        "dalton": "Дальтон",
        "lavos": "Лавос",
        "epoch": "Эпоха",
    }

    for en_name, ru_expected in expected_chars.items():
        assert en_name in terms, f"Missing core character term: {en_name}"
        assert ru_expected in terms[en_name]["ru"], (
            f"Expected {ru_expected} in {en_name} translation, got: {terms[en_name]['ru']}"
        )


def test_core_items_and_skills():
    """Verify essential combat, item, and tech terminology."""
    with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    terms = {t["source"].lower(): t for t in data if isinstance(t, dict)}

    expected_terms = {
        "potion": "Зелье",
        "ether": "Эфир",
        "elixir": "Эликсир",
        "shelter": "Убежище",
        "luminaire": "Люминар",
        "flare": "Вспышка",
        "attack": "Атака",
        "tech": "Техника",
        "item": "Предмет",
        "escape": "Побег",
    }

    for en_term, ru_expected in expected_terms.items():
        assert en_term in terms, f"Missing essential term: {en_term}"
        assert ru_expected in terms[en_term]["ru"], (
            f"Expected {ru_expected} in {en_term} translation, got: {terms[en_term]['ru']}"
        )


def test_fair_racers_in_glossary():
    with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    terms = {t["source"].lower(): t for t in data if isinstance(t, dict)}
    expected_racers = {
        "steel runner": "Стальной Бегун",
        "green ambler": "Зелёный Тихоход",
        "catalack": "Каталак",
        "g.i. jogger": "Бравый Бегун",
    }
    for en_name, ru_expected in expected_racers.items():
        assert en_name in terms, f"Missing fair racer in glossary: {en_name}"
        assert terms[en_name]["ru"] == ru_expected
