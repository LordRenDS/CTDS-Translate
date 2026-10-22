"""Unit tests for the static script QA auditor tool."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_script_translations import (
    audit_script_directory,
    audit_script_entry,
    audit_script_file,
)
from src.cli import main


def test_detects_banned_terms() -> None:
    """Flags strings containing banned MT terms: техников, уровень владения, Медленно Увеличивает."""
    # 1. 'техников' referring to techs
    entry_tech = {"id": 1, "translation": "Использование техников запрещено в этой зоне."}
    v_tech = audit_script_entry(entry_tech)
    assert any("техников" in v.lower() for v in v_tech), f"Expected 'техников' violation, got: {v_tech}"

    # 2. 'уровень владения' referring to weapon proficiencies
    entry_prof = {"id": 2, "translation": "Ваш уровень владения оружием слишком мал."}
    v_prof = audit_script_entry(entry_prof)
    assert any("уровень владения" in v.lower() for v in v_prof), (
        f"Expected 'уровень владения' violation, got: {v_prof}"
    )

    # 3. 'Медленно Увеличивает' merged status pattern
    entry_slow = {"id": 3, "translation": "Медленно Увеличивает время ожидания между ударами."}
    v_slow = audit_script_entry(entry_slow)
    assert any("медленно увеличивает" in v.lower() for v in v_slow), (
        f"Expected 'Медленно Увеличивает' violation, got: {v_slow}"
    )

    # Clean text should have no banned term violations
    entry_clean = {
        "id": 4,
        "translation": "Изучение техник доступно. Типы оружия уникальны. Замедление снижает скорость.",
    }
    assert len(audit_script_entry(entry_clean)) == 0


def test_detects_choice_tag_violations() -> None:
    """Flags choice tags missing leading newline or containing internal newline."""
    # 1. Missing leading newline before choice opening tags
    entry_missing_nl = {
        "id": 1,
        "translation": "Что скажешь? {TAG:38}{TAG:38}{GLYPH:394}Да.{GLYPH:395} {TAG:38}{TAG:38}{GLYPH:396}Нет.{GLYPH:397}",
    }
    v_missing = audit_script_entry(entry_missing_nl)
    assert any("leading" in v.lower() or "missing leading" in v.lower() for v in v_missing), (
        f"Expected missing leading newline violation, got: {v_missing}"
    )

    # 2. Internal newline within a choice option block
    entry_internal_nl = {
        "id": 2,
        "translation": "Что сыграть?\n{TAG:38}{TAG:38}{GLYPH:394}Сыграй\nгрустное!{GLYPH:395}\n{TAG:38}{TAG:38}{GLYPH:396}Весёлое!{GLYPH:397}",
    }
    v_internal = audit_script_entry(entry_internal_nl)
    assert any("internal" in v.lower() for v in v_internal), (
        f"Expected internal newline violation, got: {v_internal}"
    )

    # Clean choice format: each option starts on a newline, no internal newlines
    entry_clean = {
        "id": 3,
        "translation": "Что сыграть?\n{TAG:38}{TAG:38}{GLYPH:394}Сыграй грустное!{GLYPH:395}\n{TAG:38}{TAG:38}{GLYPH:396}Что-нибудь весёлое!{GLYPH:397}",
    }
    assert len(audit_script_entry(entry_clean)) == 0


def test_detects_subpage_line_overflow() -> None:
    """Flags sub-pages between {WAIT_KEY} having > 3 lines for dialogue presets."""
    # 4 lines on first subpage (> 3 lines)
    entry_overflow = {
        "id": 1,
        "translation": "Строка 1\nСтрока 2\nСтрока 3\nСтрока 4{WAIT_KEY}Строка 5\nСтрока 6",
    }
    v_overflow = audit_script_entry(entry_overflow, preset="dialogue")
    assert any("sub-page" in v.lower() or "overflow" in v.lower() or "lines" in v.lower() for v in v_overflow), (
        f"Expected subpage overflow violation, got: {v_overflow}"
    )

    # 4 lines on second subpage (> 3 lines)
    entry_overflow_p2 = {
        "id": 2,
        "translation": "Строка 1\nСтрока 2{WAIT_KEY}Строка 3\nСтрока 4\nСтрока 5\nСтрока 6",
    }
    v_overflow_p2 = audit_script_entry(entry_overflow_p2, preset="dialogue")
    assert any("sub-page" in v.lower() or "overflow" in v.lower() or "lines" in v.lower() for v in v_overflow_p2), (
        f"Expected subpage overflow violation on page 2, got: {v_overflow_p2}"
    )

    # Clean dialogue subpages: exactly 3 lines or less per subpage
    entry_clean = {
        "id": 3,
        "translation": "Строка 1\nСтрока 2\nСтрока 3{WAIT_KEY}Строка 4\nСтрока 5",
    }
    assert len(audit_script_entry(entry_clean, preset="dialogue")) == 0


def test_detects_male_npc_female_verb_endings() -> None:
    """Flags feminine past-tense verbs (видела, сказала, пошла) in designated male speech blocks."""
    # 1. Designated male block by gender metadata
    entry_male_videla = {
        "id": 1,
        "translation": "Я никогда не видела такого прекрасного фестиваля!",
        "gender": "m",
    }
    v_videla = audit_script_entry(entry_male_videla)
    assert any("видела" in v.lower() for v in v_videla), f"Expected 'видела' gender violation, got: {v_videla}"

    entry_male_skazala = {
        "id": 2,
        "translation": "Я же тебе сказала, что это невозможно.",
        "gender": "m",
    }
    v_skazala = audit_script_entry(entry_male_skazala)
    assert any("сказала" in v.lower() for v in v_skazala), f"Expected 'сказала' gender violation, got: {v_skazala}"

    entry_male_poshla = {
        "id": 3,
        "translation": "Я сразу пошла на главную площадь ярмарки.",
        "gender": "m",
    }
    v_poshla = audit_script_entry(entry_male_poshla)
    assert any("пошла" in v.lower() for v in v_poshla), f"Expected 'пошла' gender violation, got: {v_poshla}"

    # 2. Designated male block by known file/ID mapping (cmes0.json #77 Truce Inn Patron)
    entry_patron = {
        "id": 77,
        "translation": "Невероятно, правда? Магазины, мероприятия — я никогда не видела такого фестиваля!",
    }
    v_patron = audit_script_entry(entry_patron, file_path="cmes0.json")
    assert any("видела" in v.lower() for v in v_patron), f"Expected 'видела' violation for patron #77, got: {v_patron}"

    # 3. Female speaker using feminine verb should NOT be flagged
    entry_female = {
        "id": 37,
        "translation": "Я никогда не видела, чтобы ты приводил девушек.",
        "gender": "f",
    }
    assert len(audit_script_entry(entry_female)) == 0

    # 4. Male speaker using masculine verb should NOT be flagged
    entry_male_ok = {
        "id": 77,
        "translation": "Невероятно, правда? Магазины, мероприятия — я никогда не видел такого фестиваля!",
        "gender": "m",
    }
    assert len(audit_script_entry(entry_male_ok)) == 0


def test_audit_script_file_and_directory(tmp_path: Path) -> None:
    """Verifies file-level and directory-level QA auditing and aggregation."""
    test_file = tmp_path / "test_dialogue.json"
    data = [
        {"id": 0, "translation": "Обычный диалог без ошибок."},
        {"id": 1, "translation": "Использование техников запрещено."},
        {"id": 2, "translation": "Строка 1\nСтрока 2\nСтрока 3\nСтрока 4"},
    ]
    test_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    file_result = audit_script_file(test_file, preset="dialogue")
    assert file_result["total_entries"] == 3
    assert file_result["violations_count"] == 2
    assert len(file_result["violations"]) == 2

    dir_result = audit_script_directory(tmp_path, preset="dialogue")
    assert dir_result["total_files"] == 1
    assert dir_result["scanned_entries"] == 3
    assert dir_result["total_violations"] == 2
    assert dir_result["files_with_violations"] == 1


def test_cli_audit_scripts_command(tmp_path: Path) -> None:
    """Verifies the audit-scripts subcommand integrated into src/cli.py."""
    clean_file = tmp_path / "clean.json"
    clean_file.write_text(
        json.dumps([{"id": 0, "translation": "Чистый текст диалога."}], ensure_ascii=False),
        encoding="utf-8",
    )

    bad_file = tmp_path / "bad.json"
    bad_file.write_text(
        json.dumps([{"id": 0, "translation": "Плохой перевод техников."}], ensure_ascii=False),
        encoding="utf-8",
    )

    # Clean file should exit 0
    exit_clean = main(["audit-scripts", "--file", str(clean_file)])
    assert exit_clean == 0

    # Bad file should exit 1
    exit_bad = main(["audit-scripts", "--file", str(bad_file)])
    assert exit_bad == 1


def test_detects_token_case_suffixes() -> None:
    """Flags dynamic hero/ship tokens with attached Russian case endings or apostrophes."""
    for bad in [
        "Изобретение {LUCCA}и уже готово.",
        "Прыжок на {EPOCH}е!",
        "Замок {MAGUS}'а возвышается на востоке.",
        "Камень в лапе {FROG}а!",
    ]:
        v = audit_script_entry({"id": 1, "translation": bad})
        assert any("token" in msg.lower() or "суффикс" in msg.lower() for msg in v), f"Failed to flag: {bad}"

    # Nominative token with punctuation or space should NOT be flagged
    for good in [
        "Изобретение создала {LUCCA}!",
        "Полёт на машине «{EPOCH}».",
        "Замок чародея {MAGUS} возвышается на востоке.",
    ]:
        assert len(audit_script_entry({"id": 1, "translation": good})) == 0


def test_detects_non_canonical_protagonist_and_racer_names() -> None:
    """Flags non-canonical 'Хроно' (except 'Хроно Триггер' and compounds) and non-canonical fair racer names."""
    # Non-canonical protagonist name should be flagged
    v_crono = audit_script_entry({"id": 1, "translation": "Воскрешение Хроно на Пике Смерти"})
    assert any("хроно" in msg.lower() for msg in v_crono), f"Expected 'Хроно' violation, got: {v_crono}"

    # Allowed 'Хроно Триггер' and compound words should NOT be flagged
    for allowed in [
        "Это Хроно Триггер",
        "Хроногироскоп работает",
        "Воскрешение Кроно на Пике Смерти",
    ]:
        assert len(audit_script_entry({"id": 2, "translation": allowed})) == 0, f"Unexpectedly flagged: {allowed}"

    # Non-canonical fair racer names should be flagged
    for bad_racer in [
        "Железный Бегун",
        "Кот-Спринтер",
        "Бравый Солдат",
        "Бегун-солдат",
        "Стальной бегун",
        "Зелёный тихоход",
    ]:
        v_racer = audit_script_entry({"id": 3, "translation": f"На старте {bad_racer}!"})
        assert any("racer" in msg.lower() or "бегун" in msg.lower() for msg in v_racer), (
            f"Failed to flag racer: {bad_racer}"
        )

    # Canonical fair racer names should NOT be flagged
    for canonical_racer in [
        "Стальной Бегун",
        "Зелёный Тихоход",
        "Каталак",
        "Бравый Бегун",
    ]:
        assert len(audit_script_entry({"id": 4, "translation": f"На старте {canonical_racer}!"})) == 0, (
            f"Unexpectedly flagged canonical racer: {canonical_racer}"
        )
