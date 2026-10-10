"""Word wrapping, hyphenation carry, line break reflowing, and dialogue pagination."""

from __future__ import annotations

import re

from src.text.metrics import (
    DEFAULT_HERO_NAME_WIDTH_PX,
    DEFAULT_SPACE_WIDTH_PX,
    TAG_REGEX,
    calculate_line_width_px,
)

__all__ = [
    "CHOICE_MAX_WIDTH_PX",
    "CHOICE_TAG_PATTERN",
    "COMPOUND_KA_PREFIXES",
    "COMPOUND_TO_PREFIXES",
    "HYPHEN_BREAK_PATTERN",
    "LATIN_VOWELS",
    "PAGE_DELIM_PATTERN",
    "RUS_CONSONANTS",
    "RUS_VOWELS",
    "collapse_hyphenated_breaks",
    "split_word_carry",
    "wrap_line_to_width",
    "wrap_text_block",
]

RUS_VOWELS = frozenset("аеёиоуыэюяАЕЁИОУЫЭЮЯ")
RUS_CONSONANTS = frozenset("бвгджзйклмнпрстфхцчшщБВГДЖЗЙКЛМНПРСТФХЦЧШЩ")
LATIN_VOWELS = frozenset("aeiouyAEIOUY")

HYPHEN_BREAK_PATTERN = re.compile(
    r"([a-zA-Zа-яА-ЯёЁ]+)-\s*(?:\r?\n|\{LINE\}|\{PAGE\})\s*(?:(?:\r?\n|\{LINE\}|\{PAGE\})\s*)*([a-zA-Zа-яА-ЯёЁ]+)"
)

PAGE_DELIM_PATTERN = re.compile(r"(\{PAGE\}|\{WAIT_KEY\}|\{GLYPH:407\}|\{GLYPH:408\})")
CHOICE_TAG_PATTERN = re.compile(r"\{GLYPH:(39[4-9]|40[0-3])\}")
CHOICE_MAX_WIDTH_PX = 110

COMPOUND_TO_PREFIXES = frozenset({
    "что", "кто", "где", "как", "куда", "когда", "почему", "зачем", "откуда",
    "отчего", "сколько",
    "кого", "кому", "кем", "ком", "чего", "чему", "чем",
    "какой", "какая", "какое", "какие", "каком", "какому", "каким", "каких", "какую", "какими",
    "чей", "чья", "чье", "чьё", "чьи", "чьего", "чьей", "чьих", "чьим", "чьими", "чьем", "чьём",
    "так", "все", "всё", "он", "она", "оно", "они", "я", "ты", "мы", "вы",
    "тут", "там", "тот", "та", "те", "то", "опять", "прямо", "да", "уж", "мало",
})

COMPOUND_KA_PREFIXES = frozenset({
    "ну", "на", "давай", "давайте", "дай", "дайте", "гляди", "глянь", "гляньте",
    "смотри", "смотрите", "поди", "постой", "постойте", "подожди", "подождите",
    "слушай", "слушайте", "скажи", "скажите", "покажи", "покажите", "знай",
    "думай", "думайте", "попробуй", "попробуйте", "пойдем", "пойдемте", "посмотрим",
    "погоди", "погодите",
})


def _is_genuine_compound(prefix: str, remainder: str) -> bool:
    """Checks whether a hyphenated pair forms a genuine compound word in Russian."""
    p_lower = prefix.lower()
    r_lower = remainder.lower()

    # Suffixes: {"то", "либо", "нибудь", "ка", "де", "с"}
    if r_lower in {"либо", "нибудь"}:
        return True

    if r_lower == "то" and (
        p_lower in COMPOUND_TO_PREFIXES
        or any(p_lower.endswith("-" + x) for x in COMPOUND_TO_PREFIXES)
    ):
        return True

    if r_lower == "ка" and p_lower in COMPOUND_KA_PREFIXES:
        return True

    if r_lower == "де" and p_lower in {
        "он", "она", "оно", "они", "я", "ты", "мы", "вы", "мол", "говорит", "сказал"
    }:
        return True

    if r_lower == "с" and p_lower in {
        "да", "нет", "извольте", "слушаю", "сударь", "помилуйте"
    }:
        return True

    # Prefixes: {"из", "кое", "по", "во", "в"} (when appropriate)
    if p_lower == "из" and r_lower in {"за", "под", "над"}:
        return True

    if p_lower in {"кое", "кой"}:
        return True

    if p_lower == "по":
        if (
            r_lower.endswith(("ому", "ему", "ски", "цки", "ьи", "ыни"))
            or r_lower in {"латыни", "памяти", "пустому"}
        ):
            return True

    if p_lower == "во" and r_lower in {"первых", "вторых"}:
        return True

    if p_lower == "в" and r_lower in {
        "третьих", "четвертых", "пятых", "шестых", "седьмых", "восьмых", "девятых", "десятых"
    }:
        return True

    return False


def split_word_carry(
    word: str,
    available_width_px: int,
    glyph_widths: dict[str, int],
    mode: str = "geo",
) -> tuple[str, str] | None:
    """Splits a word for hyphenation/carry at the end of a line.

    Args:
        word: Word to split (must not contain control tokens or placeholders).
        available_width_px: Remaining pixel width available on current line.
        glyph_widths: Proportional font widths dictionary.
        mode: 'geo' (greedy geometric split) or 'syllable' (Russian syllable rules).

    Returns:
        Tuple (prefix_with_hyphen, remainder) or None if word cannot be split.
    """
    if TAG_REGEX.search(word):
        return None

    clean_word = re.sub(r"[^\w]", "", word)
    if len(clean_word) < 4 or len(word) < 4:
        return None

    has_rus_vowels = any(c in RUS_VOWELS for c in word)
    vowels = RUS_VOWELS if has_rus_vowels else LATIN_VOWELS

    # Greedily search from longest valid prefix down to minimum 2 chars
    for k in range(len(word) - 2, 1, -1):
        prefix = word[:k]
        remainder = word[k:]

        cand = prefix if prefix.endswith("-") else f"{prefix}-"
        cand_width = calculate_line_width_px(cand, glyph_widths)
        if cand_width > available_width_px:
            continue

        if mode == "geo":
            return (cand, remainder)

        if mode == "syllable":
            # Both parts must contain at least one vowel
            if not any(c in vowels for c in prefix):
                continue
            if not any(c in vowels for c in remainder):
                continue

            # Do not detach ь, ъ, й (they stay with preceding part)
            if remainder[0] in "ьъйЬЪЙ":
                continue

            # In Russian, do not detach a consonant from its following vowel (e.g. маль-чик, not мальч-ик; мо-локо, not мол-око)
            if (
                remainder[0].lower() in vowels
                and prefix[-1].lower() in RUS_CONSONANTS
            ):
                continue

            # Indivisible double consonants between vowels:
            # Do not split before double consonants (e.g. ва-нна)
            if (
                k < len(word) - 1
                and word[k].lower() == word[k + 1].lower()
                and word[k].lower() in RUS_CONSONANTS
                and word[k - 1].lower() in RUS_VOWELS
            ):
                continue

            # Do not split after double consonants (e.g. ванн-ый)
            if (
                k >= 2
                and word[k - 2].lower() == word[k - 1].lower()
                and word[k - 1].lower() in RUS_CONSONANTS
                and word[k].lower() in RUS_VOWELS
            ):
                continue

            return (cand, remainder)

    return None


def collapse_hyphenated_breaks(text: str) -> str:
    """Collapses hyphenated line and page breaks back into whole words or compound words.

    Distinguishes genuine hyphenated compounds (e.g., 'что-то', 'из-за', 'где-нибудь',
    'по-моему', 'во-первых') from soft hyphens introduced by word carry / hyphenation
    (e.g., 'пре-\\nкрасный' -> 'прекрасный', 'стро-{LINE}ка' -> 'строка').

    Args:
        text: Input string with potential hyphenated line breaks.

    Returns:
        String with hyphenated breaks properly collapsed.
    """
    if not text:
        return ""

    def _replace_break(match: re.Match[str]) -> str:
        prefix = match.group(1)
        remainder = match.group(2)
        if _is_genuine_compound(prefix, remainder):
            return f"{prefix}-{remainder}"
        return f"{prefix}{remainder}"

    prev = None
    curr = text
    while prev != curr:
        prev = curr
        curr = HYPHEN_BREAK_PATTERN.sub(_replace_break, curr)

    return curr


def wrap_line_to_width(
    line: str,
    glyph_widths: dict[str, int],
    max_width_px: int = 220,
    hero_name_width_px: int = DEFAULT_HERO_NAME_WIDTH_PX,
    carry: str | None = None,
) -> list[str]:
    """Wraps a single line of text to fit within max_width_px using proportional font metrics.

    Args:
        line: Text line to wrap (may contain control tags or hero tokens).
        glyph_widths: Mapping from character to pixel width.
        max_width_px: Maximum pixel width allowed per line (default 220px).
        hero_name_width_px: Estimated pixel width for dynamic hero tokens (default 30px).
        carry: Optional word hyphenation mode ("geo" or "syllable").

    Returns:
        List of wrapped lines.
    """
    if calculate_line_width_px(line, glyph_widths, hero_name_width_px) <= max_width_px:
        return [line]

    words = line.split()
    if not words:
        return [line]

    lines: list[str] = []
    current_line = ""
    word_queue = list(words)
    word_idx = 0

    while word_idx < len(word_queue):
        word = word_queue[word_idx]
        word_idx += 1

        if not current_line:
            w = calculate_line_width_px(word, glyph_widths, hero_name_width_px)
            if w <= max_width_px:
                current_line = word
            else:
                if carry:
                    split_res = split_word_carry(
                        word, max_width_px, glyph_widths, mode=carry
                    )
                    if split_res is not None:
                        prefix_hyphen, remainder = split_res
                        lines.append(prefix_hyphen)
                        word_queue.insert(word_idx, remainder)
                        current_line = ""
                        continue
                lines.append(word)
                current_line = ""
        else:
            candidate = f"{current_line} {word}"
            w = calculate_line_width_px(candidate, glyph_widths, hero_name_width_px)
            if w <= max_width_px:
                current_line = candidate
            else:
                if carry:
                    curr_w = calculate_line_width_px(
                        current_line, glyph_widths, hero_name_width_px
                    )
                    space_w = glyph_widths.get(" ", DEFAULT_SPACE_WIDTH_PX)
                    available_px = max_width_px - curr_w - space_w
                    if available_px > 0:
                        split_res = split_word_carry(
                            word, available_px, glyph_widths, mode=carry
                        )
                        if split_res is not None:
                            prefix_hyphen, remainder = split_res
                            lines.append(f"{current_line} {prefix_hyphen}")
                            word_queue.insert(word_idx, remainder)
                            current_line = ""
                            continue
                lines.append(current_line)
                current_line = ""
                word_queue.insert(word_idx, word)

    if current_line:
        lines.append(current_line)

    return lines


def _check_subpage_lines(lines: list[str], max_lines: int) -> list[str]:
    """Checks line counts per display sub-page, recognizing {WAIT_KEY} and {GLYPH:407} breaks."""
    warnings: list[str] = []
    sub_pages: list[list[str]] = [[]]
    for line in lines:
        sub_pages[-1].append(line)
        if PAGE_DELIM_PATTERN.search(line):
            sub_pages.append([])

    for sp in sub_pages:
        non_empty = [l for l in sp if l.strip()]
        if len(non_empty) > max_lines:
            warnings.append(f"Page has {len(non_empty)} lines (exceeds max {max_lines})")
    return warnings


def wrap_text_block(
    text: str,
    glyph_widths: dict[str, int],
    max_width_px: int = 220,
    max_lines: int = 3,
    auto_paginate: bool = False,
    hero_name_width_px: int = DEFAULT_HERO_NAME_WIDTH_PX,
    reflow: bool = True,
    force: bool = False,
    carry: str | None = None,
) -> tuple[str, list[str]]:
    """Word-wraps dialogue text and optionally paginates across dialog boxes.

    Preserves existing {PAGE} delimiters unless force=True or lines overflow in reflow mode.
    When force=True or lines overflow (and reflow=True), completely collapses text
    (stripping {PAGE} and line breaks) and repacks words sequentially into lines.

    Args:
        text: Full dialogue or description text block.
        glyph_widths: Mapping from character to pixel width.
        max_width_px: Maximum pixel width allowed per line (default 220px).
        max_lines: Maximum lines allowed per page/dialog box (default 3).
        auto_paginate: If True, automatically split pages exceeding max_lines with {PAGE}.
                       If False, keep lines together and generate a warning.
        hero_name_width_px: Estimated pixel width for dynamic hero tokens (default 30px).
        reflow: If True, collapse ragged single line breaks and re-wrap paragraphs.
                If False, preserve existing line breaks if within width.
        force: If True, force complete text collapse and repacking even if lines fit.
        carry: Optional word hyphenation mode ("geo" or "syllable").

    Returns:
        Tuple of (formatted_text, list_of_warnings).
    """
    if not text:
        return "", []

    raw_lines_all = re.split(r"\r?\n|\{LINE\}|\{PAGE\}", text)
    has_overflow = any(
        calculate_line_width_px(line, glyph_widths, hero_name_width_px=hero_name_width_px) > max_width_px
        for line in raw_lines_all
    )

    if force or (has_overflow and reflow):
        clean_text = collapse_hyphenated_breaks(text)
        clean_text = re.sub(r"\{PAGE\}|\r?\n|\{LINE\}", " ", clean_text)
        clean_text = re.sub(r" +", " ", clean_text).strip()
        if not clean_text:
            return "", []

        lines = wrap_line_to_width(
            clean_text,
            glyph_widths,
            max_width_px=max_width_px,
            hero_name_width_px=hero_name_width_px,
            carry=carry,
        )

        warnings: list[str] = []
        if auto_paginate:
            chunk_size = max(1, max_lines)
            chunks = [
                lines[i : i + chunk_size]
                for i in range(0, len(lines), chunk_size)
            ]
            formatted_text = "{PAGE}".join("\n".join(chunk) for chunk in chunks)
        else:
            warnings.extend(_check_subpage_lines(lines, max_lines))
            formatted_text = "\n".join(lines)
        return formatted_text, warnings

    raw_pages = text.split("{PAGE}")
    formatted_pages: list[str] = []
    warnings: list[str] = []

    for raw_page in raw_pages:
        page_lines: list[str] = []
        if max_lines == 1:
            raw_lines = re.split(r"\r?\n|\{LINE\}", raw_page)
            page_lines = [rl for rl in raw_lines if rl.strip() or rl == ""]
            if not page_lines and raw_page:
                page_lines = [raw_page]
        elif reflow:
            paragraphs = re.split(
                r"(?:\r?\n){2,}|(?<=\{WAIT_KEY\})\s*\r?\n|(?<=\{GLYPH:407\})\s*\r?\n",
                raw_page,
            )
            for para in paragraphs:
                p_clean = collapse_hyphenated_breaks(para)
                p_clean = re.sub(r"\r?\n|\{LINE\}", " ", p_clean)
                p_clean = re.sub(r" +", " ", p_clean).strip()
                if p_clean:
                    page_lines.extend(
                        wrap_line_to_width(
                            p_clean,
                            glyph_widths,
                            max_width_px=max_width_px,
                            hero_name_width_px=hero_name_width_px,
                            carry=carry,
                        )
                    )
        else:
            raw_lines = re.split(r"\r?\n|\{LINE\}", raw_page)
            for raw_line in raw_lines:
                page_lines.extend(
                    wrap_line_to_width(
                        raw_line,
                        glyph_widths,
                        max_width_px=max_width_px,
                        hero_name_width_px=hero_name_width_px,
                        carry=carry,
                    )
                )

        if auto_paginate:
            if page_lines:
                chunk_size = max(1, max_lines)
                chunks = [
                    page_lines[i : i + chunk_size]
                    for i in range(0, len(page_lines), chunk_size)
                ]
                page_str = "{PAGE}".join("\n".join(chunk) for chunk in chunks)
            else:
                page_str = ""
            formatted_pages.append(page_str)
        else:
            warnings.extend(_check_subpage_lines(page_lines, max_lines))
            page_str = "\n".join(page_lines)
            formatted_pages.append(page_str)

    formatted_text = "{PAGE}".join(formatted_pages)
    return formatted_text, warnings
