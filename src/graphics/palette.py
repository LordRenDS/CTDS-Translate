"""Palette conversion, NCL / NCLR format parsing, and palette lookup for Chrono Trigger DS.

Supports:
- BGR555 and RGB color conversions.
- Parsing and building proprietary NCL palette file headers.
- Parsing Nintendo DS SDK NCLR palette binaries (TTLP chunk).
- Sprite and screen palette matching tables and heuristic path resolution.
"""

from __future__ import annotations

import glob
import os
import re
import struct
from pathlib import Path
from typing import Any

from src.graphics.compression import decompress_stream
from src.graphics.tilemap import GraphicsEngineError

__all__ = [
    "MONSTER_CHARA_PALETTE_LIST",
    "SPECIAL_CELL_PALETTE_MAP",
    "WIRELESS_MON_PALETTE_MAP",
    "bgr555_to_rgb",
    "build_ncl_header",
    "find_palette_for_screen",
    "find_palette_for_sprite",
    "match_color_to_palette",
    "parse_ncl_header",
    "parse_nclr_palette",
    "rgb_to_bgr555",
]


def bgr555_to_rgb(c: int) -> tuple[int, int, int]:
    """Converts a 16-bit BGR555 Nintendo DS color integer to (R, G, B) 8-bit tuple.

    Args:
        c: 16-bit BGR555 color integer.

    Returns:
        tuple[int, int, int]: (red, green, blue) components in range 0-255.
    """
    r = (c & 0x1F) * 255 // 31
    g = ((c >> 5) & 0x1F) * 255 // 31
    b = ((c >> 10) & 0x1F) * 255 // 31
    return (r, g, b)


def rgb_to_bgr555(r: int, g: int, b: int) -> int:
    """Converts (R, G, B) 8-bit components to a 16-bit BGR555 Nintendo DS color integer.

    Args:
        r: Red component (0-255).
        g: Green component (0-255).
        b: Blue component (0-255).

    Returns:
        int: 16-bit BGR555 packed color.
    """
    r5 = (r * 31 + 127) // 255
    g5 = (g * 31 + 127) // 255
    b5 = (b * 31 + 127) // 255
    return (r5 & 0x1F) | ((g5 & 0x1F) << 5) | ((b5 & 0x1F) << 10)


def match_color_to_palette(
    r: int,
    g: int,
    b: int,
    palette_rgb: list[tuple[int, int, int]],
    max_colors: int | None = None,
    color_cache: dict[tuple[int, int, int], int] | None = None,
) -> int:
    """Finds the index of the nearest color in palette_rgb using Euclidean distance.

    Args:
        r: Red component (0-255).
        g: Green component (0-255).
        b: Blue component (0-255).
        palette_rgb: List of RGB tuples in palette.
        max_colors: Maximum sub-palette color count to search against.
        color_cache: Optional cache dictionary mapping RGB tuples to index.

    Returns:
        int: Best matching palette index.
    """
    rgb = (r, g, b)
    if color_cache is not None and rgb in color_cache:
        return color_cache[rgb]

    limit = len(palette_rgb) if max_colors is None else min(len(palette_rgb), max_colors)
    best_dist = float("inf")
    best_idx = 0
    for idx in range(limit):
        pc = palette_rgb[idx]
        dr = r - pc[0]
        dg = g - pc[1]
        db = b - pc[2]
        dist = dr * dr + dg * dg + db * db
        if dist < best_dist:
            best_dist = dist
            best_idx = idx

    if color_cache is not None:
        color_cache[rgb] = best_idx
    return best_idx


def parse_ncl_header(data: bytes) -> dict[str, Any]:
    """Parses an NCL palette file header (8 bytes).

    Args:
        data: NCL file raw binary data.

    Returns:
        dict[str, Any]: Dictionary containing magic, color_count, header_size.

    Raises:
        GraphicsEngineError: If data is too short or magic is invalid.
    """
    if len(data) < 8:
        raise GraphicsEngineError(f"NCL data too short: {len(data)} bytes")
    magic, color_count = struct.unpack("<4sI", data[:8])
    if magic != b"NCL\x00":
        raise GraphicsEngineError(f"Invalid NCL magic: {magic!r}")
    return {
        "magic": magic,
        "color_count": color_count,
        "header_size": 8,
    }


def build_ncl_header(color_count: int) -> bytes:
    """Builds an 8-byte NCL palette header.

    Args:
        color_count: Number of colors in the palette.

    Returns:
        bytes: 8-byte binary NCL header.
    """
    return struct.pack("<4sI", b"NCL\x00", color_count)


def parse_nclr_palette(data: bytes) -> list[int]:
    """Parses an NCLR binary file and returns flat list of RGB values [r0, g0, b0, ...].

    Args:
        data: NCLR file raw binary data.

    Returns:
        list[int]: Flat list of 256 RGB triples (768 integers).
    """
    decomp, _ = decompress_stream(data)
    ttlp_idx = decomp.find(b"TTLP")
    if ttlp_idx != -1:
        pal_size = int.from_bytes(decomp[ttlp_idx + 16 : ttlp_idx + 20], "little")
        pal_offset = int.from_bytes(decomp[ttlp_idx + 20 : ttlp_idx + 24], "little")
        # In Nitro SDK TTLP format, pal_offset (16) is relative to start of TTLP payload (ttlp_idx + 8)
        pal_raw = decomp[ttlp_idx + 8 + pal_offset : ttlp_idx + 8 + pal_offset + pal_size]
    elif decomp[:4] == b"NCL\x00":
        pal_raw = decomp[8:]
    else:
        pal_raw = decomp[0x28:] if len(decomp) > 0x28 else decomp

    colors: list[int] = []
    for i in range(0, len(pal_raw), 2):
        c = struct.unpack("<H", pal_raw[i : i + 2])[0]
        r, g, b = bgr555_to_rgb(c)
        colors.extend([r, g, b])

    while len(colors) < 256 * 3:
        colors.extend([0, 0, 0])

    return colors[: 256 * 3]


def find_palette_for_screen(nsc_path: Path | str) -> str | None:
    """Finds matching _ncl.bin palette for a given _nsc.bin screen.

    Args:
        nsc_path: Path to target NSC screen binary.

    Returns:
        str | None: Absolute path to matched NCL file, or None if not found.
    """
    nsc_path_str = str(nsc_path)
    stem = nsc_path_str[:-8]
    direct = stem + "_ncl.bin"
    if os.path.isfile(direct):
        return direct

    dir_path = os.path.dirname(nsc_path_str)
    base = os.path.basename(stem)

    # 1. Hyphen / underscore normalization
    for cand_name in (base.replace("-", "_") + "_ncl.bin", base.replace("_", "-") + "_ncl.bin"):
        cand = os.path.join(dir_path, cand_name)
        if os.path.isfile(cand):
            return cand

    # 2. Stripping double underscores or trailing underscores
    for cand_name in (base.rstrip("_") + "__ncl.bin", base.rstrip("_") + "_ncl.bin"):
        cand = os.path.join(dir_path, cand_name)
        if os.path.isfile(cand):
            return cand

    # 3. Minimap background palette fallback (menu/bg/minimap_000_ncl.bin)
    if base.startswith("minimap_"):
        cand_mm = os.path.join(dir_path, "minimap_000_ncl.bin")
        if os.path.isfile(cand_mm):
            return cand_mm

    # 3. Special screen palette mapping
    special_pal_map = {
        "kouscr": "05_racecol_ncl.bin",
        "metescr": "20_metecol__ncl.bin",
        "lasscr": "37_lascol_ncl.bin",
        "moonscr": "51_mooncol_ncl.bin",
        "wmscr": "52_wmcol1_ncl.bin",
        "font4": "60_font4_ncl.bin",
        "earsc": "EARCL_ncl.bin",
    }
    for key, val in special_pal_map.items():
        if key in base:
            cand = os.path.join(dir_path, val)
            if os.path.isfile(cand):
                return cand

    # 4. Check menu/plt with theme style suffix (e.g. _1.._8)
    style_num = None
    for part in base.split("_"):
        if part.isdigit():
            style_num = part
            break
    if style_num:
        menu_plt_style = os.path.join(os.path.dirname(dir_path), "plt", f"win_{style_num}_ncl.bin")
        if os.path.isfile(menu_plt_style):
            return menu_plt_style

    menu_plt = os.path.join(os.path.dirname(dir_path), "plt", "win_1_ncl.bin")
    if os.path.isfile(menu_plt):
        return menu_plt

    # 5. Direct prefix in dir
    cands = glob.glob(os.path.join(dir_path, "*_ncl.bin"))
    if cands:
        return cands[0]

    return None


MONSTER_CHARA_PALETTE_LIST: list[int] = [
    57, 16, 18, 19, 21, 24, 26, 241, 169, 71, 71, 233, 67, 63, 167, 68, 63, 64, 65, 63,
    243, 169, 165, 166, 243, 27, 169, 167, 28, 117, 121, 243, 122, 243, 33, 32, 32, 159,
    36, 37, 38, 101, 100, 93, 94, 92, 91, 92, 95, 14, 15, 44, 45, 212, 212, 248, 248,
    40, 237, 39, 242, 17, 86, 86, 87, 87, 238, 238, 242, 47, 105, 72, 104, 103, 102, 23,
    56, 55, 55, 54, 78, 79, 80, 81, 48, 49, 50, 58, 59, 60, 242, 111, 108, 109, 110, 107,
    242, 109, 109, 43, 332, 42, 72, 243, 74, 70, 75, 73, 73, 96, 208, 208, 97, 112, 114,
    78, 112, 116, 113, 243, 243, 29, 30, 18, 25, 106, 71, 70, 211, 90, 57, 89, 244, 246,
    84, 85, 62, 51, 52, 53, 111, 41, 191, 209, 185, 55, 182, 184, 184, 234, 193, 198, 197,
    199, 190, 186, 187, 200, 200, 210, 210, 192, 192, 194, 195, 200, 196, 196, 196, 188,
    18, 62, 31, 184, 225, 32, 205, 206, 206, 203, 203, 204, 204, 144, 213, 213, 200, 210,
    229, 230, 232, 232, 216, 183, 207, 207, 207, 207, 207, 249, 189, 207, 207, 226, 226,
    226, 233, 201, 201, 227, 228, 228, 202, 82, 83, 208, 208, 236, 243, 243, 242, 242,
    243, 242, 55, 19, 114, 26, 251, 250, 207, 207, 207, 207, 207, 207, 207, 233, 22, 233,
    40, 71, 231, 235, 157, 99, 237, 173, 215, 255, 255, 255, 256, 257, 258, 259, 260, 261,
    262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278,
    279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295,
    296, 297, 192, 298, 207, 299, 301, 302, 303, 304, 305, 306, 307, 312, 313, 314, 315,
    316, 317, 318, 319, 320, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330, 331, 334,
    335, 336, 337, 126, 338, 95, 92,
]

WIRELESS_MON_PALETTE_MAP: dict[int, int] = {
    1: 308, 2: 312, 3: 313, 4: 121, 5: 64, 6: 112, 7: 45, 8: 51,
    9: 318, 10: 95, 11: 29, 12: 62, 13: 18, 14: 266, 15: 284, 16: 103,
    17: 327, 18: 328, 19: 281, 20: 329, 21: 330, 22: 331,
}

SPECIAL_CELL_PALETTE_MAP: dict[str, str] = {
    "balloon": "50_playcol.NCLR",
    "cockpit": "37_lascol_.NCLR",
    "earobj": "EARCOL2.NCLR",
    "enemy": "05_racecol.NCLR",
    "fireworks": "47_hnbcol.NCLR",
    "font2": "34_font2.NCLR",
    "machine_direction": "38_lascol2_.NCLR",
    "machine_zoom": "38_lascol2_.NCLR",
    "obj_msk_ear": "obj_msk_ear.NCLR",
    "other": "05_racecol.NCLR",
    "planet": "18_placol.NCLR",
    "player": "05_racecol.NCLR",
    "star": "19_monocol.NCLR",
    "the_end": "58_thendcol.NCLR",
    "time_machine": "57_timcol.NCLR",
}


def find_palette_for_sprite(ncgr_path: Path | str) -> str | None:
    """Finds matching NCLR or NCL palette for a given NCGR sprite file.

    Args:
        ncgr_path: Path to the target NCGR file.

    Returns:
        str | None: Path to matching palette file if found, else None.
    """
    ncgr_path_str = str(ncgr_path)
    stem = os.path.splitext(ncgr_path_str)[0]
    dir_path = os.path.dirname(ncgr_path_str)
    base = os.path.basename(stem)

    # 1. Direct match with exact or lowercase extension
    for ext in (".NCLR", ".nclr"):
        cand = stem + ext
        if os.path.isfile(cand):
            return cand

    # 2. Language variant fallback (e.g. icon_fra.NCGR -> icon.NCLR)
    for lang in ("_fra", "_eng"):
        if base.endswith(lang):
            base_cand = os.path.join(dir_path, base[: -len(lang)] + ".NCLR")
            if os.path.isfile(base_cand):
                return base_cand

    curr = dir_path
    data_root = None
    while curr and os.path.basename(curr):
        if os.path.basename(curr) == "data":
            data_root = curr
            break
        curr = os.path.dirname(curr)

    # 3. Chara sprites (Chara_0000 -> ObjPlt_0000.NCLR, monsters -> ARM9 monster table)
    m_chara = re.match(r"^Chara_(\d+)", base)
    if m_chara:
        num = int(m_chara.group(1))
        if num < 263:
            plt_num = num
        elif num - 263 < len(MONSTER_CHARA_PALETTE_LIST):
            plt_num = MONSTER_CHARA_PALETTE_LIST[num - 263]
        else:
            plt_num = num
        cand_name = f"ObjPlt_{plt_num:04d}.NCLR"
        cand_local = os.path.join(dir_path, cand_name)
        if os.path.isfile(cand_local):
            return cand_local
        if data_root:
            cand_chara = os.path.join(data_root, "Chara", cand_name)
            if os.path.isfile(cand_chara):
                return cand_chara

    # 4. Wireless monster sprites (obj_cmu_mon_01..22 -> ObjPlt_XXXX.NCLR)
    m_cmu_mon = re.match(r"^obj_cmu_mon_(\d+)", base)
    if m_cmu_mon:
        mon_idx = int(m_cmu_mon.group(1))
        plt_num = WIRELESS_MON_PALETTE_MAP.get(mon_idx)
        if plt_num is not None:
            cand_name = f"ObjPlt_{plt_num:04d}.NCLR"
            cand_local = os.path.join(dir_path, cand_name)
            if os.path.isfile(cand_local):
                return cand_local
            if data_root:
                cand_chara = os.path.join(data_root, "Chara", cand_name)
                if os.path.isfile(cand_chara):
                    return cand_chara

    # 5. special/cell sprites (balloon, cockpit, fireworks, etc.)
    norm_dir = dir_path.replace("\\", "/").rstrip("/")
    if norm_dir.endswith("special/cell") or norm_dir.endswith("special\\cell"):
        pal_name = SPECIAL_CELL_PALETTE_MAP.get(base.lower())
        if pal_name:
            cand = os.path.join(dir_path, pal_name)
            if os.path.isfile(cand):
                return cand
            if data_root:
                cand = os.path.join(data_root, "special", "cell", pal_name)
                if os.path.isfile(cand):
                    return cand

    # 6. Effect sprites (ObjEffect_000..028 -> ObjEffect.NCLR)
    if base.startswith("ObjEffect"):
        cand_eff = os.path.join(dir_path, "ObjEffect.NCLR")
        if os.path.isfile(cand_eff):
            return cand_eff

    # 7. Wireless animation frames (obj_efe_cmu_02_0 -> obj_efe_cmu_02.NCLR)
    m_wireless = re.match(r"^(obj_efe_cmu_\d+)_\d+$", base)
    if m_wireless:
        cand_wire = os.path.join(dir_path, m_wireless.group(1) + ".NCLR")
        if os.path.isfile(cand_wire):
            return cand_wire

    # 8. WorldMap sprites (WorldObj_XXXX -> WorldObjPlt_XXXX.NCLR)
    if base.startswith("WorldObj_") or base == "WorldObj_00":
        suffix = base[len("WorldObj_"):]
        cand_wobj = os.path.join(dir_path, f"WorldObjPlt_{suffix}.NCLR")
        if os.path.isfile(cand_wobj):
            return cand_wobj
        # Epoch era variants (0107, 0207, 1007, 2007, etc.) and vehicles (0011..0014)
        if base.endswith("07") or base in ("WorldObj_0011", "WorldObj_0012", "WorldObj_0013", "WorldObj_0014"):
            cand = os.path.join(dir_path, "WorldObjPlt_0007.NCLR")
            if os.path.isfile(cand):
                return cand
            if data_root:
                cand = os.path.join(data_root, "WorldMap", "WorldObjPlt_0007.NCLR")
                if os.path.isfile(cand):
                    return cand
        # 0009 and 0010 (markers / pointers)
        if base in ("WorldObj_0009", "WorldObj_0010"):
            cand = os.path.join(dir_path, "WorldObjPlt_0001.NCLR")
            if os.path.isfile(cand):
                return cand
            if data_root:
                cand = os.path.join(data_root, "WorldMap", "WorldObjPlt_0001.NCLR")
                if os.path.isfile(cand):
                    return cand
        # WorldObj_00, WorldObj_damy fallback to WorldObjPlt_0000.NCLR
        cand = os.path.join(dir_path, "WorldObjPlt_0000.NCLR")
        if os.path.isfile(cand):
            return cand
        if data_root:
            cand = os.path.join(data_root, "WorldMap", "WorldObjPlt_0000.NCLR")
            if os.path.isfile(cand):
                return cand

    # 9. Menu window components (obj_win_*, obj_fld_win*, obj_soroll*)
    if base.startswith("obj_win_") or base.startswith("obj_fld_win") or base.startswith("obj_soroll"):
        cand_win = os.path.join(dir_path, "win_ncl.bin")
        if os.path.isfile(cand_win):
            return cand_win
        m_num = re.search(r"_(\d+)$", base)
        if m_num:
            style_num = m_num.group(1)
            cand_style = os.path.join(os.path.dirname(dir_path), "plt", f"win_{style_num}.NCLR")
            if os.path.isfile(cand_style):
                return cand_style
            if data_root:
                cand_style_global = os.path.join(data_root, "menu", "plt", f"win_{style_num}.NCLR")
                if os.path.isfile(cand_style_global):
                    return cand_style_global
                cand_style_bin = os.path.join(data_root, "menu", "plt", f"win_{style_num}_ncl.bin")
                if os.path.isfile(cand_style_bin):
                    return cand_style_bin
        cand_plt = os.path.join(os.path.dirname(dir_path), "plt", "win_1.NCLR")
        if os.path.isfile(cand_plt):
            return cand_plt
        # Search global data/menu/plt/
        if data_root:
            for def_win in ("win_1.NCLR", "win_1_ncl.bin"):
                cand_def = os.path.join(data_root, "menu", "plt", def_win)
                if os.path.isfile(cand_def):
                    return cand_def

    # 10. Face portraits (face_00..face_07 -> face.NCLR)
    if base.startswith("face"):
        cand = os.path.join(dir_path, "face.NCLR")
        if os.path.isfile(cand):
            return cand

    # 11. Slave names (obj_slv_name_00.. -> obj_slv_name.NCLR)
    if base.startswith("obj_slv_name"):
        cand = os.path.join(dir_path, "obj_slv_name.NCLR")
        if os.path.isfile(cand):
            return cand

    # 12. Character icons (chara -> chara_00.NCLR, chricon -> bticon.NCLR or chara_00.NCLR)
    if base.startswith("chara"):
        cand = os.path.join(dir_path, "chara_00.NCLR")
        if os.path.isfile(cand):
            return cand
    if base == "chricon":
        cand = os.path.join(dir_path, "bticon.NCLR")
        if os.path.isfile(cand):
            return cand

    # 13. Cursors (btcursor, cursor_*, etc.)
    if "cursor" in base:
        for cand_name in ("cursor_1.NCLR", "btcursor.NCLR"):
            cand = os.path.join(dir_path, cand_name)
            if os.path.isfile(cand):
                return cand

    # 14. icon_bike -> icon.NCLR
    if base == "icon_bike":
        cand = os.path.join(dir_path, "icon.NCLR")
        if os.path.isfile(cand):
            return cand

    return None
