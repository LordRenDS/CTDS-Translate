"""Text validator and line width calculation engine for Chrono Trigger DS.

Provides proportional font metrics (VWF) loading, control tag stripping,
and line pixel width calculation respecting dynamic hero tokens and Cyrillic glyphs.
"""

from dataclasses import dataclass
import fnmatch
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from src.char_map import BIG_CHAR_TO_GLYPH


@dataclass(frozen=True)
class TextWindowPreset:
    """Configuration preset for dialogue, hint, or UI text windows."""

    name: str
    max_width_px: int
    max_lines: int
    reflow: bool
    font_type: str  # "big" or "small"
    patterns: Tuple[str, ...]


WINDOW_PRESETS: Dict[str, TextWindowPreset] = {
    "dialogue": TextWindowPreset(
        name="dialogue",
        max_width_px=230,
        max_lines=3,
        reflow=True,
        font_type="big",
        patterns=(
            "msg*.json",
            "cmes*.json",
            "kmes*.json",
            "mesi*.json",
            "mesk*.json",
            "mess*.json",
            "mest*.json",
            "exms*.json",
            "comu*.json",
            "ques*.json",
        ),
    ),
    "tutorial": TextWindowPreset(
        name="tutorial",
        max_width_px=230,
        max_lines=6,
        reflow=True,
        font_type="big",
        patterns=("tutorial.json", "start.json", "ev_title.json"),
    ),
    "encyclopedia": TextWindowPreset(
        name="encyclopedia",
        max_width_px=215,
        max_lines=6,
        reflow=True,
        font_type="big",
        patterns=(
            "player.json",
            "ex_mon*.json",
            "ex_itemget.json",
            "ex_illust.json",
            "ex_ending.json",
        ),
    ),
    "item_desc": TextWindowPreset(
        name="item_desc",
        max_width_px=195,
        max_lines=2,
        reflow=True,
        font_type="big",
        patterns=("item_mes.json", "item_mes2.json"),
    ),
    "item_sub": TextWindowPreset(
        name="item_sub",
        max_width_px=110,
        max_lines=2,
        reflow=False,
        font_type="big",
        patterns=("item_sub.json",),
    ),
    "item_name": TextWindowPreset(
        name="item_name",
        max_width_px=105,
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=("item.json", "ex_item.json"),
    ),
    "tech_name": TextWindowPreset(
        name="tech_name",
        max_width_px=80,
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=("tech.json",),
    ),
    "tech_desc": TextWindowPreset(
        name="tech_desc",
        max_width_px=190,
        max_lines=2,
        reflow=True,
        font_type="big",
        patterns=("tec_mes.json", "mon_tec.json"),
    ),
    "monster_name": TextWindowPreset(
        name="monster_name",
        max_width_px=85,
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=("monster.json", "wireless_mon*.json"),
    ),
    "map_location": TextWindowPreset(
        name="map_location",
        max_width_px=120,
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=("map.json", "w_map.json"),
    ),
    "bgm_name": TextWindowPreset(
        name="bgm_name",
        max_width_px=145,
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=("bgm.json",),
    ),
    "credits": TextWindowPreset(
        name="credits",
        max_width_px=180,
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=("endroll*.json", "staf.json"),
    ),
    "zukan": TextWindowPreset(
        name="zukan",
        max_width_px=70,
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=("zukan.json",),
    ),
    "battle": TextWindowPreset(
        name="battle",
        max_width_px=210,
        max_lines=2,
        reflow=True,
        font_type="big",
        patterns=("battle.json",),
    ),
    "menu": TextWindowPreset(
        name="menu",
        max_width_px=200,
        max_lines=2,
        reflow=False,
        font_type="big",
        patterns=("menu.json", "wireless*.json"),
    ),
    "system_big": TextWindowPreset(
        name="system_big",
        max_width_px=200,
        max_lines=2,
        reflow=False,
        font_type="big",
        patterns=("msg/big/system.json", "msg\\big\\system.json", "big/system.json"),
    ),
    "small_system": TextWindowPreset(
        name="small_system",
        max_width_px=130,
        max_lines=1,
        reflow=False,
        font_type="small",
        patterns=(
            "msg/small/*.json",
            "msg\\small\\*.json",
            "sfc_*.json",
            "small.json",
            "small/system.json",
            "system.json",
        ),
    ),
}


def get_preset_for_file(
    file_path: str, explicit_preset: Optional[str] = None
) -> TextWindowPreset:
    """Resolves the appropriate TextWindowPreset for a given file path.

    Args:
        file_path: Path to the JSON file (can be absolute, relative, or basename).
        explicit_preset: Optional preset name override (e.g., 'tutorial', 'auto').

    Returns:
        The matched TextWindowPreset instance.

    Raises:
        ValueError: If explicit_preset is not recognized and not 'auto' or None.
    """
    if explicit_preset is not None and explicit_preset != "auto":
        if explicit_preset in WINDOW_PRESETS:
            return WINDOW_PRESETS[explicit_preset]
        raise ValueError(
            f"Unknown window preset: '{explicit_preset}'. "
            f"Valid presets: {list(WINDOW_PRESETS.keys())}"
        )

    norm_path = file_path.replace("\\", "/")
    base_name = os.path.basename(file_path)

    # Big system file check
    is_big = (
        "/big/" in norm_path
        or norm_path.startswith("big/")
        or norm_path.endswith("/big")
    )
    if is_big and base_name == "system.json":
        return WINDOW_PRESETS["system_big"]

    # Small system candidate check
    is_small_candidate = (
        "/small/" in norm_path
        or norm_path.startswith("small/")
        or norm_path.endswith("/small")
        or base_name.startswith("sfc_")
        or base_name == "small.json"
    )
    if is_small_candidate:
        small_preset = WINDOW_PRESETS["small_system"]
        for pat in small_preset.patterns:
            pat_norm = pat.replace("\\", "/")
            if "/" in pat_norm:
                if fnmatch.fnmatch(norm_path, pat_norm) or fnmatch.fnmatch(norm_path, f"*{pat_norm}"):
                    return small_preset
            else:
                if fnmatch.fnmatch(base_name, pat):
                    return small_preset

    # Check non-dialogue presets in order
    preset_order = [
        "system_big",
        "tech_name",
        "tech_desc",
        "monster_name",
        "map_location",
        "bgm_name",
        "credits",
        "zukan",
        "item_desc",
        "item_sub",
        "item_name",
        "tutorial",
        "encyclopedia",
        "battle",
        "menu",
        "small_system",
        "dialogue",
    ]

    for preset_name in preset_order:
        preset = WINDOW_PRESETS[preset_name]
        for pat in preset.patterns:
            pat_norm = pat.replace("\\", "/")
            if "/" in pat_norm:
                if fnmatch.fnmatch(norm_path, pat_norm) or fnmatch.fnmatch(norm_path, f"*{pat_norm}"):
                    return preset
            else:
                if fnmatch.fnmatch(base_name, pat):
                    return preset

    # Default fallback
    return WINDOW_PRESETS["dialogue"]


def get_constraints_for_entry(
    file_path: str, entry_id: int, explicit_preset: Optional[str] = None
) -> TextWindowPreset:
    """Resolves the effective TextWindowPreset / constraints for a specific entry ID.

    For composite files like menu.json and battle.json, returns a specialized
    TextWindowPreset tuned to the specific UI element (e.g. 2-column config options,
    small buttons, toggle switches, or hint bars).

    Args:
        file_path: Path to the JSON file.
        entry_id: Integer identifier of the text entry.
        explicit_preset: Optional preset override.

    Returns:
        The resolved TextWindowPreset for this entry.
    """
    if explicit_preset is not None and explicit_preset != "auto":
        return get_preset_for_file(file_path, explicit_preset=explicit_preset)

    base_preset = get_preset_for_file(file_path)
    base_name = os.path.basename(file_path).lower()

    if base_name == "menu.json":
        # 1. Option labels (Settings 2-column table on top screen)
        if 85 <= entry_id <= 98:
            return TextWindowPreset(
                name="menu_config_option",
                max_width_px=105,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 2. Defaults button on bottom screen ([SELECT] Defaults)
        if entry_id == 100:
            return TextWindowPreset(
                name="menu_defaults_button",
                max_width_px=45,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 3. Action buttons (Cancel, Save & Apply, Enable/Disable, Accept, Toggle Run)
        if entry_id in (99, 101, 102, 103, 104):
            return TextWindowPreset(
                name="menu_action_button",
                max_width_px=65,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 4. Settings toggle values (OFF, TYPE A, TYPE B, Custom)
        if 109 <= entry_id <= 112:
            return TextWindowPreset(
                name="menu_toggle",
                max_width_px=50,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 5. Settings tab headers (Battle I, Battle II, Controls, System)
        if 113 <= entry_id <= 116:
            return TextWindowPreset(
                name="menu_tab",
                max_width_px=65,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 6. Bottom screen hint / explanation bar
        if 144 <= entry_id <= 178:
            return TextWindowPreset(
                name="menu_bottom_hint",
                max_width_px=205,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 7. Empty inventory / equip status messages
        if 69 <= entry_id <= 74:
            return TextWindowPreset(
                name="menu_status_msg",
                max_width_px=195,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 8. Era / Epoch warp destinations
        if 39 <= entry_id <= 44:
            return TextWindowPreset(
                name="menu_era_dest",
                max_width_px=130,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 9. Inventory category tabs & sort button
        if 61 <= entry_id <= 67:
            return TextWindowPreset(
                name="menu_item_tab",
                max_width_px=95,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 10. Tech category headers (Single Techs, etc.)
        if 78 <= entry_id <= 83:
            return TextWindowPreset(
                name="menu_tech_category",
                max_width_px=95,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 11. Stat labels (Attack, Defense, Magic Defense, Next level)
        if 45 <= entry_id <= 56:
            return TextWindowPreset(
                name="menu_stat_param",
                max_width_px=95,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 12. Short stats (LV, HP, MP, Time, G, etc.)
        if 0 <= entry_id <= 35:
            return TextWindowPreset(
                name="menu_stat_label",
                max_width_px=70,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 13. Equipment slot labels (Weapon, Helm, Armor, Accessory)
        if 57 <= entry_id <= 60:
            return TextWindowPreset(
                name="menu_slot_label",
                max_width_px=70,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 14. Screen Header (Settings)
        if entry_id == 84:
            return TextWindowPreset(
                name="menu_header",
                max_width_px=110,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 15. Name entry prompt (multi-line banner)
        if entry_id == 141:
            return TextWindowPreset(
                name="menu_naming_prompt",
                max_width_px=230,
                max_lines=2,
                reflow=True,
                font_type="big",
                patterns=(),
            )
        # 16. Control navigation help lines on bottom screen
        if 179 <= entry_id <= 181:
            return TextWindowPreset(
                name="menu_control_help",
                max_width_px=230,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        return TextWindowPreset(
            name="menu_general",
            max_width_px=120,
            max_lines=1,
            reflow=False,
            font_type="big",
            patterns=(),
        )

    if base_name == "battle.json":
        # 1. Action commands (Attack, Tech, Combo, Item, Escape)
        if 0 <= entry_id <= 7:
            return TextWindowPreset(
                name="battle_command",
                max_width_px=60,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 2. Status ailments & buffs (Poison, Slow, Sleep, Stop...)
        if 8 <= entry_id <= 23:
            return TextWindowPreset(
                name="battle_status",
                max_width_px=50,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 3. Battle log / outcome messages (EXP, TP, Level Up, Escaped...)
        if 24 <= entry_id <= 49:
            return TextWindowPreset(
                name="battle_message",
                max_width_px=190,
                max_lines=2,
                reflow=True,
                font_type="big",
                patterns=(),
            )

    if base_name == "system.json" and ("small" in file_path.lower() or "sfc" in file_path.lower()):
        # Popup prompts (e.g. {LUCCA}\nObtained {ROBO}!, It's empty!)
        if 9 <= entry_id <= 11:
            return TextWindowPreset(
                name="small_system_popup",
                max_width_px=130,
                max_lines=2,
                reflow=False,
                font_type="small",
                patterns=(),
            )

    return base_preset


# Dynamic hero name tokens that represent variable visual text in-game
HERO_TOKENS = frozenset({
    "{CRONO}",
    "{MARLE}",
    "{LUCCA}",
    "{ROBO}",
    "{FROG}",
    "{AYLA}",
    "{MAGUS}",
    "{EPOCH}",
})

HERO_PATTERN = re.compile(r"\{(?:CRONO|MARLE|LUCCA|ROBO|FROG|AYLA|MAGUS|EPOCH)\}")
TAG_REGEX = re.compile(r"\{[^{}]+\}")

DEFAULT_CHAR_WIDTH_PX = 5
DEFAULT_SPACE_WIDTH_PX = 3
DEFAULT_HERO_NAME_WIDTH_PX = 30


class GlyphWidths(dict):
    """Dictionary mapping characters to their pixel widths with a 5px fallback."""

    def __missing__(self, key: str) -> int:
        return DEFAULT_CHAR_WIDTH_PX

    def get(self, key: str, default: Any = DEFAULT_CHAR_WIDTH_PX) -> int:
        return super().get(key, default)


def strip_control_tags(text: str) -> str:
    """Strips non-visual control tags while preserving dynamic hero name tokens.

    Args:
        text: Input string with control tokens (e.g., {WAIT_KEY}, {PAGE}, {CRONO}).

    Returns:
        String with non-visual control tokens removed.
    """
    def _replace(match: re.Match) -> str:
        token = match.group(0)
        if token in HERO_TOKENS:
            return token
        return ""

    return TAG_REGEX.sub(_replace, text)


def load_glyph_metrics(
    font_json_path: str,
    cyrillic_json_path: Optional[str] = None,
) -> Dict[str, int]:
    """Loads font glyph widths from base font JSON and optional Cyrillic overlay.

    Args:
        font_json_path: Path to base font JSON (e.g., extracted fonts/msg/big/msgcmn.json).
        cyrillic_json_path: Optional path to Cyrillic font JSON (e.g., assets/fonts/cyrillic_big.json).

    Returns:
        Mapping of characters to pixel widths with fallback for unmapped characters.

    Raises:
        FileNotFoundError: If font_json_path or cyrillic_json_path does not exist.
        json.JSONDecodeError: If JSON file cannot be parsed.
    """
    with open(font_json_path, "r", encoding="utf-8") as f:
        base_data = json.load(f)

    glyphs = base_data.get("glyphs", [])
    glyph_by_idx: Dict[int, int] = {}
    for g in glyphs:
        if "index" in g and "width" in g:
            glyph_by_idx[g["index"]] = g["width"]

    widths = GlyphWidths()

    # Map ASCII characters 0x1F..0x7D via char_map table if available
    char_map = base_data.get("char_map", [])
    for code in range(0x1F, min(len(char_map), 0x7E)):
        g_idx = char_map[code]
        if g_idx != 0xFFFF and g_idx in glyph_by_idx:
            widths[chr(code + 1)] = glyph_by_idx[g_idx]

    # Map characters using BIG_CHAR_TO_GLYPH table
    for ch, g_idx in BIG_CHAR_TO_GLYPH.items():
        if g_idx in glyph_by_idx:
            widths[ch] = glyph_by_idx[g_idx]

    # Map any single-character char_repr from glyphs
    for g in glyphs:
        rep = g.get("char_repr")
        if rep and len(rep) == 1 and rep not in widths and "width" in g:
            widths[rep] = g["width"]

    # Ensure space character has its correct width
    if ' ' not in widths or widths[' '] <= 0:
        if 1 in glyph_by_idx:
            widths[' '] = glyph_by_idx[1]
        else:
            widths[' '] = DEFAULT_SPACE_WIDTH_PX

    # Load Cyrillic overlay if provided
    if cyrillic_json_path is not None:
        with open(cyrillic_json_path, "r", encoding="utf-8") as f:
            cyr_data = json.load(f)
        for g in cyr_data.get("glyphs", []):
            ch = g.get("char") or g.get("char_repr")
            if ch and "width" in g:
                widths[ch] = g["width"]

    return widths


def calculate_line_width_px(
    line: str,
    glyph_widths: Dict[str, int],
    hero_name_width_px: int = DEFAULT_HERO_NAME_WIDTH_PX,
) -> int:
    """Calculates the total pixel width of a single text line under proportional font metrics.

    Args:
        line: Text line to measure (may contain control tags or hero tokens).
        glyph_widths: Mapping from character to pixel width.
        hero_name_width_px: Pixel width assigned to dynamic hero name tokens.

    Returns:
        Total width in pixels.
    """
    clean_line = strip_control_tags(line)
    if not clean_line:
        return 0

    total_width = 0
    last_end = 0

    for match in HERO_PATTERN.finditer(clean_line):
        prefix = clean_line[last_end:match.start()]
        for ch in prefix:
            if ch in ('\r', '\n'):
                continue
            total_width += glyph_widths.get(ch, DEFAULT_CHAR_WIDTH_PX)
        total_width += hero_name_width_px
        last_end = match.end()

    suffix = clean_line[last_end:]
    for ch in suffix:
        if ch in ('\r', '\n'):
            continue
        total_width += glyph_widths.get(ch, DEFAULT_CHAR_WIDTH_PX)

    return total_width


def wrap_line_to_width(
    line: str,
    glyph_widths: Dict[str, int],
    max_width_px: int = 230,
    hero_name_width_px: int = DEFAULT_HERO_NAME_WIDTH_PX,
) -> List[str]:
    """Wraps a single line of text to fit within max_width_px using proportional font metrics.

    Args:
        line: Text line to wrap (may contain control tags or hero tokens).
        glyph_widths: Mapping from character to pixel width.
        max_width_px: Maximum pixel width allowed per line (default 230px).
        hero_name_width_px: Estimated pixel width for dynamic hero tokens (default 30px).

    Returns:
        List of wrapped lines.
    """
    if calculate_line_width_px(line, glyph_widths, hero_name_width_px) <= max_width_px:
        return [line]

    words = line.split()
    if not words:
        return [line]

    lines: List[str] = []
    current_line = ""

    for word in words:
        if not current_line:
            if calculate_line_width_px(word, glyph_widths, hero_name_width_px) <= max_width_px:
                current_line = word
            else:
                lines.append(word)
                current_line = ""
        else:
            candidate = f"{current_line} {word}"
            if calculate_line_width_px(candidate, glyph_widths, hero_name_width_px) <= max_width_px:
                current_line = candidate
            else:
                lines.append(current_line)
                if calculate_line_width_px(word, glyph_widths, hero_name_width_px) <= max_width_px:
                    current_line = word
                else:
                    lines.append(word)
                    current_line = ""

    if current_line:
        lines.append(current_line)

    return lines


def wrap_text_block(
    text: str,
    glyph_widths: Dict[str, int],
    max_width_px: int = 230,
    max_lines: int = 3,
    auto_paginate: bool = False,
    hero_name_width_px: int = DEFAULT_HERO_NAME_WIDTH_PX,
    reflow: bool = True,
) -> Tuple[str, List[str]]:
    """Word-wraps dialogue text and optionally paginates across dialog boxes.

    Preserves existing {PAGE} delimiters, splits pages into lines (\\n or {LINE}),
    applies word-wrapping, and enforces or warns about line limits.
    When reflow is True (default), ragged single line breaks within each page are
    collapsed into spaces before re-wrapping to fit max_width_px cleanly.

    Args:
        text: Full dialogue or description text block.
        glyph_widths: Mapping from character to pixel width.
        max_width_px: Maximum pixel width allowed per line (default 230px).
        max_lines: Maximum lines allowed per page/dialog box (default 3).
        auto_paginate: If True, automatically split pages exceeding max_lines with {PAGE}.
                       If False, keep lines together and generate a warning.
        hero_name_width_px: Estimated pixel width for dynamic hero tokens (default 30px).
        reflow: If True, collapse ragged single line breaks and re-wrap paragraphs.
                If False, preserve existing line breaks if within width.

    Returns:
        Tuple of (formatted_text, list_of_warnings).
    """
    if not text:
        return "", []

    raw_pages = text.split("{PAGE}")
    formatted_pages: List[str] = []
    warnings: List[str] = []

    for raw_page in raw_pages:
        page_lines: List[str] = []
        if max_lines == 1:
            raw_lines = re.split(r"\r?\n|\{LINE\}", raw_page)
            page_lines = [rl for rl in raw_lines if rl.strip() or rl == ""]
            if not page_lines and raw_page:
                page_lines = [raw_page]
        elif reflow:
            paragraphs = re.split(r"(?:\r?\n){2,}", raw_page)
            for para in paragraphs:
                p_clean = re.sub(r"\r?\n|\{LINE\}", " ", para)
                p_clean = re.sub(r" +", " ", p_clean).strip()
                if p_clean:
                    page_lines.extend(
                        wrap_line_to_width(
                            p_clean,
                            glyph_widths,
                            max_width_px=max_width_px,
                            hero_name_width_px=hero_name_width_px,
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
                    )
                )

        num_lines = len(page_lines)
        if auto_paginate:
            if page_lines:
                chunk_size = max(1, max_lines)
                chunks = [
                    page_lines[i : i + chunk_size]
                    for i in range(0, num_lines, chunk_size)
                ]
                page_str = "{PAGE}".join("\n".join(chunk) for chunk in chunks)
            else:
                page_str = ""
            formatted_pages.append(page_str)
        else:
            if num_lines > max_lines:
                warnings.append(f"Page has {num_lines} lines (exceeds max {max_lines})")
            page_str = "\n".join(page_lines)
            formatted_pages.append(page_str)

    formatted_text = "{PAGE}".join(formatted_pages)
    return formatted_text, warnings


def validate_and_format_file(
    file_path: str,
    glyph_widths: Dict[str, int],
    max_width_px: Optional[int] = None,
    max_lines: Optional[int] = None,
    auto_paginate: bool = False,
    field: str = "translation",
    fix: bool = False,
    out_path: Optional[str] = None,
    hero_name_width_px: int = DEFAULT_HERO_NAME_WIDTH_PX,
    reflow: Optional[bool] = None,
    preset: str = "auto",
) -> Dict[str, Any]:
    """Validates and formats dialogue or UI text within a single JSON file.

    Checks line pixel widths against effective max_width_px, collects warnings, and optionally
    rewraps/paginates text and writes back in-place or to out_path.

    Args:
        file_path: Path to the JSON file to inspect.
        glyph_widths: Mapping from character to pixel width.
        max_width_px: Maximum pixel width allowed per line (overrides preset if not None).
        max_lines: Maximum lines allowed per page/dialog box (overrides preset if not None).
        auto_paginate: If True, automatically splits pages exceeding max_lines.
        field: Name of string field to validate (default "translation").
        fix: If True, writes rewrapped text back to JSON file.
        out_path: Destination path for fixed JSON file (if None, writes in-place).
        hero_name_width_px: Estimated pixel width for dynamic hero tokens.
        reflow: If True, collapse ragged single line breaks and re-wrap paragraphs.
                If False, preserve existing line breaks if within width.
                (overrides preset if not None).
        preset: Window preset name or "auto" for filename-based detection.

    Returns:
        Dict with keys: file_path, total_entries, overflows_found, warnings, modified, changes_count, preset.
    """
    effective_preset = get_preset_for_file(file_path, explicit_preset=preset)
    effective_max_width_px = (
        max_width_px if max_width_px is not None else effective_preset.max_width_px
    )
    effective_max_lines = (
        max_lines if max_lines is not None else effective_preset.max_lines
    )
    effective_reflow = reflow if reflow is not None else effective_preset.reflow

    with open(file_path, "r", encoding="utf-8") as f:
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

    total_entries = len(entries)
    overflows_count = 0
    warnings: List[str] = []
    changes_count = 0

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id", i)
        text = entry.get(field)
        if not text or not isinstance(text, str):
            continue

        entry_preset = get_constraints_for_entry(file_path, entry_id, explicit_preset=preset)
        entry_max_width_px = (
            max_width_px if max_width_px is not None else entry_preset.max_width_px
        )
        entry_max_lines = (
            max_lines if max_lines is not None else entry_preset.max_lines
        )
        entry_reflow = reflow if reflow is not None else entry_preset.reflow

        # Check overflows in original lines
        raw_pages = text.split("{PAGE}")
        for raw_page in raw_pages:
            raw_lines = re.split(r"\r?\n|\{LINE\}", raw_page)
            for raw_line in raw_lines:
                line_width = calculate_line_width_px(
                    raw_line, glyph_widths, hero_name_width_px=hero_name_width_px
                )
                if line_width > entry_max_width_px:
                    overflows_count += 1
                    warnings.append(
                        f"Entry {entry_id}: line exceeds {entry_max_width_px}px ({line_width}px): '{raw_line}'"
                    )

        wrapped_text, block_warnings = wrap_text_block(
            text,
            glyph_widths,
            max_width_px=entry_max_width_px,
            max_lines=entry_max_lines,
            auto_paginate=auto_paginate,
            hero_name_width_px=hero_name_width_px,
            reflow=entry_reflow,
        )
        for bw in block_warnings:
            warnings.append(f"Entry {entry_id}: {bw}")

        if wrapped_text != text:
            changes_count += 1
            if fix:
                entry[field] = wrapped_text

    modified = False
    if fix and (changes_count > 0 or out_path is not None):
        target_path = out_path if out_path is not None else file_path
        parent_dir = os.path.dirname(target_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        modified = True

    return {
        "file_path": file_path,
        "total_entries": total_entries,
        "overflows_found": overflows_count,
        "warnings": warnings,
        "modified": modified,
        "changes_count": changes_count,
        "preset": effective_preset.name,
    }


def validate_and_format_directory(
    json_dir: str,
    font_json_path: str = "extracted fonts/msg/big/msgcmn.json",
    cyrillic_json_path: Optional[str] = "assets/fonts/cyrillic_big.json",
    max_width_px: Optional[int] = None,
    max_lines: Optional[int] = None,
    auto_paginate: bool = False,
    field: str = "translation",
    fix: bool = False,
    out_dir: Optional[str] = None,
    hero_name_width_px: int = DEFAULT_HERO_NAME_WIDTH_PX,
    glyph_widths: Optional[Dict[str, int]] = None,
    reflow: Optional[bool] = None,
    preset: str = "auto",
) -> Dict[str, Any]:
    """Recursively validates and formats all JSON translation files in a directory.

    Args:
        json_dir: Root directory containing JSON translation files.
        font_json_path: Path to base font JSON (default extracted fonts/msg/big/msgcmn.json).
        cyrillic_json_path: Path to Cyrillic font JSON overlay.
        max_width_px: Maximum pixel width allowed per line (overrides presets if specified).
        max_lines: Maximum lines allowed per page/dialog box (overrides presets if specified).
        auto_paginate: If True, automatically splits pages exceeding max_lines.
        field: Name of string field to validate (default "translation").
        fix: If True, writes rewrapped text back.
        out_dir: Optional destination directory mirroring input hierarchy.
        hero_name_width_px: Estimated pixel width for dynamic hero tokens.
        glyph_widths: Optional preloaded glyph widths dictionary.
        reflow: If True, collapse ragged single line breaks and re-wrap paragraphs.
                If False, preserve existing line breaks if within width.
        preset: Window preset name or "auto" for automatic per-file detection.

    Returns:
        Dict with keys: files_checked, files_modified, total_entries, total_overflows,
        total_warnings, presets_used, file_reports.
    """
    if glyph_widths is None:
        glyph_widths = load_glyph_metrics(font_json_path, cyrillic_json_path)

    # Lazily preload small font metrics if present
    small_glyph_widths = None
    small_font_path = "extracted fonts/msg/small/msgcmn.json"
    small_cyr_path = "assets/fonts/cyrillic_small.json"
    if os.path.isfile(small_font_path):
        try:
            cyr_opt = small_cyr_path if os.path.isfile(small_cyr_path) else None
            small_glyph_widths = load_glyph_metrics(small_font_path, cyr_opt)
        except Exception:
            small_glyph_widths = None

    if not os.path.isdir(json_dir):
        raise FileNotFoundError(f"JSON directory not found: {json_dir}")

    json_files: List[str] = []
    for root, _dirs, files in os.walk(json_dir):
        for file in files:
            if file.lower().endswith(".json"):
                json_files.append(os.path.join(root, file))

    json_files.sort()

    file_reports: List[Dict[str, Any]] = []
    for file_path in json_files:
        if out_dir is not None:
            rel_path = os.path.relpath(file_path, json_dir)
            target_out_path = os.path.join(out_dir, rel_path)
        else:
            target_out_path = None

        target_preset = get_preset_for_file(file_path, explicit_preset=preset)
        file_metrics = (
            small_glyph_widths
            if (target_preset.font_type == "small" and small_glyph_widths is not None)
            else glyph_widths
        )

        report = validate_and_format_file(
            file_path,
            glyph_widths=file_metrics,
            max_width_px=max_width_px,
            max_lines=max_lines,
            auto_paginate=auto_paginate,
            field=field,
            fix=fix,
            out_path=target_out_path,
            hero_name_width_px=hero_name_width_px,
            reflow=reflow,
            preset=preset,
        )
        file_reports.append(report)

    files_checked = len(json_files)
    files_modified = sum(1 for r in file_reports if r["modified"])
    total_entries = sum(r["total_entries"] for r in file_reports)
    total_overflows = sum(r["overflows_found"] for r in file_reports)
    total_warnings = sum(len(r["warnings"]) for r in file_reports)

    presets_used: Dict[str, int] = {}
    for r in file_reports:
        p_name = r.get("preset", "dialogue")
        presets_used[p_name] = presets_used.get(p_name, 0) + 1

    return {
        "files_checked": files_checked,
        "files_modified": files_modified,
        "total_entries": total_entries,
        "total_overflows": total_overflows,
        "total_warnings": total_warnings,
        "presets_used": presets_used,
        "file_reports": file_reports,
    }

