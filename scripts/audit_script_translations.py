"""Static script QA auditor for Chrono Trigger DS translation files.

Audits dialogue and UI translation JSON files across the repository to detect:
1. Choice formatting violations: missing leading newline or internal newlines within choice options.
2. Sub-page line overflows: sub-pages between {WAIT_KEY} / {PAGE} exceeding line limits (>3 for dialogue).
3. Forbidden MT patterns: техников (referring to techs), уровень владения (referring to proficiencies),
   and merged status effects like Медленно Увеличивает.
4. NPC gender mismatches: feminine past-tense verbs in designated male speech blocks.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from src.text.metrics import load_glyph_metrics
from src.text.presets import WINDOW_PRESETS, TextWindowPreset, get_constraints_for_entry
from src.text.reflow import wrap_line_to_width

__all__ = [
    "BANNED_PATTERNS",
    "FEMININE_PAST_VERBS",
    "HANGING_PUNCT_START",
    "KNOWN_MALE_BLOCKS",
    "KNOWN_MALE_SPEAKERS",
    "audit_script_directory",
    "audit_script_entry",
    "audit_script_file",
    "main",
]

# 1. Banned translation patterns and machine translation artifacts
BANNED_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bтехников\b", re.IGNORECASE),
        "banned term 'техников' found in translation (referring to techs; use 'техник')",
    ),
    (
        re.compile(r"уровень\s+владения", re.IGNORECASE),
        "banned MT term 'уровень владения' found in translation (referring to weapon types; use 'типы оружия' or 'специализация')",
    ),
    (
        re.compile(r"Медленно\s+Увеличивает", re.IGNORECASE),
        "banned merged status pattern 'Медленно Увеличивает' found in translation (use 'Замедление')",
    ),
    (
        re.compile(r"\{(?:CRONO|MARLE|LUCCA|ROBO|FROG|AYLA|MAGUS|EPOCH)\}['’`-]?[а-яёА-ЯЁa-zA-Z]+"),
        "dynamic token has attached case ending/suffix (rephrase sentence so token stands in Nominative case)",
    ),
    (
        re.compile(
            r"\b(?:Железный\s+Бегун|Кот-Спринтер|Бравый\s+Солдат|Бравого\s+Солдата|Бегун-солдат|Стальной\s+бегун|Зелёный\s+тихоход)\b"
        ),
        "non-canonical Millennial Fair racer name found (use Стальной Бегун, Зелёный Тихоход, Каталак, Бравый Бегун)",
    ),
    (
        re.compile(r"\bХроно\b(?!\s*Триггер)"),
        "non-canonical protagonist name 'Хроно' found (use 'Кроно'; only 'Хроно Триггер' is allowed with Х)",
    ),
    (
        re.compile(r"\bГейтс\b", re.IGNORECASE),
        "banned transliteration 'Гейтс' found (referring to Gates; use 'Врата' or 'Вратами')",
    ),
    (
        re.compile(r"\bв\s+(?:этой|эту)\s+зал[еу]?\b", re.IGNORECASE),
        "incorrect gender form 'в этой зале/залу' found (use 'в этом зале' or 'в этой комнате')",
    ),
    (
        re.compile(r"\bВпрочем,\s+пустое\b", re.IGNORECASE),
        "stilted translation 'Впрочем, пустое' found (use 'Впрочем, не будем об этом' or 'Ну да неважно')",
    ),
)

# 2. Choice tag pairs and regexes
CHOICE_OPEN_TAGS: re.Pattern[str] = re.compile(r"\{GLYPH:(394|396|398|400)\}")
CHOICE_PAIRS: tuple[tuple[int, int], ...] = (
    (394, 395),
    (396, 397),
    (398, 399),
    (400, 401),
)
CHOICE_PAIR_PATTERNS: tuple[tuple[int, re.Pattern[str]], ...] = tuple(
    (open_id, re.compile(rf"\{{GLYPH:{open_id}\}}(.*?)\{{GLYPH:{close_id}\}}", re.DOTALL))
    for open_id, close_id in CHOICE_PAIRS
)
PREC_STRIP_REGEX: re.Pattern[str] = re.compile(r"(?:\{TAG:38\}|®|[ \t])+$")

# 3. Sub-page boundary split pattern
SUBPAGE_SPLIT: re.Pattern[str] = re.compile(r"\{WAIT_KEY\}|\{PAGE\}|\{GLYPH:407\}|\{GLYPH:408\}")

# 4. Russian feminine past-tense verbs commonly misattributed in MT dialogue
FEMININE_PAST_VERBS: re.Pattern[str] = re.compile(
    r"\b(видела|сказала|пошла|думала|хотела|забыла|слышала|решила|пришла|смогла|знала|нашла|была|ждала|поняла|взяла|отдала|просила|спросила)\b",
    re.IGNORECASE,
)

# 5. Designated male speech blocks and character names
KNOWN_MALE_BLOCKS: set[tuple[str, int]] = {
    ("cmes0.json", 77),
    ("cmes0", 77),
}

KNOWN_MALE_SPEAKERS: frozenset[str] = frozenset({
    "Truce Inn Patron",
    "Посетитель таверны Труса",
    "Crono",
    "Кроно",
    "Glenn",
    "Гленн",
    "Frog",
    "Фрог",
    "Robo",
    "Робо",
    "Prometheus",
    "Прометей",
    "Magus",
    "Магус",
    "Janus",
    "Янус",
    "Dalton",
    "Дальтон",
    "Gaspar",
    "Гаспар",
    "Belthasar",
    "Бельтазар",
    "Melchior",
    "Мельхиор",
    "Taban",
    "Табан",
    "Kino",
    "Кино",
    "Cyrus",
    "Сайрус",
    "Ozzie",
    "Оззи",
    "Slash",
    "Слэш",
    "Flea",
    "Фли",
    "Lavos",
    "Лавос",
})


# 6. Hanging punctuation starting a line
HANGING_PUNCT_START: re.Pattern[str] = re.compile(
    r"(?:\r?\n|\{LINE\})[ \t]*([?!»\),;:]{1,3}|\.{2,3})(?=[ \t\wа-яА-ЯёЁ]|$)"
)


def _is_legitimate_ellipsis(text: str, match: re.Match[str]) -> bool:
    """Checks whether a line-starting punctuation mark is a legitimate hesitation ellipsis."""
    punct = match.group(1)
    if punct not in ("...", "…"):
        return False
    preceding = text[: match.start()].rstrip(" \t")
    if preceding.endswith(("-", "—", "–")):
        return False
    after = text[match.end() :].lstrip(" \t")
    if not after or after.startswith(("\r", "\n", "{WAIT_KEY}", "{PAGE}", "{LINE}")):
        return True
    if not preceding or preceding.endswith((".", "!", "?", "…", ":", "»", '"', "'", ">", "}")):
        return True
    if after and (after[0].isupper() or after[0] in ("«", "—")):
        return True
    return False


def audit_script_entry(
    entry: dict[str, Any],
    file_path: str | Path = "",
    glyph_widths: dict[str, int] | None = None,
    preset: str | None = None,
    field: str = "translation",
) -> list[str]:
    """Audits a single translation entry for static QA violations.

    Args:
        entry: Dictionary containing text entry fields (e.g. 'id', 'translation').
        file_path: Optional path or filename for context and preset resolution.
        glyph_widths: Optional character width table for pixel wrap simulation.
        preset: Optional explicit window preset override (default "auto").
        field: Name of string field to validate (default "translation").

    Returns:
        List of human-readable violation descriptions.
    """
    text = entry.get(field)
    if not text or not isinstance(text, str):
        return []

    violations: list[str] = []

    # Check 1: Banned translation patterns and MT artifacts
    for pattern, desc in BANNED_PATTERNS:
        if pattern.search(text):
            violations.append(desc)

    # Check 2: Choice tag formatting violations
    # 2a. Choice opening tags missing leading newline
    for m in CHOICE_OPEN_TAGS.finditer(text):
        tag = m.group(0)
        preceding = text[: m.start()]
        prec_stripped = PREC_STRIP_REGEX.sub("", preceding)
        if prec_stripped and not prec_stripped.endswith(
            ("\n", "\r", "{WAIT_KEY}", "{PAGE}", "{GLYPH:407}", "{GLYPH:408}")
        ):
            violations.append(
                f"Choice tag {tag} is missing leading newline (must start on a new line with \\n)"
            )

    # 2b. Internal newlines within choice option blocks
    for open_id, pair_pat in CHOICE_PAIR_PATTERNS:
        for pm in pair_pat.finditer(text):
            inner = pm.group(1)
            if "\n" in inner or "\r" in inner or "{LINE}" in inner:
                violations.append(
                    f"Choice option {{GLYPH:{open_id}}} contains internal newline: '{inner.strip()}'"
                )

    # Resolve preset constraints for sub-page line limit checks
    entry_id = entry.get("id")
    effective_preset: TextWindowPreset
    if file_path:
        effective_preset = get_constraints_for_entry(
            str(file_path),
            entry_id=entry_id if isinstance(entry_id, int) else 0,
            explicit_preset=preset,
            entry_dict=entry,
        )
    else:
        preset_key = preset if preset and preset != "auto" else "dialogue"
        effective_preset = WINDOW_PRESETS.get(preset_key, WINDOW_PRESETS["dialogue"])

    max_lines = effective_preset.max_lines

    # Check 3: Sub-page line overflows between {WAIT_KEY} / {PAGE}
    subpages = SUBPAGE_SPLIT.split(text)
    for idx, sp in enumerate(subpages):
        sp_clean = sp.strip("\r\n")
        if not sp_clean.strip():
            continue
        raw_lines = sp_clean.split("\n")
        if glyph_widths:
            wrapped_count = 0
            for rl in raw_lines:
                if rl.strip():
                    wl = wrap_line_to_width(
                        rl,
                        glyph_widths,
                        max_width_px=effective_preset.max_width_px,
                    )
                    wrapped_count += max(1, len(wl))
                else:
                    wrapped_count += 1
            line_count = max(len(raw_lines), wrapped_count)
        else:
            line_count = len(raw_lines)

        subpage_max_lines = (
            4
            if CHOICE_OPEN_TAGS.search(sp)
            and effective_preset.name.startswith(("dialogue", "status_tutorial"))
            else max_lines
        )
        if line_count > subpage_max_lines:
            violations.append(
                f"Sub-page line overflow: Sub-page {idx + 1} has {line_count} lines (max allowed: {subpage_max_lines})"
            )

    # Check 4: NPC Gender Mismatches (feminine past-tense verbs in male speech blocks)
    is_male = False
    gender_attr = entry.get("gender") or entry.get("speaker_gender")
    if gender_attr:
        is_male = str(gender_attr).strip().lower() in ("m", "male", "муж", "м")
    else:
        if entry_id is not None and file_path:
            f_name = Path(file_path).name.lower()
            f_stem = Path(file_path).stem.lower()
            if (f_name, entry_id) in KNOWN_MALE_BLOCKS or (f_stem, entry_id) in KNOWN_MALE_BLOCKS:
                is_male = True
        speaker = entry.get("speaker")
        if speaker and speaker in KNOWN_MALE_SPEAKERS:
            is_male = True

    if is_male:
        for fm in FEMININE_PAST_VERBS.finditer(text):
            verb = fm.group(0)
            violations.append(
                f"Gender mismatch: Designated male speech block contains feminine verb '{verb}'"
            )

    # Check 5: Hanging punctuation starting a line
    for hm in HANGING_PUNCT_START.finditer(text):
        punct = hm.group(1)
        if not _is_legitimate_ellipsis(text, hm):
            violations.append(f"Line starts with hanging punctuation: '{punct}'")

    # Check 6: Choice prompt line count parity against original English
    orig_en = entry.get("original_en")
    if orig_en and isinstance(orig_en, str) and orig_en.strip() and field != "original_en":
        has_choice_ru = bool(CHOICE_OPEN_TAGS.search(text))
        has_choice_en = bool(CHOICE_OPEN_TAGS.search(orig_en))
        if has_choice_ru or has_choice_en:
            subpages_ru = [sp for sp in SUBPAGE_SPLIT.split(text) if CHOICE_OPEN_TAGS.search(sp)]
            subpages_en = [sp for sp in SUBPAGE_SPLIT.split(orig_en) if CHOICE_OPEN_TAGS.search(sp)]

            sp_ru = subpages_ru[0] if subpages_ru else ""
            sp_en = subpages_en[0] if subpages_en else ""

            m_ru = CHOICE_OPEN_TAGS.search(sp_ru)
            m_en = CHOICE_OPEN_TAGS.search(sp_en)

            prompt_ru = sp_ru[: m_ru.start()] if m_ru else sp_ru
            prompt_en = sp_en[: m_en.start()] if m_en else sp_en

            prompt_ru_clean = re.sub(r"(?:\{TAG:38\}|®|[ \t\r\n])+$", "", prompt_ru)
            prompt_en_clean = re.sub(r"(?:\{TAG:38\}|®|[ \t\r\n])+$", "", prompt_en)

            lines_ru = [l for l in prompt_ru_clean.split("\n") if l.strip()]
            lines_en = [l for l in prompt_en_clean.split("\n") if l.strip()]

            n_ru = len(lines_ru)
            n_en = len(lines_en)

            if n_ru != n_en:
                violations.append(
                    f"Choice prompt line count mismatch: EN={n_en} lines vs RU={n_ru} lines (causes hardware choice cursor misalignment)"
                )

    return violations


def audit_script_file(
    file_path: str | Path,
    glyph_widths: dict[str, int] | None = None,
    preset: str | None = None,
    field: str = "translation",
) -> dict[str, Any]:
    """Audits all entries in a single translation JSON file.

    Args:
        file_path: Path to the JSON file to inspect.
        glyph_widths: Optional character width table.
        preset: Optional window preset override.
        field: JSON string field to validate (default "translation").

    Returns:
        Dictionary with keys 'file_path', 'total_entries', 'violations_count', and 'violations'.
    """
    path_obj = Path(file_path)
    with open(path_obj, encoding="utf-8") as f:
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

    file_violations: list[str] = []
    total_entries = len(entries)

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id", i)
        entry_violations = audit_script_entry(
            entry=entry,
            file_path=path_obj,
            glyph_widths=glyph_widths,
            preset=preset,
            field=field,
        )
        for ev in entry_violations:
            file_violations.append(f"[{path_obj.name} #{entry_id}] {ev}")

    return {
        "file_path": str(path_obj),
        "total_entries": total_entries,
        "violations_count": len(file_violations),
        "violations": file_violations,
    }


def audit_script_directory(
    dir_path: str | Path,
    glyph_widths: dict[str, int] | None = None,
    preset: str | None = None,
    field: str = "translation",
    verbose: bool = False,
) -> dict[str, Any]:
    """Audits all translation JSON files located within a directory recursively.

    Args:
        dir_path: Path to the directory containing JSON translation files.
        glyph_widths: Optional character width table.
        preset: Optional window preset override.
        field: JSON string field to validate.
        verbose: If True, prints progress details during scanning.

    Returns:
        Summary dictionary with aggregated statistics and violation log.
    """
    root_path = Path(dir_path)
    json_files = sorted(root_path.rglob("*.json"))

    total_files = 0
    total_entries = 0
    all_violations: list[str] = []
    files_with_violations = 0

    for jf in json_files:
        res = audit_script_file(
            file_path=jf,
            glyph_widths=glyph_widths,
            preset=preset,
            field=field,
        )
        total_files += 1
        total_entries += res["total_entries"]
        if res["violations_count"] > 0:
            files_with_violations += 1
            all_violations.extend(res["violations"])
            if verbose:
                print(f"  [FAIL] {jf.name}: {res['violations_count']} violations")
        elif verbose:
            print(f"  [OK]   {jf.name}")

    return {
        "total_files": total_files,
        "scanned_entries": total_entries,
        "total_violations": len(all_violations),
        "files_with_violations": files_with_violations,
        "violations": all_violations,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for scripts/audit_script_translations.py.

    Args:
        argv: Command-line arguments. If None, sys.argv[1:] is used.

    Returns:
        Exit code: 0 if no violations found, 1 if violations exist or an error occurred.
    """
    if hasattr(sys.stdout, "reconfigure"):
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        with contextlib.suppress(Exception):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="audit_script_translations",
        description="Static Script QA Auditor for Chrono Trigger DS Translations",
    )
    parser.add_argument(
        "--json-dir",
        action="append",
        default=None,
        help="Directory containing JSON files to audit (can be specified multiple times)",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="Path to a single JSON file to audit",
    )
    parser.add_argument(
        "--preset",
        default="auto",
        help="Window preset name or 'auto' (default: 'auto')",
    )
    parser.add_argument(
        "--field",
        default="translation",
        help="JSON field to validate (default: 'translation')",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Print detailed progress and all violations",
    )
    parser.add_argument(
        "--font-json",
        default="extracted fonts/msg/big/msgcmn.json",
        help="Path to base font metrics JSON",
    )
    parser.add_argument(
        "--cyrillic-json",
        default="assets/fonts/cyrillic_big.json",
        help="Path to Cyrillic font metrics JSON",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    # Load metrics if available
    widths = None
    font_path = getattr(args, "font_json", None) or "extracted fonts/msg/big/msgcmn.json"
    cyr_path = getattr(args, "cyrillic_json", None) or "assets/fonts/cyrillic_big.json"
    if os.path.isfile(font_path):
        try:
            widths = load_glyph_metrics(
                font_path,
                cyr_path if os.path.isfile(cyr_path) else None,
            )
        except Exception:
            widths = None

    if args.file:
        if not os.path.isfile(args.file):
            print(f"Error: JSON file not found: {args.file}")
            return 1
        res = audit_script_file(
            file_path=args.file,
            glyph_widths=widths,
            preset=args.preset,
            field=args.field,
        )
        print(f"=== Script QA Audit Report: {args.file} ===")
        print(f"Total entries: {res['total_entries']}")
        print(f"Violations found: {res['violations_count']}")
        if res["violations"]:
            print("\nViolations:")
            for v in res["violations"]:
                print(f"  - {v}")
            return 1
        return 0

    json_dirs = args.json_dir or ["translated text"]
    total_files = 0
    total_entries = 0
    total_violations = 0
    all_violations: list[str] = []

    for d in json_dirs:
        if not os.path.isdir(d):
            print(f"Warning: Directory not found, skipping: {d}")
            continue
        res = audit_script_directory(
            dir_path=d,
            glyph_widths=widths,
            preset=args.preset,
            field=args.field,
            verbose=args.verbose,
        )
        total_files += res["total_files"]
        total_entries += res["scanned_entries"]
        total_violations += res["total_violations"]
        all_violations.extend(res["violations"])

    print("=== Script QA Audit Summary ===")
    print(f"Scanned {total_files} files, {total_entries} entries.")
    print(f"Total violations found: {total_violations}")
    if all_violations:
        print("\nViolations detected:")
        display_limit = len(all_violations) if args.verbose else min(50, len(all_violations))
        for v in all_violations[:display_limit]:
            print(f"  - {v}")
        if len(all_violations) > display_limit:
            print(
                f"  ... and {len(all_violations) - display_limit} more violations (use --verbose to see all)."
            )
        return 1

    print("SUCCESS: 0 QA violations detected across all checked files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
