"""Comprehensive Script QA and Formatting Fixer for Chrono Trigger DS.

Fixes:
1. Punctuation missing spaces and Latin homoglyph typos (e.g. mesk1 #76).
2. Extra completion data labels in extra.json.
3. Syllable hyphenation breaks (e.g. 'ра-\\nзвитой' -> 'развитой') and re-wraps subpages cleanly.
4. Choice block formatting:
   - Strictly enforces the Mathematical Invariant of CTDS Choices:
     Target RU Prompt Lines == EN Prompt Lines (N_EN in {0, 1, 2}).
   - Strips internal newlines from choice options.
   - Normalizes choice prefixes to '\\n{TAG:38}{TAG:38}{GLYPH:...}'.
   - Re-wraps prompt to exactly N_EN lines (<= 238px each).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from src.text.metrics import calculate_line_width_px, load_glyph_metrics
from src.text.presets import get_constraints_for_entry
from src.text.reflow import wrap_line_to_width

SUBPAGE_SPLIT = re.compile(r"(\{WAIT_KEY\}|\{PAGE\}|\{GLYPH:407\}|\{GLYPH:408\})")
CHOICE_TAG_RE = re.compile(r"\{GLYPH:(394|396|398|400)\}")

# Special manual prompt shortenings for 1-line EN prompts where Russian originally exceeded 238px
MANUAL_1LINE_PROMPTS: dict[tuple[str, int], str] = {
    ("cmes0.json", 74): "Ночлег — 10 З. Желаете остаться?",
    ("cmes0.json", 78): "Слушай, не угостишь выпивкой за 10 З?",
    ("cmes2.json", 90): "{AYLA}: {GLYPH:392} сразиться с {AYLA}?",
    ("comu0.json", 1): "Смотритель: Рассказать обо всём?",
    ("comu0.json", 26): "Распорядитель: Какую битву выберете?",
    ("exms1.json", 250): "Отправиться на поиски Золотого молота?",
    ("exms1.json", 258): "Попробовать показать ей чудесный камень?",
    ("mest0.json", 132): "{LUCCA}: Неужто тебе не нужен мой гений?",
    ("mest2.json", 22): "{FROG}: {GLYPH:386}! Ты готов к этой битве?",
    ("mest2.json", 24): "{MAGUS}: Хм. Ты струсил?",
    ("mest3.json", 64): "{ROBO}: Что будем делать, {GLYPH:386}?",
    ("mest4.json", 40): "Вы ведь не вели себя... неподобающе?",
}

# Special manual choice options where original text was over 110px or had internal break
MANUAL_CHOICE_OPTIONS: dict[tuple[str, int, int], str] = {
    ("cmes1.json", 108, 394): "Режим 1: Турбо включено.",
    ("cmes1.json", 109, 394): "Режим 1: Турбо включено.",
    ("cmes3.json", 182, 394): "Сжечь из жалости.",
    ("comu0.json", 26, 396): "Битва эпох (Связь).",
    ("mest3.json", 64, 394): "Притвориться больным.",
    ("mest3.json", 64, 396): "Придумать иной план.",
    ("msg01.json", 189, 396): "Мне не нужна рухлядь.",
}


def clean_choice_opt_text(text: str) -> str:
    """Cleans internal newlines and excess whitespace from choice option text."""
    # Replace internal newlines with space
    t = text.replace("\r", " ").replace("\n", " ").replace("{LINE}", " ")
    # Normalize multiple spaces, but preserve tags
    return " ".join(t.split())


def fix_choice_subpage(
    ru_subpage: str,
    en_subpage: str,
    file_name: str,
    entry_id: int,
    metrics: Any,
) -> str:
    """Formats a choice subpage according to the Mathematical Invariant of CTDS Choices."""
    if "{GLYPH:394}" not in ru_subpage and "{GLYPH:394}" not in en_subpage:
        return ru_subpage

    # 1. Parse EN prompt line count
    en_prompt_lines = 0
    if "{GLYPH:394}" in en_subpage:
        en_idx = en_subpage.find("{GLYPH:394}")
        en_pre = en_subpage[:en_idx]
        en_pre = re.sub(r"(\{TAG:38\}|®|\s)+$", "", en_pre)
        en_lines = [l for l in en_pre.split("\n") if l.strip()]
        en_prompt_lines = len(en_lines)

    # 2. Extract Russian prompt and choices
    # Find all choice segments in RU
    choices_pattern = re.compile(
        r"(?:(?:\{TAG:38\}|®|\s)*)\{GLYPH:(394|396|398|400)\}(.*?)\{GLYPH:(395|397|399|401)\}",
        re.DOTALL,
    )

    ru_choices: list[tuple[int, str]] = []
    first_choice_pos = len(ru_subpage)
    for m in choices_pattern.finditer(ru_subpage):
        if m.start() < first_choice_pos:
            first_choice_pos = m.start()
        tag_num = int(m.group(1))
        opt_text = m.group(2)
        ru_choices.append((tag_num, opt_text))

    if not ru_choices:
        return ru_subpage

    ru_pre = ru_subpage[:first_choice_pos]
    ru_pre = re.sub(r"(\{TAG:38\}|®|\s)+$", "", ru_pre)

    # 3. Format RU Prompt
    formatted_prompt_lines: list[str] = []
    key = (file_name, entry_id)
    if key in MANUAL_1LINE_PROMPTS:
        formatted_prompt_lines = [MANUAL_1LINE_PROMPTS[key]]
    elif en_prompt_lines == 0:
        formatted_prompt_lines = []
    elif en_prompt_lines == 1:
        # Wrap to single line
        single_l = " ".join(ru_pre.replace("\n", " ").split())
        formatted_prompt_lines = [single_l]
    elif en_prompt_lines == 2:
        # Wrap to 2 lines
        single_l = " ".join(ru_pre.replace("\n", " ").split())
        wl = wrap_line_to_width(single_l, metrics, max_width_px=238)
        if len(wl) > 2:
            # Rebalance into 2 lines if possible
            mid = len(single_l) // 2
            split_idx = single_l.rfind(" ", 0, mid + 15)
            if split_idx != -1:
                l1 = single_l[:split_idx].strip()
                l2 = single_l[split_idx:].strip()
                formatted_prompt_lines = [l1, l2]
            else:
                formatted_prompt_lines = wl[:2]
        elif len(wl) == 1:
            # In English it was 2 lines; split cleanly into 2 lines
            words = single_l.split()
            if len(words) >= 4:
                half = len(words) // 2
                formatted_prompt_lines = [" ".join(words[:half]), " ".join(words[half:])]
            else:
                formatted_prompt_lines = [single_l]
        else:
            formatted_prompt_lines = wl
    else:
        # 3 or more lines
        single_l = " ".join(ru_pre.replace("\n", " ").split())
        formatted_prompt_lines = wrap_line_to_width(single_l, metrics, max_width_px=238)

    # 4. Format choices
    formatted_choices: list[str] = []
    for tag_num, raw_opt in ru_choices:
        close_tag = tag_num + 1
        opt_key = (file_name, entry_id, tag_num)
        if opt_key in MANUAL_CHOICE_OPTIONS:
            opt_clean = MANUAL_CHOICE_OPTIONS[opt_key]
        else:
            opt_clean = clean_choice_opt_text(raw_opt)
        formatted_choices.append(f"{{TAG:38}}{{TAG:38}}{{GLYPH:{tag_num}}}{opt_clean}{{GLYPH:{close_tag}}}")

    # 5. Assemble subpage
    if not formatted_prompt_lines:
        return "\n".join(formatted_choices)
    else:
        prompt_str = "\n".join(formatted_prompt_lines)
        return prompt_str + "\n" + "\n".join(formatted_choices)


def fix_syllable_hyphenation(text: str, max_width_px: int, metrics: Any) -> str:
    """Removes awkward syllable hyphens at line ends and re-wraps subpages."""
    # Check if text contains non-compound syllable hyphens like 'ра-\nзвитой'
    compound_tails = {"то", "нибудь", "либо", "таки", "ка"}
    compound_heads = {"из", "по", "кое"}

    def _unhyphen(match: re.Match[str]) -> str:
        w1 = match.group(1)
        w2 = match.group(2)
        if w2.lower() in compound_tails or w1.lower() in compound_heads:
            return f"{w1}-\n{w2}"
        return f"{w1}{w2}"

    unhyphened = re.sub(r"([а-яА-ЯёЁ]+)-\n([а-яА-ЯёЁ]+)", _unhyphen, text)
    if unhyphened == text:
        return text

    # Re-wrap each subpage if not a choice subpage
    parts = SUBPAGE_SPLIT.split(unhyphened)
    new_parts: list[str] = []
    for sp in parts:
        if SUBPAGE_SPLIT.fullmatch(sp):
            new_parts.append(sp)
            continue
        if "{GLYPH:394}" in sp:
            new_parts.append(sp)
            continue
        # Normal dialogue subpage: unwrap lines and re-wrap to max_width_px
        lines = [l for l in sp.strip("\r\n").split("\n")]
        wrapped_lines: list[str] = []
        # Join words
        subpage_text = " ".join(" ".join(lines).split())
        wl = wrap_line_to_width(subpage_text, metrics, max_width_px=max_width_px)
        new_parts.append("\n".join(wl))

    return "".join(new_parts)


def process_entry(
    file_name: str,
    entry_id: int,
    item: dict[str, Any],
    metrics: Any,
) -> bool:
    """Processes and fixes a single translation entry."""
    trans = item.get("translation") or item.get("ru") or ""
    orig = item.get("original_en") or item.get("en") or ""
    if not trans.strip():
        return False

    old_trans = trans

    # 1. Specific typos & punct fixes
    if file_name == "mesk1.json" and entry_id == 76:
        trans = (
            "Повторяйте движения!\n"
            "Кнопка L: Левая рука{TAG:38}{TAG:38}®Кнопка R: Правая рука\n"
            "Кнопка Y: Смех{TAG:38}{TAG:38}{TAG:38}{TAG:38}Кнопка A: Испуг"
        )
    if file_name == "cmes0.json" and entry_id == 123:
        trans = trans.replace("делу.Пожалуйста", "делу. Пожалуйста")
    if file_name == "cmes0.json" and entry_id == 141:
        trans = trans.replace("Зенан.Мы", "Зенан. Мы")

    # 2. Extra.json labels
    if file_name == "extra.json":
        if entry_id == 2:
            trans = "ИТОГИ ПРОХОЖДЕНИЯ"
        elif entry_id == 3:
            trans = "Встреченные враги:"
        elif entry_id == 4:
            trans = "Собрано предметов:"
        elif entry_id == 6:
            trans = "Число сохранений:"

    # 3. Choice formatting
    if "{GLYPH:394}" in trans or "{GLYPH:394}" in orig:
        # Split by subpage delimiters
        orig_sps = SUBPAGE_SPLIT.split(orig)
        trans_sps = SUBPAGE_SPLIT.split(trans)

        new_trans_sps: list[str] = []
        for i, tsp in enumerate(trans_sps):
            if SUBPAGE_SPLIT.fullmatch(tsp):
                new_trans_sps.append(tsp)
                continue
            osp = orig_sps[i] if i < len(orig_sps) else ""
            fixed_sp = fix_choice_subpage(tsp, osp, file_name, entry_id, metrics)
            new_trans_sps.append(fixed_sp)
        trans = "".join(new_trans_sps)

    # 4. Syllable hyphenation (in dialogue files, except quest/items with intentional hyphens)
    if file_name.startswith(("cmes", "kmes", "mesi", "mesk", "mess", "mest", "msg", "exms", "comu")):
        constraints = get_constraints_for_entry(file_name, entry_id=entry_id, entry_dict=item)
        trans = fix_syllable_hyphenation(trans, constraints.max_width_px, metrics)

    if trans != old_trans:
        item["translation"] = trans
        return True
    return False


def main() -> int:
    font_json = Path("extracted fonts/msg/big/msgcmn.json")
    cyrillic_json = Path("assets/fonts/cyrillic_big.json")
    metrics = load_glyph_metrics(font_json, cyrillic_json) if font_json.exists() else None

    target_dirs = [Path("ai translated text")]
    total_modified = 0

    for d in target_dirs:
        for json_path in sorted(d.glob("**/*.json")):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            file_modified = False
            for idx, item in enumerate(data):
                if process_entry(json_path.name, idx, item, metrics):
                    file_modified = True
                    total_modified += 1

            if file_modified:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"Updated {json_path}")

    print(f"\nDone! Modified {total_modified} entries across target files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
