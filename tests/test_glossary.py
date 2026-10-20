"""Tests for Chrono Trigger DS project glossary schema and canonical terms."""

import json
from collections import defaultdict
from pathlib import Path

GLOSSARY_PATH: Path = (
    Path(__file__).resolve().parent.parent / "glossary" / "ctds_terms.json"
)


def _load_glossary() -> list[dict[str, str]]:
    """Load and parse the project glossary JSON file.

    Returns:
        List of glossary entry dictionaries.
    """
    assert GLOSSARY_PATH.is_file(), f"Glossary file not found: {GLOSSARY_PATH}"
    with GLOSSARY_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list), f"Expected list of entries, got {type(data)}"
    return data


def test_glossary_valid_json_and_keys() -> None:
    """Ensure all glossary entries are valid dictionaries with required keys."""
    entries = _load_glossary()
    assert len(entries) > 0, "Glossary must not be empty"

    required_keys = {"source", "ru", "category"}
    for idx, entry in enumerate(entries):
        assert isinstance(
            entry, dict
        ), f"Entry {idx} is not a dictionary: {entry}"
        missing_keys = required_keys - set(entry.keys())
        assert not missing_keys, f"Entry {idx} missing required keys {missing_keys}: {entry}"
        assert isinstance(entry["source"], str) and entry["source"].strip(), (
            f"Entry {idx} has invalid source: {entry}"
        )
        assert isinstance(entry["ru"], str) and entry["ru"].strip(), (
            f"Entry {idx} has invalid ru translation: {entry}"
        )
        assert isinstance(entry["category"], str) and entry["category"].strip(), (
            f"Entry {idx} has invalid category: {entry}"
        )


def test_glossary_has_required_canonical_terms() -> None:
    """Verify presence of core canonical terms and translations."""
    entries = _load_glossary()
    term_map: dict[str, dict[str, str]] = {e["source"]: e for e in entries}

    required_terms: dict[str, str] = {
        "G": "З",
        "HP": "ОЗ",
        "MP": "ОМ",
        "Techs": "Техники",
        "Lock": "Блок техник",
        "Slow": "Замедление",
        "Weak": "Слаб.",
        "Absorbs": "Поглощ.",
        "Immune": "Иммун.",
        "Music Box": "Фонограф",
    }

    missing_terms: list[str] = []
    mismatched_translations: list[str] = []

    for source, expected_ru in required_terms.items():
        if source not in term_map:
            missing_terms.append(source)
        elif term_map[source].get("ru") != expected_ru:
            mismatched_translations.append(
                f"{source}: expected '{expected_ru}', got '{term_map[source].get('ru')}'"
            )

    assert not missing_terms, f"Missing required canonical terms: {missing_terms}"
    assert not mismatched_translations, (
        f"Mismatched translations: {mismatched_translations}"
    )


def test_no_duplicate_source_terms() -> None:
    """Ensure no contradictory duplicate entries across the same category."""
    entries = _load_glossary()
    category_sources: dict[tuple[str, str], list[str]] = defaultdict(list)

    for entry in entries:
        cat = entry["category"].strip().lower()
        src = entry["source"].strip().lower()
        ru = entry["ru"].strip()
        category_sources[(cat, src)].append(ru)

    contradictions: dict[tuple[str, str], list[str]] = {
        key: translations
        for key, translations in category_sources.items()
        if len(set(translations)) > 1
    }
    assert not contradictions, (
        f"Contradictory duplicate entries found in same category: {contradictions}"
    )

    duplicates: dict[tuple[str, str], int] = {
        key: len(translations)
        for key, translations in category_sources.items()
        if len(translations) > 1
    }
    assert not duplicates, (
        f"Duplicate entries found in same category: {duplicates}"
    )
