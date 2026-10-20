"""Window presets and granular UI entry constraints for Chrono Trigger DS."""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.exceptions import ValidationError

__all__ = [
    "TextWindowPreset",
    "WINDOW_PRESETS",
    "get_constraints_for_entry",
    "get_preset_for_file",
]


@dataclass(frozen=True)
class TextWindowPreset:
    """Configuration preset for dialogue, hint, or UI text windows."""

    name: str
    max_width_px: int
    max_lines: int
    reflow: bool
    font_type: str  # "big" or "small"
    patterns: tuple[str, ...]


WINDOW_PRESETS: dict[str, TextWindowPreset] = {
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
    "field_choice_box": TextWindowPreset(
        name="field_choice_box",
        max_width_px=110,
        max_lines=4,
        reflow=False,
        font_type="big",
        patterns=(),
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
    "ending_title": TextWindowPreset(
        name="ending_title",
        max_width_px=180,
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=(),
    ),
    "player_char_name": TextWindowPreset(
        name="player_char_name",
        max_width_px=100,
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=(),
    ),
    "player_char_profile": TextWindowPreset(
        name="player_char_profile",
        max_width_px=132,
        max_lines=6,
        reflow=True,
        font_type="big",
        patterns=(),
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
    "extra_button": TextWindowPreset(
        name="extra_button",
        max_width_px=95,
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=(),
    ),
    "extra_desc": TextWindowPreset(
        name="extra_desc",
        max_width_px=224,
        max_lines=2,
        reflow=True,
        font_type="big",
        patterns=(),
    ),
    "zukan_stat_label": TextWindowPreset(
        name="zukan_stat_label",
        max_width_px=48,
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=(),
    ),
    "zukan_discovered": TextWindowPreset(
        name="zukan_discovered",
        max_width_px=65,
        max_lines=1,
        reflow=False,
        font_type="big",
        patterns=(),
    ),
    "status_tutorial": TextWindowPreset(
        name="status_tutorial",
        max_width_px=210,
        max_lines=3,
        reflow=False,
        font_type="big",
        patterns=(),
    ),
}


def get_preset_for_file(
    file_path: str | Path, explicit_preset: str | None = None
) -> TextWindowPreset:
    """Resolves the appropriate TextWindowPreset for a given file path.

    Args:
        file_path: Path to the JSON file (can be absolute, relative, or basename).
        explicit_preset: Optional preset name override (e.g., 'tutorial', 'auto').

    Returns:
        The matched TextWindowPreset instance.

    Raises:
        ValidationError: If explicit_preset is not recognized and not 'auto' or None.
    """
    if explicit_preset is not None and explicit_preset != "auto":
        if explicit_preset in WINDOW_PRESETS:
            return WINDOW_PRESETS[explicit_preset]
        raise ValidationError(
            f"Unknown window preset: '{explicit_preset}'. "
            f"Valid presets: {list(WINDOW_PRESETS.keys())}"
        )

    norm_path = str(file_path).replace("\\", "/")
    base_name = os.path.basename(str(file_path))

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
    file_path: str | Path,
    entry_id: int = 0,
    explicit_preset: str | None = None,
    entry_index: int | None = None,
    tag_id: int | None = None,
    entry_dict: dict[str, Any] | None = None,
) -> TextWindowPreset:
    """Resolves the effective TextWindowPreset / constraints for a specific entry ID.

    For composite files like menu.json and battle.json, returns a specialized
    TextWindowPreset tuned to the specific UI element (e.g. 2-column config options,
    small buttons, toggle switches, or hint bars).

    Args:
        file_path: Path to the JSON file.
        entry_id: Integer identifier of the text entry.
        explicit_preset: Optional preset override.
        entry_index: Optional index fallback if entry_id is omitted.
        tag_id: Optional tag ID metadata.
        entry_dict: Optional entry dictionary metadata.

    Returns:
        The resolved TextWindowPreset for this entry.
    """
    if entry_id == 0 and entry_index is not None:
        entry_id = entry_index

    if explicit_preset is not None and explicit_preset != "auto":
        return get_preset_for_file(file_path, explicit_preset=explicit_preset)

    base_preset = get_preset_for_file(file_path)
    base_name = os.path.basename(str(file_path)).lower()

    if base_name == "start.json":
        # 1. Game mode descriptions (DS Mode & Classic Mode on right of settings screen)
        # Outer box: x=120..249 (w=130), y=79..171 (h=92).
        # Left text anchor: x=125 (padding 5px).
        # Symmetric right padding: 5px (x=244).
        # Inner printable width: 244 - 125 = 119px (safe limit: 118px).
        # Line pitch: 13px. Max lines: 7.
        if entry_id in (77, 78):
            return TextWindowPreset(
                name="start_mode_desc",
                max_width_px=118,
                max_lines=7,
                reflow=True,
                font_type="big",
                patterns=(),
            )
        # 2. Battle mode (Active/Wait) & Movie mode descriptions
        # Max width: 145px, line pitch: 13px, max lines: 4.
        if entry_id in (82, 83, 87, 88):
            return TextWindowPreset(
                name="start_setting_desc",
                max_width_px=145,
                max_lines=4,
                reflow=True,
                font_type="big",
                patterns=(),
            )
        # 3. Card/save corruption and file access alert modals
        if (23 <= entry_id <= 49) or (104 <= entry_id <= 108):
            return TextWindowPreset(
                name="start_alert_box",
                max_width_px=220,
                max_lines=3,
                reflow=True,
                font_type="big",
                patterns=(),
            )
        # 4. Title screen main menu action buttons (New Game, Load Game, Arena, Extras)
        if 0 <= entry_id <= 11:
            return TextWindowPreset(
                name="start_title_button",
                max_width_px=100,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 5. Setting labels and toggle buttons (Game Mode, Classic, DS, Battle Mode, Active, Wait, etc.)
        if entry_id in (73, 74, 75, 76, 79, 80, 81, 84, 85, 86, 89, 90):
            return TextWindowPreset(
                name="start_setting_button",
                max_width_px=110,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 6. Bottom screen hint bar in settings ("These settings can be changed later")
        if entry_id == 91:
            return TextWindowPreset(
                name="start_bottom_hint",
                max_width_px=224,
                max_lines=1,
                reflow=False,
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

    if base_name == "ex_ending.json":
        if 0 <= entry_id <= 25:
            return WINDOW_PRESETS["ending_desc"]
        elif 26 <= entry_id <= 38:
            return WINDOW_PRESETS["ending_title"]

    if base_name == "player.json":
        if 0 <= entry_id <= 7:
            return WINDOW_PRESETS["player_char_name"]
        elif 8 <= entry_id <= 15:
            return WINDOW_PRESETS["player_char_profile"]

    if base_name == "bgm.json":
        return WINDOW_PRESETS["bgm_name"]

    if base_name == "extra.json":
        if 0 <= entry_id <= 15:
            return WINDOW_PRESETS["extra_button"]
        if 16 <= entry_id <= 31:
            return WINDOW_PRESETS["extra_desc"]

    if base_name == "zukan.json":
        if 10 <= entry_id <= 13:
            return WINDOW_PRESETS["zukan_stat_label"]
        if entry_id == 16:
            return WINDOW_PRESETS["zukan_discovered"]

    if base_name == "cmes0.json" and 98 <= entry_id <= 114:
        return WINDOW_PRESETS["status_tutorial"]

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
        # 6. Shop UI controls & notices
        if 117 <= entry_id <= 120:
            return TextWindowPreset(
                name="shop_action_button",
                max_width_px=70,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        if entry_id in (121, 122, 135, 136):
            return TextWindowPreset(
                name="shop_funds_label",
                max_width_px=75,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        if 123 <= entry_id <= 130:
            return TextWindowPreset(
                name="shop_empty_notice",
                max_width_px=195,
                max_lines=2,
                reflow=True,
                font_type="big",
                patterns=(),
            )
        if 132 <= entry_id <= 134:
            return TextWindowPreset(
                name="shop_stat_label",
                max_width_px=75,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 7. Bottom screen hint / explanation bar
        if 144 <= entry_id <= 178:
            return TextWindowPreset(
                name="menu_bottom_hint",
                max_width_px=205,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 8. Empty inventory / equip status messages
        if 69 <= entry_id <= 74:
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
        # 17. Usable by label (entry 76: "Usable by:" / "Peut s'en\\néquiper :")
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
                name="battle_cmd_button",
                max_width_px=80,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 2. Status ailments & conditions (Poison, Slow, Sleep, Blind...)
        if 8 <= entry_id <= 23:
            return TextWindowPreset(
                name="battle_status_condition",
                max_width_px=75,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 3. Battle result labels (Enemies:, Obtained, EXP, TP, G)
        if 24 <= entry_id <= 31:
            return TextWindowPreset(
                name="battle_label",
                max_width_px=60,
                max_lines=1,
                reflow=False,
                font_type="big",
                patterns=(),
            )
        # 4. Battle log / outcome messages (Level Up, Learned Tech, Escaped...)
        if 32 <= entry_id <= 49:
            return TextWindowPreset(
                name="battle_result_msg",
                max_width_px=180,
                max_lines=2,
                reflow=True,
                font_type="big",
                patterns=(),
            )

    if base_name == "system.json":
        norm_path = str(file_path).replace("\\", "/").lower()
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
