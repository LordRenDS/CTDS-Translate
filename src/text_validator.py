"""Text validator and line width calculation engine for Chrono Trigger DS.

Provides proportional font metrics (VWF) loading, control tag stripping,
and line pixel width calculation respecting dynamic hero tokens and Cyrillic glyphs.
"""

from dataclasses import dataclass
import fnmatch
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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
        max_width_px=238,
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
        max_width_px=200,
        max_lines=6,
        reflow=True,
        font_type="big",
        patterns=("tutorial.json",),
    ),
    "chapter_title": TextWindowPreset(
        name="chapter_title",
        max_width_px=130,
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=("ev_title.json",),
    ),
    "battle_banner": TextWindowPreset(
        name="battle_banner",
        max_width_px=238,
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=("mon_tec.json",),
    ),
    "ending_desc": TextWindowPreset(
        name="ending_desc",
        max_width_px=224,
        max_lines=2,
        reflow=True,
        font_type="big",
        patterns=("ex_ending.json",),
    ),
    "encyclopedia": TextWindowPreset(
        name="encyclopedia",
        max_width_px=136,
        max_lines=6,
        reflow=True,
        font_type="big",
        patterns=(
            "player.json",
            "ex_mon*.json",
            "ex_itemget.json",
            "ex_illust.json",
        ),
    ),
    "item_desc": TextWindowPreset(
        name="item_desc",
        max_width_px=210,
        max_lines=1,
        reflow=False,
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
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=("tec_mes.json",),
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
        max_width_px=140,
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
        max_width_px=80,
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=("zukan.json",),
    ),
    "battle": TextWindowPreset(
        name="battle",
        max_width_px=180,
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
        "chapter_title",
        "battle_banner",
        "ending_desc",
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

    if base_name == "start.json":
        if entry_id in (77, 78):
            return TextWindowPreset(
                name="start_mode_desc",
                max_width_px=130,
                max_lines=7,
                reflow=True,
                font_type="big",
                patterns=(),
            )
        if entry_id in (82, 83, 87, 88):
            return TextWindowPreset(
                name="start_setting_desc",
                max_width_px=145,
                max_lines=4,
                reflow=True,
                font_type="big",
                patterns=(),
            )
        if (23 <= entry_id <= 45) or (104 <= entry_id <= 108):
            return TextWindowPreset(
                name="start_alert_box",
                max_width_px=220,
                max_lines=3,
                reflow=True,
                font_type="big",
                patterns=(),
            )
        return TextWindowPreset(
            name="start_general",
            max_width_px=200,
            max_lines=2,
            reflow=False,
            font_type="big",
            patterns=(),
        )

    if base_name == "ex_item.json":
        if (176 <= entry_id <= 204) or (247 <= entry_id <= 250):
            return TextWindowPreset(
                name="ex_item_treasure_choice",
                max_width_px=165,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        return TextWindowPreset(
            name="item_name",
            max_width_px=105,
            max_lines=1,
            reflow=False,
            font_type="big",
            patterns=(),
        )

    if base_name == "ex_illust.json":
        return TextWindowPreset(
            name="ex_illust_title",
            max_width_px=145,
            max_lines=1,
            reflow=False,
            font_type="big",
            patterns=(),
        )

    if base_name == "tutorial.json":
        if entry_id == 12:
            return TextWindowPreset(
                name="tutorial_prompt",
                max_width_px=230,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        return TextWindowPreset(
            name="tutorial",
            max_width_px=210,
            max_lines=6,
            reflow=True,
            font_type="big",
            patterns=(),
        )

    if base_name.startswith("wireless") and not base_name.startswith("wireless_mon"):
        return TextWindowPreset(
            name="wireless_menu",
            max_width_px=210,
            max_lines=2,
            reflow=False,
            font_type="big",
            patterns=(),
        )

    if base_name == "menu.json":
        # 1. Option labels (Settings 2-column table on top screen)
        if 85 <= entry_id <= 98:
            return TextWindowPreset(
                name="menu_config_option",
                max_width_px=110,
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
                max_width_px=95,
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
        # 7. Empty inventory / equip status messages & empty shop messages
        if (69 <= entry_id <= 74) or (entry_id in (125, 126, 129, 130)):
            return TextWindowPreset(
                name="menu_status_msg",
                max_width_px=195,
                max_lines=2,
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
                max_width_px=220,
                max_lines=2,
                reflow=True,
                font_type="big",
                patterns=(),
            )
        # 16. Control navigation help lines on bottom screen
        if 179 <= entry_id <= 181:
            return TextWindowPreset(
                name="menu_control_help",
                max_width_px=224,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 17. Usable by label (entry 76: "Usable by:" / "Peut s'en\néquiper :")
        if entry_id == 76:
            return TextWindowPreset(
                name="menu_usable_by",
                max_width_px=70,
                max_lines=2,
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
                max_width_px=65,
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

    if base_name == "system.json":
        norm_path = file_path.replace("\\", "/").lower()
        is_small = (
            "/small/" in norm_path
            or norm_path.startswith("small/")
            or norm_path.endswith("/small")
            or "sfc" in norm_path
            or base_preset.font_type == "small"
        )
        if is_small:
            if entry_id in (1, 2, 3, 4, 5, 6):
                return TextWindowPreset(
                    name="system_charmap",
                    max_width_px=9999,
                    max_lines=99,
                    reflow=False,
                    font_type="small",
                    patterns=(),
                )
            if 9 <= entry_id <= 11:
                return TextWindowPreset(
                    name="small_system_popup",
                    max_width_px=130,
                    max_lines=2,
                    reflow=False,
                    font_type="small",
                    patterns=(),
                )
        else:
            if entry_id in (3, 4, 6):
                return TextWindowPreset(
                    name="system_charmap",
                    max_width_px=9999,
                    max_lines=99,
                    reflow=False,
                    font_type="big",
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
GLYPH_PATTERN = re.compile(r"^\{GLYPH:\d+\}$")
PLACEHOLDER_PATTERN = re.compile(
    r"\{(?:(CRONO|MARLE|LUCCA|ROBO|FROG|AYLA|MAGUS|EPOCH)|GLYPH:(\d+))\}"
)
TAG_REGEX = re.compile(r"\{[^{}]+\}")

DEFAULT_CHAR_WIDTH_PX = 5
DEFAULT_SPACE_WIDTH_PX = 3
DEFAULT_HERO_NAME_WIDTH_PX = 30


class GlyphWidths(dict):
    """Dictionary mapping characters to their pixel widths with a 5px fallback."""

    def __init__(self, *args, glyph_by_idx: Optional[Dict[int, int]] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.glyph_by_idx: Dict[int, int] = glyph_by_idx if glyph_by_idx is not None else {}

    def __missing__(self, key: str) -> int:
        return DEFAULT_CHAR_WIDTH_PX

    def get(self, key: str, default: Any = DEFAULT_CHAR_WIDTH_PX) -> int:
        return super().get(key, default)


def strip_control_tags(text: str) -> str:
    """Strips non-visual control tags while preserving dynamic hero name tokens and glyphs.

    Args:
        text: Input string with control tokens (e.g., {WAIT_KEY}, {PAGE}, {CRONO}, {GLYPH:12}).

    Returns:
        String with non-visual control tokens removed.
    """
    text = re.sub(r"\{GLYPH:405\}[0-9a-fA-F]+\{GLYPH:406\}", "", text)
    text = re.sub(r"\{GLYPH:407\}[0-9a-fA-F]+\{GLYPH:408\}", "", text)
    text = re.sub(r"\{GLYPH:40[5-8]\}", "", text)

    def _replace(match: re.Match) -> str:
        token = match.group(0)
        if token in HERO_TOKENS or GLYPH_PATTERN.match(token):
            return token
        return ""

    return TAG_REGEX.sub(_replace, text)


def load_glyph_metrics(
    font_json_path: str,
    cyrillic_json_path: Optional[str] = None,
) -> GlyphWidths:
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

    # Load Cyrillic overlay if provided
    cyr_glyphs = []
    if cyrillic_json_path is not None:
        with open(cyrillic_json_path, "r", encoding="utf-8") as f:
            cyr_data = json.load(f)
        cyr_glyphs = cyr_data.get("glyphs", [])
        for g in cyr_glyphs:
            if "font_glyph_id" in g and "width" in g:
                glyph_by_idx[g["font_glyph_id"]] = g["width"]

    widths = GlyphWidths(glyph_by_idx=glyph_by_idx)

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

    # Map any single-character char_repr from base glyphs
    for g in glyphs:
        rep = g.get("char_repr")
        if rep and len(rep) == 1 and rep not in widths and "width" in g:
            widths[rep] = g["width"]

    # Map Cyrillic glyphs
    for g in cyr_glyphs:
        ch = g.get("char") or g.get("char_repr")
        if ch and "width" in g:
            widths[ch] = g["width"]

    # Ensure space character has its correct width
    if ' ' not in widths or widths[' '] <= 0:
        if 1 in glyph_by_idx:
            widths[' '] = glyph_by_idx[1]
        else:
            widths[' '] = DEFAULT_SPACE_WIDTH_PX

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

    for match in PLACEHOLDER_PATTERN.finditer(clean_line):
        prefix = clean_line[last_end:match.start()]
        for ch in prefix:
            if ch in ('\r', '\n'):
                continue
            total_width += glyph_widths.get(ch, DEFAULT_CHAR_WIDTH_PX)

        hero_token, glyph_idx_str = match.groups()
        if hero_token is not None:
            total_width += hero_name_width_px
        elif glyph_idx_str is not None:
            glyph_idx = int(glyph_idx_str)
            glyph_by_idx = getattr(glyph_widths, "glyph_by_idx", None)
            if isinstance(glyph_by_idx, dict) and glyph_idx in glyph_by_idx:
                total_width += glyph_by_idx[glyph_idx]
            elif match.group(0) in glyph_widths:
                total_width += glyph_widths[match.group(0)]
            elif f"GLYPH:{glyph_idx}" in glyph_widths:
                total_width += glyph_widths[f"GLYPH:{glyph_idx}"]
            else:
                total_width += DEFAULT_CHAR_WIDTH_PX

        last_end = match.end()

    suffix = clean_line[last_end:]
    for ch in suffix:
        if ch in ('\r', '\n'):
            continue
        total_width += glyph_widths.get(ch, DEFAULT_CHAR_WIDTH_PX)

    return total_width


RUS_VOWELS = frozenset("аеёиоуыэюяАЕЁИОУЫЭЮЯ")
RUS_CONSONANTS = frozenset("бвгджзйклмнпрстфхцчшщБВГДЖЗЙКЛМНПРСТФХЦЧШЩ")
LATIN_VOWELS = frozenset("aeiouyAEIOUY")


def split_word_carry(
    word: str,
    available_width_px: int,
    glyph_widths: Dict[str, int],
    mode: str = "geo",
) -> Optional[Tuple[str, str]]:
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


def wrap_line_to_width(
    line: str,
    glyph_widths: Dict[str, int],
    max_width_px: int = 220,
    hero_name_width_px: int = DEFAULT_HERO_NAME_WIDTH_PX,
    carry: Optional[str] = None,
) -> List[str]:
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

    lines: List[str] = []
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


HYPHEN_BREAK_PATTERN = re.compile(
    r"([a-zA-Zа-яА-ЯёЁ]+)-\s*(?:\r?\n|\{LINE\}|\{PAGE\})\s*(?:(?:\r?\n|\{LINE\}|\{PAGE\})\s*)*([a-zA-Zа-яА-ЯёЁ]+)"
)

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

    def _replace_break(match: re.Match) -> str:
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


def wrap_text_block(
    text: str,
    glyph_widths: Dict[str, int],
    max_width_px: int = 220,
    max_lines: int = 3,
    auto_paginate: bool = False,
    hero_name_width_px: int = DEFAULT_HERO_NAME_WIDTH_PX,
    reflow: bool = True,
    force: bool = False,
    carry: Optional[str] = None,
) -> Tuple[str, List[str]]:
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

        warnings: List[str] = []
        if auto_paginate:
            chunk_size = max(1, max_lines)
            chunks = [
                lines[i : i + chunk_size]
                for i in range(0, len(lines), chunk_size)
            ]
            formatted_text = "{PAGE}".join("\n".join(chunk) for chunk in chunks)
        else:
            if len(lines) > max_lines:
                warnings.append(f"Page has {len(lines)} lines (exceeds max {max_lines})")
            formatted_text = "\n".join(lines)
        return formatted_text, warnings

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
    file_path: Union[str, Path],
    glyph_widths: Optional[Dict[str, int]] = None,
    max_width_px: Optional[int] = None,
    max_lines: Optional[int] = None,
    auto_paginate: bool = False,
    field: str = "translation",
    fix: bool = False,
    out_path: Optional[str] = None,
    hero_name_width_px: int = DEFAULT_HERO_NAME_WIDTH_PX,
    reflow: Optional[bool] = None,
    preset: str = "auto",
    force: bool = False,
    carry: Optional[str] = None,
    font_widths: Optional[Dict[str, int]] = None,
    small_widths: Optional[Dict[str, int]] = None,
    dry_run: Optional[bool] = None,
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
        force: If True, force recalculation and repacking of all text even if lines fit.
        carry: Optional word hyphenation mode ("geo" or "syllable").
        font_widths: Alias for glyph_widths.
        small_widths: Optional metrics for small-font entries.
        dry_run: If True, do not write changes to disk even if fix=True.

    Returns:
        Dict with keys: file_path, total_entries, overflows_found, warnings, modified, changes_count, preset.
    """
    if dry_run is not None and dry_run:
        fix = False

    effective_preset = get_preset_for_file(str(file_path), explicit_preset=preset)
    effective_max_width_px = (
        max_width_px if max_width_px is not None else effective_preset.max_width_px
    )
    effective_max_lines = (
        max_lines if max_lines is not None else effective_preset.max_lines
    )
    effective_reflow = reflow if reflow is not None else effective_preset.reflow

    active_base_widths = font_widths if font_widths is not None else glyph_widths
    if active_base_widths is None:
        active_base_widths = load_glyph_metrics(
            "extracted fonts/msg/big/msgcmn.json",
            "assets/fonts/cyrillic_big.json" if os.path.isfile("assets/fonts/cyrillic_big.json") else None,
        )

    if small_widths is None and os.path.isfile("extracted fonts/msg/small/msgcmn.json"):
        try:
            small_widths = load_glyph_metrics(
                "extracted fonts/msg/small/msgcmn.json",
                "assets/fonts/cyrillic_small.json" if os.path.isfile("assets/fonts/cyrillic_small.json") else None,
            )
        except Exception:
            small_widths = None

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

        entry_preset = get_constraints_for_entry(str(file_path), entry_id, explicit_preset=preset)
        entry_max_width_px = (
            max_width_px if max_width_px is not None else entry_preset.max_width_px
        )
        entry_max_lines = (
            max_lines if max_lines is not None else entry_preset.max_lines
        )
        entry_reflow = reflow if reflow is not None else entry_preset.reflow
        active_widths = (
            small_widths
            if (entry_preset.font_type == "small" and small_widths is not None)
            else active_base_widths
        )

        # Check overflows in original lines
        raw_pages = text.split("{PAGE}")
        for raw_page in raw_pages:
            raw_lines = re.split(r"\r?\n|\{LINE\}", raw_page)
            if field in ("original_en", "original_fr") and entry_max_lines == 1 and len(raw_lines) > 1:
                overflows_count += 1
                warnings.append(
                    f"Entry {entry_id}: Page has {len(raw_lines)} lines (exceeds max 1)"
                )
            for raw_line in raw_lines:
                line_width = calculate_line_width_px(
                    raw_line, active_widths, hero_name_width_px=hero_name_width_px
                )
                if line_width > entry_max_width_px:
                    overflows_count += 1
                    warnings.append(
                        f"Entry {entry_id}: line exceeds {entry_max_width_px}px ({line_width}px): '{raw_line}'"
                    )

        if fix or field not in ("original_en", "original_fr"):
            wrapped_text, block_warnings = wrap_text_block(
                text,
                active_widths,
                max_width_px=entry_max_width_px,
                max_lines=entry_max_lines,
                auto_paginate=auto_paginate,
                hero_name_width_px=hero_name_width_px,
                reflow=entry_reflow,
                force=force,
                carry=carry,
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
        "file_path": str(file_path),
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
    force: bool = False,
    carry: Optional[str] = None,
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
        force: If True, force recalculation and repacking of all text even if lines fit.
        carry: Optional word hyphenation mode ("geo" or "syllable").

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
            force=force,
            carry=carry,
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

