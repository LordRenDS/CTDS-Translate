"""Graphics Engine for Chrono Trigger DS.

Handles extraction and re-insertion of Nintendo DS background screens:
- Multi-layer LZ10 decompression and compression.
- Parsing and serialization of Chrono Trigger DS proprietary NCG, NCL, NSC headers.
- Rendering tilemaps to PNG and metadata JSON.
- Slicing PNGs into 8x8 tiles with smart deduplication (normal, H-flip, V-flip, HV-flip).
- Rebuilding game binary triplets (*_ncg.bin, *_ncl.bin, *_nsc.bin).
"""

import json
import os
import re
import struct
from typing import Any, Dict, List, Optional, Tuple

import ndspy.color
import ndspy.graphics2D
import ndspy.lz10


class GraphicsEngineError(Exception):
    """Base exception for graphics engine errors."""


class TilePoolOverflowError(GraphicsEngineError):
    """Raised when unique tile count exceeds Nintendo DS hardware limit (1024 tiles)."""


class DumpResult(int):
    """Result of a graphics dump operation, behaves as an int total count."""

    total: int
    screens: int
    slides: int
    sprites: int

    def __new__(cls, total: int, screens: int = 0, slides: int = 0, sprites: int = 0):
        obj = super().__new__(cls, total)
        obj.total = total
        obj.screens = screens
        obj.slides = slides
        obj.sprites = sprites
        return obj

    def __repr__(self) -> str:
        return f"<DumpResult total={self.total} screens={self.screens} slides={self.slides} sprites={self.sprites}>"


def decompress_stream(raw_bytes: bytes) -> Tuple[bytes, int]:
    """Unwraps single- or multi-layer LZ10 compression until raw binary data is reached.

    Returns:
        tuple[bytes, int]: (unwrapped_bytes, layer_count)
    """
    current_data = raw_bytes
    layer_count = 0

    while len(current_data) >= 4 and current_data[0] == 0x10:
        # Check if already a valid header without decompression
        if len(current_data) >= 8 and current_data[:4] in (b"NCG\x00", b"NCL\x00", b"NSC\x00"):
            break

        try:
            decomp = ndspy.lz10.decompress(current_data)
            layer_count += 1
            current_data = decomp
        except Exception:
            # Not a valid LZ10 stream or corrupt, stop unwrapping
            break

    return current_data, layer_count


def compress_stream(data: bytes, layers: int = 1) -> bytes:
    """Applies `layers` passes of LZ10 compression to data."""
    result = data
    for _ in range(layers):
        result = ndspy.lz10.compress(result)
    return result


def parse_ncl_header(data: bytes) -> Dict[str, Any]:
    """Parses an NCL palette file header (8 bytes)."""
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
    """Builds an 8-byte NCL palette header."""
    return struct.pack("<4sI", b"NCL\x00", color_count)


def parse_ncg_header(data: bytes) -> Dict[str, Any]:
    """Parses an NCG character/tile file header (8 bytes)."""
    if len(data) < 8:
        raise GraphicsEngineError(f"NCG data too short: {len(data)} bytes")
    magic, tile_count = struct.unpack("<4sI", data[:8])
    if magic != b"NCG\x00":
        raise GraphicsEngineError(f"Invalid NCG magic: {magic!r}")
    return {
        "magic": magic,
        "tile_count": tile_count,
        "header_size": 8,
    }


def build_ncg_header(tile_count: int) -> bytes:
    """Builds an 8-byte NCG tile header."""
    return struct.pack("<4sI", b"NCG\x00", tile_count)


def parse_nsc_header(data: bytes) -> Dict[str, Any]:
    """Parses an NSC screen tilemap header (12 bytes)."""
    if len(data) < 12:
        raise GraphicsEngineError(f"NSC data too short: {len(data)} bytes")
    magic, flags = struct.unpack("<4sI", data[:8])
    if magic != b"NSC\x00":
        raise GraphicsEngineError(f"Invalid NSC magic: {magic!r}")
    width_tiles, height_tiles = data[8], data[9]
    is_affine = ((flags >> 16) & 0xFF) == 1
    return {
        "magic": magic,
        "flags": flags,
        "width_tiles": width_tiles,
        "height_tiles": height_tiles,
        "is_affine": is_affine,
        "header_size": 12,
    }


def build_nsc_header(width_tiles: int, height_tiles: int, flags: int = 0x00030000) -> bytes:
    """Builds a 12-byte NSC screen tilemap header."""
    return struct.pack("<4sIBBH", b"NSC\x00", flags, width_tiles, height_tiles, 0)


def dump_screen(
    ncg_path: str,
    ncl_path: str,
    nsc_path: str,
    out_png_path: str,
    out_json_path: str,
) -> Dict[str, Any]:
    """Extracts a background screen triplet into an editable PNG image and metadata JSON."""
    import json

    with open(ncl_path, "rb") as f:
        ncl_data = f.read()
    with open(ncg_path, "rb") as f:
        ncg_data = f.read()
    with open(nsc_path, "rb") as f:
        nsc_data = f.read()

    ncl_decomp, ncl_layers = decompress_stream(ncl_data)
    ncg_decomp, ncg_layers = decompress_stream(ncg_data)
    nsc_decomp, nsc_layers = decompress_stream(nsc_data)

    ncl_info = parse_ncl_header(ncl_decomp)
    ncg_info = parse_ncg_header(ncg_decomp)
    nsc_info = parse_nsc_header(nsc_decomp)

    # Detect 8bpp vs 4bpp
    raw_tile_cnt = ncg_info["tile_count"]
    high_flag = (raw_tile_cnt >> 16) & 0xFFFF
    is_8bpp = (high_flag == 1)
    tile_count = (raw_tile_cnt & 0xFFFF) if is_8bpp else raw_tile_cnt
    fmt = ndspy.graphics2D.ImageFormat.I8 if is_8bpp else ndspy.graphics2D.ImageFormat.I4

    palette = ndspy.color.loadPalette(ncl_decomp[8:])
    # Ensure palette has at least 256 entries to prevent IndexError in ndspy
    while len(palette) < 256:
        palette.append((0, 0, 0, 0))

    tiles = ndspy.graphics2D.loadImageTiles(ncg_decomp[8:], fmt)
    w_tiles = nsc_info["width_tiles"]
    h_tiles = nsc_info["height_tiles"]
    is_affine = nsc_info.get("is_affine", False)

    if is_affine:
        tile_bytes_needed = w_tiles * h_tiles
        tilemap = ndspy.graphics2D.loadTilemapTiles(
            nsc_decomp[12 : 12 + tile_bytes_needed], ndspy.graphics2D.TilemapFormat.I8
        )
        extra_data = nsc_decomp[12 + tile_bytes_needed :].hex()
    else:
        tile_bytes_needed = w_tiles * h_tiles * 2
        tilemap = ndspy.graphics2D.loadTilemapTiles(
            nsc_decomp[12 : 12 + tile_bytes_needed], ndspy.graphics2D.TilemapFormat.I10H1V1P4
        )
        extra_data = nsc_decomp[12 + tile_bytes_needed :].hex()

    # Pad missing tiles with blank tiles if referenced in tilemap
    if tilemap:
        max_idx = max(t.tileNum for t in tilemap)
        if max_idx >= len(tiles):
            blank_tile = ndspy.graphics2D.ImageTile(b"\x00" * (64 if is_8bpp else 32), fmt)
            tiles.extend([blank_tile] * (max_idx + 1 - len(tiles)))

    # In 8bpp mode, reset paletteNum so it doesn't offset into missing sub-palettes
    if is_8bpp:
        for t in tilemap:
            t.paletteNum = 0

    img = ndspy.graphics2D.renderTilemapTilesAsImage(tilemap, tiles, palette, w_tiles)

    os.makedirs(os.path.dirname(os.path.abspath(out_png_path)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_json_path)), exist_ok=True)
    img.save(out_png_path)

    meta = {
        "is_8bpp": is_8bpp,
        "is_affine": is_affine,
        "tile_count": tile_count,
        "raw_tile_count": raw_tile_cnt,
        "width_tiles": w_tiles,
        "height_tiles": h_tiles,
        "width_px": w_tiles * 8,
        "height_px": h_tiles * 8,
        "flags": nsc_info["flags"],
        "extra_data": extra_data,
        "color_count": ncl_info["color_count"],
        "ncg_layers": ncg_layers,
        "ncl_layers": ncl_layers,
        "nsc_layers": nsc_layers,
        "ncg_path": ncg_path,
        "ncl_path": ncl_path,
        "nsc_path": nsc_path,
    }

    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return meta


def resolve_rom_directory(rom_data_dir: str, target: str) -> str:
    """Resolves a target directory path that may be relative to rom_data_dir, absolute, or standalone."""
    if os.path.isdir(target):
        return os.path.abspath(target)
    cand = os.path.join(rom_data_dir, target)
    if os.path.isdir(cand):
        return os.path.abspath(cand)
    raise GraphicsEngineError(f"Directory not found: '{target}' (checked '{target}' and '{cand}')")


def find_shared_nsc_for_tiles(ncg_path: str) -> Optional[str]:
    """Finds a shared _nsc.bin template for illustration/slide tilesets in a folder."""
    import glob
    d = os.path.dirname(ncg_path)
    b = os.path.basename(ncg_path)

    # Specific prefixes
    if b.startswith("bg_name_back_slv"):
        cand = os.path.join(d, "bg_name_back_slv_nsc.bin")
        if os.path.isfile(cand):
            return cand
    if b.startswith("bg_name_back_"):
        cand = os.path.join(d, "bg_name_back_nsc.bin")
        if os.path.isfile(cand):
            return cand

    # Known bg_pct templates in directory
    for template in ("bg_pct_illust_nsc.bin", "bg_pct_end_nsc.bin", "bg_pct_skill_nsc.bin"):
        cand = os.path.join(d, template)
        if os.path.isfile(cand):
            return cand

    # Single NSC in directory without direct NCG companion
    dir_nscs = glob.glob(os.path.join(d, "*_nsc.bin"))
    if len(dir_nscs) == 1:
        single_nsc = dir_nscs[0]
        if not os.path.isfile(single_nsc.replace("_nsc.bin", "_ncg.bin")):
            return single_nsc

    return None


def find_palette_for_screen(nsc_path: str) -> Optional[str]:
    """Finds matching _ncl.bin palette for a given _nsc.bin screen."""
    import glob
    stem = nsc_path[:-8]
    direct = stem + "_ncl.bin"
    if os.path.isfile(direct):
        return direct

    dir_path = os.path.dirname(nsc_path)
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


def find_tiles_for_screen(nsc_path: str) -> Optional[str]:
    """Finds matching _ncg.bin tiles for a given _nsc.bin screen."""
    stem = nsc_path[:-8]
    direct = stem + "_ncg.bin"
    if os.path.isfile(direct):
        return direct

    dir_path = os.path.dirname(nsc_path)
    base = os.path.basename(stem)

    # 1. Hyphen / underscore normalization (e.g. wall2-256_nsc.bin -> wall2_256_ncg.bin)
    for cand_name in (base.replace("-", "_") + "_ncg.bin", base.replace("_", "-") + "_ncg.bin"):
        cand = os.path.join(dir_path, cand_name)
        if os.path.isfile(cand):
            return cand

    # 2. Stripping double underscores or trailing underscores (e.g. 60_font4_nsc.bin -> 60_font4__ncg.bin)
    for cand_name in (base.rstrip("_") + "__ncg.bin", base.rstrip("_") + "_ncg.bin"):
        cand = os.path.join(dir_path, cand_name)
        if os.path.isfile(cand):
            return cand

    # 3. Special screens mapping
    special_map = {
        "kouscr": "07_koucgx_ncg.bin",
        "etscr": "14_etcgx__ncg.bin",
        "metescr": "15_metecgx_ncg.bin",
        "lasscr": "35_lascgx_ncg.bin",
        "kokscr": "39_kokcgx_ncg.bin",
        "wmscr": "43_wmcgx_ncg.bin",
        "font4": "60_font4__ncg.bin",
        "moonscr": "61_mooncgx_ncg.bin",
        "kumscr": "66_kumcgx_ncg.bin",
        "earsc": "EARCG_ncg.bin",
    }
    for key, val in special_map.items():
        if key in base:
            cand = os.path.join(dir_path, val)
            if os.path.isfile(cand):
                return cand

    # 4. Ending clear window
    if "bg_win_clear" in base:
        cand_obj = os.path.join(dir_path, base.replace("bg_win_clear_dwn", "obj_win_clear") + "_ncg.bin")
        if os.path.isfile(cand_obj):
            return cand_obj

    # 5. Menu background styles fallback
    if base.startswith("bg_back_"):
        cand_bg1 = os.path.join(dir_path, "bg_back_1_ncg.bin")
        if os.path.isfile(cand_bg1):
            return cand_bg1

    # 6. Prefix matching
    parts = base.split("_")
    parts_no_pos = [p for p in parts if p not in ("up", "down", "dwn")]
    if parts_no_pos != parts:
        cand_pos = os.path.join(dir_path, "_".join(parts_no_pos) + "_ncg.bin")
        if os.path.isfile(cand_pos):
            return cand_pos

    for i in range(len(parts), 0, -1):
        cand = os.path.join(dir_path, "_".join(parts[:i]) + "_ncg.bin")
        if os.path.isfile(cand):
            return cand

    return None


def dump_all_screens(
    rom_data_dir: str,
    output_image_dir: str,
    category: Optional[str] = None,
    dump_all: bool = False,
    directory: Optional[str] = None,
) -> DumpResult:
    """Scans rom_data_dir for screen tilemaps, slide sequences, and sprites and dumps them to PNG + JSON.

    Args:
        rom_data_dir: Path to extracted NitroFS data directory.
        output_image_dir: Output base directory (e.g. 'extracted image').
        category: Optional category filter (e.g. 'title', 'Ending', 'menu') [deprecated, use directory].
        dump_all: If True, dumps every found graphic across all folders.
        directory: Optional directory or subdirectory to dump (e.g. 'menu', 'menu/obj', 'title/bg').

    Returns:
        DumpResult: Object behaving as int total count of dumped graphics, with .screens, .slides, .sprites.
    """
    import glob
    import json

    target_dir_arg = directory or category
    search_dirs = []

    if target_dir_arg:
        search_dirs.append(resolve_rom_directory(rom_data_dir, target_dir_arg))
    elif dump_all:
        search_dirs.append(os.path.abspath(rom_data_dir))
    else:
        default_categories = ["title", "Ending", "menu", "minimap", "special"]
        for c in default_categories:
            p = os.path.join(rom_data_dir, c)
            if os.path.isdir(p):
                search_dirs.append(os.path.abspath(p))

    dumped_screens = 0
    dumped_slides = 0
    dumped_sprites = 0
    dumped_ncg_paths = set()

    # 1. Screen tilemaps (*_nsc.bin)
    nsc_files: List[str] = []
    for d in search_dirs:
        nsc_files.extend(glob.glob(os.path.join(d, "**", "*_nsc.bin"), recursive=True))
    nsc_files = sorted(list(set(nsc_files)))

    for nsc in nsc_files:
        ncg = find_tiles_for_screen(nsc)
        ncl = find_palette_for_screen(nsc)
        if not ncg or not ncl:
            continue

        rel = os.path.relpath(nsc, rom_data_dir)
        rel_stem = rel[:-8]  # strip '_nsc.bin'
        out_png = os.path.join(output_image_dir, rel_stem + ".png")
        out_json = os.path.join(output_image_dir, rel_stem + ".json")

        try:
            dump_screen(ncg, ncl, nsc, out_png, out_json)
            dumped_screens += 1
            dumped_ncg_paths.add(os.path.abspath(ncg))
        except Exception as e:
            print(f"Warning: Failed to dump {rel}: {e}")

    # 2. Shared-NSC slide collections (*_ncg.bin using a shared template *_nsc.bin)
    ncg_files: List[str] = []
    for d in search_dirs:
        ncg_files.extend(glob.glob(os.path.join(d, "**", "*_ncg.bin"), recursive=True))
    ncg_files = sorted(list(set(ncg_files)))

    for ncg in ncg_files:
        if os.path.abspath(ncg) in dumped_ncg_paths:
            continue

        shared_nsc = find_shared_nsc_for_tiles(ncg)
        if not shared_nsc:
            continue

        stem_ncl = ncg[:-8] + "_ncl.bin"
        if os.path.isfile(stem_ncl):
            ncl = stem_ncl
        else:
            ncl = find_palette_for_screen(shared_nsc)

        if not ncl or not os.path.isfile(ncl):
            continue

        rel = os.path.relpath(ncg, rom_data_dir)
        rel_stem = rel[:-8]  # strip '_ncg.bin'
        out_png = os.path.join(output_image_dir, rel_stem + ".png")
        out_json = os.path.join(output_image_dir, rel_stem + ".json")

        try:
            meta = dump_screen(ncg, ncl, shared_nsc, out_png, out_json)
            meta["is_shared_nsc"] = True
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
            dumped_slides += 1
            dumped_ncg_paths.add(os.path.abspath(ncg))
        except Exception as e:
            print(f"Warning: Failed to dump slide {rel}: {e}")

    # 3. Sprites (*.NCGR / *.ncgr)
    ncgr_files: List[str] = []
    for d in search_dirs:
        ncgr_files.extend(glob.glob(os.path.join(d, "**", "*.ncgr"), recursive=True))
        ncgr_files.extend(glob.glob(os.path.join(d, "**", "*.NCGR"), recursive=True))
    ncgr_files = sorted(list(set(ncgr_files)))

    for ncgr in ncgr_files:
        rel = os.path.relpath(ncgr, rom_data_dir)
        rel_stem = os.path.splitext(rel)[0]
        out_png = os.path.join(output_image_dir, rel_stem + ".png")
        out_json = os.path.join(output_image_dir, rel_stem + ".json")

        nclr = find_palette_for_sprite(ncgr)
        ncer = find_cell_bank_for_sprite(ncgr)

        try:
            dump_ncgr_sprite(ncgr, nclr, out_png, out_json, ncer_path=ncer)
            dumped_sprites += 1
        except Exception as e:
            print(f"Warning: Failed to dump sprite {rel}: {e}")

    total = dumped_screens + dumped_slides + dumped_sprites
    return DumpResult(total, screens=dumped_screens, slides=dumped_slides, sprites=dumped_sprites)



def pad_to_alignment(data: bytes, align: int = 4) -> bytes:
    """Pads byte buffer to specified alignment boundary with zeros."""
    rem = len(data) % align
    if rem:
        data += b"\x00" * (align - rem)
    return data


def deduplicate_tiles(
    tiles_8x8: List[List[int]],
    is_8bpp: bool,
    allow_flips: bool = True,
) -> Tuple[List[List[int]], List[Tuple[int, bool, bool, int]]]:
    """Deduplicates 8x8 pixel tiles and returns unique tiles + tilemap placement parameters.

    Returns:
        tuple: (unique_tiles, tile_placements)
        where each placement is (tile_index, h_flip, v_flip, palette_num)
    """
    unique_tiles: List[List[int]] = []
    tile_lookup: Dict[Tuple[int, ...], Tuple[int, bool, bool]] = {}
    placements: List[Tuple[int, bool, bool, int]] = []

    for tile_px in tiles_8x8:
        if is_8bpp:
            pal_num = 0
            norm_px = list(tile_px)
        else:
            # Determine palette bank for 4bpp (indices 0..15)
            non_zero = [p for p in tile_px if p != 0]
            if not non_zero:
                pal_num = 0
                norm_px = [0] * 64
            else:
                from collections import Counter

                banks = [p // 16 for p in non_zero]
                pal_num = Counter(banks).most_common(1)[0][0]
                norm_px = []
                for p in tile_px:
                    if p == 0:
                        norm_px.append(0)
                    elif p // 16 == pal_num:
                        norm_px.append(p % 16)
                    else:
                        norm_px.append(0)

        t_norm = tuple(norm_px)
        if t_norm in tile_lookup:
            idx, hf, vf = tile_lookup[t_norm]
        else:
            idx = len(unique_tiles)
            max_tiles = 256 if not allow_flips else 1024
            if idx >= max_tiles:
                raise TilePoolOverflowError(
                    f"Screen exceeded maximum allowable unique tiles ({max_tiles}). Got {idx + 1} unique tiles."
                )
            unique_tiles.append(norm_px)

            tile_lookup[t_norm] = (idx, False, False)
            if allow_flips:
                tile_2d = [norm_px[i * 8 : (i + 1) * 8] for i in range(8)]
                t_h = tuple(p for row in tile_2d for p in reversed(row))
                t_v = tuple(p for row in reversed(tile_2d) for p in row)
                t_hv = tuple(p for row in reversed(tile_2d) for p in reversed(row))

                if t_h not in tile_lookup:
                    tile_lookup[t_h] = (idx, True, False)
                if t_v not in tile_lookup:
                    tile_lookup[t_v] = (idx, False, True)
                if t_hv not in tile_lookup:
                    tile_lookup[t_hv] = (idx, True, True)

            hf, vf = False, False

        placements.append((idx, hf, vf, pal_num))

    return unique_tiles, placements


def build_screen(
    png_path: str,
    meta_json_path: str,
    out_ncg_path: str,
    out_ncl_path: str,
    out_nsc_path: str,
) -> Dict[str, Any]:
    """Rebuilds NCG, NCL, NSC binaries from an edited PNG and metadata JSON."""
    import json
    from PIL import Image

    with open(meta_json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    is_8bpp = meta["is_8bpp"]
    w_tiles = meta["width_tiles"]
    h_tiles = meta["height_tiles"]
    flags = meta["flags"]
    is_affine = meta.get("is_affine", False) or (((flags >> 16) & 0xFF) == 1)

    # Load original palette from meta or ncl_path
    with open(meta["ncl_path"], "rb") as f:
        ncl_data = f.read()
    ncl_decomp, _ = decompress_stream(ncl_data)
    palette = ndspy.color.loadPalette(ncl_decomp[8:])

    # Prepare palette lookup for RGB colors
    pal_rgb = [(c[0] * 255 // 31, c[1] * 255 // 31, c[2] * 255 // 31) for c in palette]
    color_map: Dict[Tuple[int, int, int], int] = {}

    def get_best_color(rgba: Tuple[int, int, int, int]) -> int:
        if len(rgba) >= 4 and rgba[3] < 128:
            return 0
        rgb = (rgba[0], rgba[1], rgba[2])
        if rgb in color_map:
            return color_map[rgb]
        best_dist = float("inf")
        best_idx = 0
        for idx, c in enumerate(pal_rgb):
            dr = rgb[0] - c[0]
            dg = rgb[1] - c[1]
            db = rgb[2] - c[2]
            dist = dr * dr + dg * dg + db * db
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        color_map[rgb] = best_idx
        return best_idx

    with Image.open(png_path) as orig_img:
        img = orig_img.convert("RGBA")

    # Slice into 8x8 tiles
    tiles_8x8: List[List[int]] = []
    for ty in range(h_tiles):
        for tx in range(w_tiles):
            tile_pixels = []
            for y in range(8):
                for x in range(8):
                    px_x = tx * 8 + x
                    px_y = ty * 8 + y
                    if px_x < img.width and px_y < img.height:
                        px = img.getpixel((px_x, px_y))
                        tile_pixels.append(get_best_color(px))
                    else:
                        tile_pixels.append(0)
            tiles_8x8.append(tile_pixels)

    unique_tiles, placements = deduplicate_tiles(
        tiles_8x8, is_8bpp=is_8bpp, allow_flips=not is_affine
    )

    # Construct ImageTiles and TilemapTiles
    fmt = ndspy.graphics2D.ImageFormat.I8 if is_8bpp else ndspy.graphics2D.ImageFormat.I4
    img_tiles = [ndspy.graphics2D.ImageTile.fromPixels(px, fmt) for px in unique_tiles]

    if is_affine:
        tilemap_tiles = [
            ndspy.graphics2D.TilemapTile.fromParameters(
                idx,
                format=ndspy.graphics2D.TilemapFormat.I8,
            )
            for (idx, hf, vf, pal_num) in placements
        ]
    else:
        tilemap_tiles = [
            ndspy.graphics2D.TilemapTile.fromParameters(
                idx,
                format=ndspy.graphics2D.TilemapFormat.I10H1V1P4,
                hFlip=hf,
                vFlip=vf,
                paletteNum=pal_num,
            )
            for (idx, hf, vf, pal_num) in placements
        ]

    # Save tile binary data
    tiles_binary = ndspy.graphics2D.saveImageTiles(img_tiles)
    tilemap_binary = ndspy.graphics2D.saveTilemapTiles(tilemap_tiles)
    if meta.get("extra_data"):
        tilemap_binary += bytes.fromhex(meta["extra_data"])
    palette_binary = ncl_decomp[8:]

    # Headers
    if is_8bpp:
        raw_tile_count = (1 << 16) | (len(unique_tiles) & 0xFFFF)
    else:
        raw_tile_count = len(unique_tiles)

    ncg_payload = build_ncg_header(raw_tile_count) + tiles_binary
    nsc_payload = build_nsc_header(w_tiles, h_tiles, flags=flags) + tilemap_binary
    ncl_payload = build_ncl_header(meta["color_count"]) + palette_binary

    # 4-byte alignment
    ncg_payload = pad_to_alignment(ncg_payload, 4)
    nsc_payload = pad_to_alignment(nsc_payload, 4)
    ncl_payload = pad_to_alignment(ncl_payload, 4)

    # Multi-layer compression
    ncg_final = compress_stream(ncg_payload, layers=meta.get("ncg_layers", 0))
    nsc_final = compress_stream(nsc_payload, layers=meta.get("nsc_layers", 0))
    ncl_final = compress_stream(ncl_payload, layers=meta.get("ncl_layers", 0))

    os.makedirs(os.path.dirname(os.path.abspath(out_ncg_path)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_ncl_path)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_nsc_path)), exist_ok=True)

    with open(out_ncg_path, "wb") as f:
        f.write(ncg_final)
    with open(out_ncl_path, "wb") as f:
        f.write(ncl_final)
    with open(out_nsc_path, "wb") as f:
        f.write(nsc_final)

    return {
        "unique_tiles": len(unique_tiles),
        "total_screen_tiles": len(tiles_8x8),
        "is_8bpp": is_8bpp,
        "width_tiles": w_tiles,
        "height_tiles": h_tiles,
    }


def build_all_screens(
    image_dir: str,
    meta_dir: str,
    target_rom_data_dir: str,
    sub_dir: Optional[str] = None,
) -> int:
    """Scans image_dir for translated PNGs and rebuilds them into target_rom_data_dir.

    Args:
        image_dir: Source folder of translated PNGs (e.g. 'translated image').
        meta_dir: Folder containing metadata JSONs from original dump (e.g. 'extracted image').
        target_rom_data_dir: Target NitroFS data directory (e.g. 'extracted rom/data').
        sub_dir: Optional subfolder within image_dir to rebuild.

    Returns:
        int: Number of screens rebuilt.
    """
    import glob

    built_count = 0
    search_root = os.path.join(image_dir, sub_dir) if sub_dir else image_dir
    png_files = glob.glob(os.path.join(search_root, "**", "*.png"), recursive=True)

    for png_path in sorted(png_files):
        rel = os.path.relpath(png_path, image_dir)
        rel_stem = os.path.splitext(rel)[0]

        meta_json_path = os.path.join(meta_dir, rel_stem + ".json")
        if not os.path.isfile(meta_json_path):
            print(f"Warning: Metadata JSON not found for {rel}: {meta_json_path}")
            continue

        with open(meta_json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        if meta.get("format") == "NCGR":
            out_ncgr = os.path.join(target_rom_data_dir, rel_stem + ".NCGR")
            try:
                build_ncgr_sprite(png_path, meta_json_path, out_ncgr)
                if meta.get("is_cell_sheet") and meta.get("ncer_path"):
                    out_ncer = os.path.join(target_rom_data_dir, rel_stem + ".NCER")
                    rebuild_ncer_from_metadata(meta_json_path, out_ncer)
                built_count += 1
            except Exception as e:
                print(f"Warning: Failed to build NCGR sprite {rel}: {e}")
            continue

        out_ncg = os.path.join(target_rom_data_dir, rel_stem + "_ncg.bin")
        out_ncl = os.path.join(target_rom_data_dir, rel_stem + "_ncl.bin")
        if meta.get("is_shared_nsc") and "nsc_path" in meta:
            rel_nsc = os.path.basename(meta["nsc_path"])
            out_nsc = os.path.join(os.path.dirname(out_ncg), rel_nsc)
        else:
            out_nsc = os.path.join(target_rom_data_dir, rel_stem + "_nsc.bin")

        try:
            build_screen(png_path, meta_json_path, out_ncg, out_ncl, out_nsc)
            built_count += 1
        except Exception as e:
            print(f"Warning: Failed to build {rel}: {e}")

    return built_count


def parse_nclr_palette(data: bytes) -> List[int]:
    """Parses an NCLR binary file and returns flat list of RGB values [r0, g0, b0, ...]."""
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

    colors: List[int] = []
    for i in range(0, len(pal_raw), 2):
        c = struct.unpack("<H", pal_raw[i : i + 2])[0]
        r = (c & 0x1F) * 255 // 31
        g = ((c >> 5) & 0x1F) * 255 // 31
        b = ((c >> 10) & 0x1F) * 255 // 31
        colors.extend([r, g, b])

    while len(colors) < 256 * 3:
        colors.extend([0, 0, 0])

    return colors[: 256 * 3]


def find_palette_for_sprite(ncgr_path: str) -> Optional[str]:
    """Finds matching NCLR or NCL palette for a given NCGR sprite file.

    Args:
        ncgr_path: Path to the target NCGR file.

    Returns:
        Optional[str]: Path to matching palette file if found, else None.
    """
    stem = os.path.splitext(ncgr_path)[0]
    dir_path = os.path.dirname(ncgr_path)
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

    # 3. Menu window components (obj_win_*, obj_fld_win*, obj_soroll*)
    if base.startswith("obj_win_") or base.startswith("obj_fld_win") or base.startswith("obj_soroll"):
        cand_win = os.path.join(dir_path, "win_ncl.bin")
        if os.path.isfile(cand_win):
            return cand_win
        cand_plt = os.path.join(os.path.dirname(dir_path), "plt", "win_1.NCLR")
        if os.path.isfile(cand_plt):
            return cand_plt

    # 4. Face portraits (face_00..face_07 -> face.NCLR)
    if base.startswith("face"):
        cand = os.path.join(dir_path, "face.NCLR")
        if os.path.isfile(cand):
            return cand

    # 5. Slave names (obj_slv_name_00.. -> obj_slv_name.NCLR)
    if base.startswith("obj_slv_name"):
        cand = os.path.join(dir_path, "obj_slv_name.NCLR")
        if os.path.isfile(cand):
            return cand

    # 6. Character icons (chara -> chara_00.NCLR, chricon -> bticon.NCLR or chara_00.NCLR)
    if base.startswith("chara"):
        cand = os.path.join(dir_path, "chara_00.NCLR")
        if os.path.isfile(cand):
            return cand
    if base == "chricon":
        cand = os.path.join(dir_path, "bticon.NCLR")
        if os.path.isfile(cand):
            return cand

    # 7. Cursors (btcursor, cursor_*, etc.)
    if "cursor" in base:
        for cand_name in ("cursor_1.NCLR", "btcursor.NCLR"):
            cand = os.path.join(dir_path, cand_name)
            if os.path.isfile(cand):
                return cand

    # 8. icon_bike -> icon.NCLR
    if base == "icon_bike":
        cand = os.path.join(dir_path, "icon.NCLR")
        if os.path.isfile(cand):
            return cand

    return None


OAM_SHAPES = {
    0: {0: (8, 8), 1: (16, 16), 2: (32, 32), 3: (64, 64)},
    1: {0: (16, 8), 1: (32, 8), 2: (32, 16), 3: (64, 32)},
    2: {0: (8, 16), 1: (8, 32), 2: (16, 32), 3: (32, 64)},
}

WH_TO_OAM_SHAPE_SIZE = {
    (w, h): (shape, size_code)
    for shape, sizes in OAM_SHAPES.items()
    for size_code, (w, h) in sizes.items()
}


def find_cell_bank_for_sprite(ncgr_path: str) -> Optional[str]:
    """Finds matching NCER cell bank for a given NCGR sprite file.

    Args:
        ncgr_path: Path to the target NCGR file.

    Returns:
        Optional[str]: Path to matching NCER file if found, else None.
    """
    stem = os.path.splitext(ncgr_path)[0]
    dir_path = os.path.dirname(ncgr_path)
    base = os.path.basename(stem)

    # 1. Direct match with exact or lowercase extension
    for ext in (".NCER", ".ncer"):
        cand = stem + ext
        if os.path.isfile(cand):
            return cand

    # 2. Language variant fallback (e.g. icon_fra.NCGR -> icon.NCER)
    for lang in ("_fra", "_eng"):
        if base.endswith(lang):
            base_cand = os.path.join(dir_path, base[: -len(lang)] + ".NCER")
            if os.path.isfile(base_cand):
                return base_cand

    return None


def _is_oam_tile_occluded(oams: List[Dict[str, Any]], k: int, tx: int, ty: int) -> bool:
    """Checks whether the tile at (tx, ty) of oams[k] overlaps with any other OAM in the same cell."""
    if len(oams) <= 1:
        return False
    o_k = oams[k]
    tx0 = o_k["x"] + tx * 8
    ty0 = o_k["y"] + ty * 8
    tx1 = tx0 + 8
    ty1 = ty0 + 8
    for j in range(len(oams)):
        if j == k:
            continue
        o_j = oams[j]
        jx0, jy0 = o_j["x"], o_j["y"]
        jx1, jy1 = jx0 + o_j["w"], jy0 + o_j["h"]
        if not (tx1 <= jx0 or jx1 <= tx0 or ty1 <= jy0 or jy1 <= ty0):
            return True
    return False


def dump_ncgr_sprite(
    ncgr_path: str,
    nclr_path: Optional[str],
    out_png_path: str,
    out_json_path: str,
    ncer_path: Optional[str] = None,
    tiles_per_row: int = 16,
) -> Dict[str, Any]:
    """Extracts an NCGR sprite character container into an editable PNG and metadata JSON.

    If an NCER companion cell bank is found or specified, exports assembled 2D cell sprites
    without 1D tile slicing distortions or alignment padding artifacts.
    """
    import json
    import re
    from PIL import Image

    with open(ncgr_path, "rb") as f:
        raw = f.read()

    decomp, comp_layers = decompress_stream(raw)
    if decomp[:4] != b"RGCN":
        raise GraphicsEngineError(f"Invalid NCGR magic: {decomp[:4]!r}")

    rahc_idx = decomp.find(b"RAHC")
    if rahc_idx == -1:
        raise GraphicsEngineError("RAHC block not found in NCGR")

    magic, block_size, tiles_y, tiles_x, depth_raw, mapping, flags, data_size, data_offset = (
        struct.unpack("<4sIHHIIIII", decomp[rahc_idx : rahc_idx + 32])
    )
    is_8bpp = (depth_raw == 4)
    tile_bytes = 64 if is_8bpp else 32

    tiles_start = rahc_idx + 8 + data_offset
    char_size = data_size
    if char_size == 0 or tiles_start + char_size > len(decomp):
        tiles_data = decomp[tiles_start:]
    else:
        tiles_data = decomp[tiles_start : tiles_start + char_size]

    num_tiles = len(tiles_data) // tile_bytes
    if num_tiles == 0:
        raise GraphicsEngineError("No tiles found in NCGR")

    # Detect base_pal (0-indexed integer) from the file name
    base = os.path.basename(ncgr_path)
    m_face = re.search(r"face_(\d+)", base)
    m_win = re.search(r"obj_win_.*_(\d+)", base)
    m_slv = re.search(r"obj_slv_name_(\d+)", base)
    m_soroll = re.search(r"obj_soroll_(\d+)", base)

    if m_face:
        base_pal = int(m_face.group(1))
    elif m_win:
        base_pal = max(0, int(m_win.group(1)) - 1)
    elif m_slv:
        base_pal = int(m_slv.group(1))
    elif m_soroll:
        base_pal = max(0, int(m_soroll.group(1)) - 1)
    else:
        base_pal = 0

    # Load palette
    if nclr_path and os.path.isfile(nclr_path):
        with open(nclr_path, "rb") as f:
            pal_bytes = f.read()
        colors = parse_nclr_palette(pal_bytes)
    else:
        colors = []
        for i in range(256):
            v = min(255, i * 255 // (15 if not is_8bpp else 255))
            colors.extend([v, v, v])

    if ncer_path is None:
        ncer_path = find_cell_bank_for_sprite(ncgr_path)

    # Attempt NCER cell-aware export if NCER file is available
    if ncer_path and os.path.isfile(ncer_path):
        try:
            ncer_decomp, _ = decompress_stream(open(ncer_path, "rb").read())
            cebk_idx = ncer_decomp.find(b"KBEC")
            if cebk_idx == -1:
                cebk_idx = ncer_decomp.find(b"CEBK")
            if cebk_idx != -1:
                num_cells = struct.unpack("<H", ncer_decomp[cebk_idx + 8 : cebk_idx + 10])[0]
                cell_data_offset = struct.unpack("<I", ncer_decomp[cebk_idx + 12 : cebk_idx + 16])[0]
                mapping_mode = struct.unpack("<I", ncer_decomp[cebk_idx + 16 : cebk_idx + 20])[0]
                cell_start = cebk_idx + 8 + cell_data_offset
                oam_base = cell_start + num_cells * 8
                tile_multiplier = 1 << mapping_mode

                labels = []
                labl_idx = ncer_decomp.find(b"LBAL")
                if labl_idx == -1:
                    labl_idx = ncer_decomp.find(b"LABL")
                if labl_idx != -1 and num_cells > 0:
                    labl_size = struct.unpack("<I", ncer_decomp[labl_idx + 4 : labl_idx + 8])[0]
                    labl_payload = ncer_decomp[labl_idx + 8 : labl_idx + labl_size]
                    if len(labl_payload) >= num_cells * 4:
                        offsets = [
                            struct.unpack("<I", labl_payload[i * 4 : (i + 1) * 4])[0]
                            for i in range(num_cells)
                        ]
                        str_base = num_cells * 4
                        for off in offsets:
                            if str_base + off < len(labl_payload):
                                end = labl_payload.find(b"\x00", str_base + off)
                                if end == -1:
                                    end = len(labl_payload)
                                labels.append(
                                    labl_payload[str_base + off : end].decode("latin1", errors="replace")
                                )
                            else:
                                labels.append("")

                components = []
                covered_tiles = set()

                for i in range(num_cells):
                    n_oam, attr, oam_off = struct.unpack(
                        "<HHI", ncer_decomp[cell_start + i * 8 : cell_start + (i + 1) * 8]
                    )
                    oams = []
                    for o in range(n_oam):
                        pos = oam_base + oam_off + o * 6
                        a0, a1, a2 = struct.unpack("<HHH", ncer_decomp[pos : pos + 6])
                        y = a0 & 0xFF
                        if y >= 128:
                            y -= 256
                        shape = (a0 >> 14) & 3
                        x = a1 & 0x1FF
                        if x >= 256:
                            x -= 512
                        size_code = (a1 >> 14) & 3
                        w, h = OAM_SHAPES.get(shape, {}).get(size_code, (8, 8))
                        raw_tile = (a2 & 0x3FF) * tile_multiplier
                        pal = (a2 >> 12) & 0xF
                        rot = (a0 >> 8) & 1
                        hflip = (a1 >> 12) & 1 if not rot else 0
                        vflip = (a1 >> 13) & 1 if not rot else 0
                        oams.append({
                            "x": x,
                            "y": y,
                            "w": w,
                            "h": h,
                            "tile": raw_tile,
                            "pal": pal,
                            "rot": rot,
                            "hflip": hflip,
                            "vflip": vflip,
                            "shape": shape,
                            "size_code": size_code,
                        })
                        num_t = (w * h) // 64
                        covered_tiles.update(range(raw_tile, raw_tile + num_t))

                    if oams:
                        min_x = min(o["x"] for o in oams)
                        min_y = min(o["y"] for o in oams)
                        max_x = max(o["x"] + o["w"] for o in oams)
                        max_y = max(o["y"] + o["h"] for o in oams)
                        comp_entry = {
                            "type": "cell",
                            "cell_idx": i,
                            "cell_attr": attr,
                            "min_x": min_x,
                            "min_y": min_y,
                            "width": max_x - min_x,
                            "height": max_y - min_y,
                            "oams": oams,
                        }
                        if i < len(labels):
                            comp_entry["label"] = labels[i]
                        components.append(comp_entry)

                # Extra component for uncovered tiles so all tiles can be edited
                uncovered_tiles = sorted([t for t in range(num_tiles) if t not in covered_tiles])
                if uncovered_tiles:
                    cols = min(len(uncovered_tiles), 16)
                    rows = (len(uncovered_tiles) + cols - 1) // cols
                    extra_oams = []
                    for idx, t in enumerate(uncovered_tiles):
                        c = idx % cols
                        r = idx // cols
                        extra_oams.append({
                            "x": c * 8,
                            "y": r * 8,
                            "w": 8,
                            "h": 8,
                            "tile": t,
                            "pal": 0,
                            "rot": 0,
                            "hflip": 0,
                            "vflip": 0,
                        })
                    components.append({
                        "type": "uncovered",
                        "cell_idx": -1,
                        "min_x": 0,
                        "min_y": 0,
                        "width": cols * 8,
                        "height": rows * 8,
                        "oams": extra_oams,
                    })

                # Determine padding byte from uncovered tiles if available
                padding_byte = 0xCC
                if uncovered_tiles:
                    sample_t = min(uncovered_tiles)
                    padding_byte = tiles_data[sample_t * tile_bytes]

                # 2D Shelf packing
                max_row_width = 256
                spacing = 8
                cur_x = spacing
                cur_y = spacing
                row_h = 0
                for comp in components:
                    cw = comp["width"]
                    ch = comp["height"]
                    if cur_x + cw + spacing > max_row_width:
                        cur_x = spacing
                        cur_y += row_h + spacing
                        row_h = 0
                    comp["canvas_x"] = cur_x
                    comp["canvas_y"] = cur_y
                    cur_x += cw + spacing
                    row_h = max(row_h, ch)

                sheet_w = max_row_width
                sheet_h = cur_y + row_h + spacing

                img = Image.new("P", (sheet_w, sheet_h), 0)
                img.putpalette(colors)

                # Record occluded tiles before rendering
                occluded_tiles: Dict[str, str] = {}
                for comp in components:
                    oams = comp["oams"]
                    for k, o in enumerate(oams):
                        w_t = o["w"] // 8
                        h_t = o["h"] // 8
                        for ty in range(h_t):
                            for tx in range(w_t):
                                if _is_oam_tile_occluded(oams, k, tx, ty):
                                    src_tx = (w_t - 1 - tx) if o.get("hflip", 0) else tx
                                    src_ty = (h_t - 1 - ty) if o.get("vflip", 0) else ty
                                    t_idx = o["tile"] + src_ty * w_t + src_tx
                                    if t_idx < num_tiles:
                                        occluded_tiles[str(t_idx)] = tiles_data[
                                            t_idx * tile_bytes : (t_idx + 1) * tile_bytes
                                        ].hex()

                # Render components (reverse order so OAM 0 is drawn on top)
                for comp in components:
                    cx = comp["canvas_x"]
                    cy = comp["canvas_y"]
                    min_x = comp["min_x"]
                    min_y = comp["min_y"]
                    for o in reversed(comp["oams"]):
                        ox = o["x"] - min_x
                        oy = o["y"] - min_y
                        w = o["w"]
                        h = o["h"]
                        w_t = w // 8
                        h_t = h // 8
                        raw_tile = o["tile"]
                        eff_pal = base_pal + o.get("pal", 0)
                        for ty in range(h_t):
                            for tx in range(w_t):
                                src_tx = (w_t - 1 - tx) if o.get("hflip", 0) else tx
                                src_ty = (h_t - 1 - ty) if o.get("vflip", 0) else ty
                                t_idx = raw_tile + src_ty * w_t + src_tx
                                if t_idx >= num_tiles:
                                    continue
                                t_bytes = tiles_data[t_idx * tile_bytes : (t_idx + 1) * tile_bytes]
                                for py in range(8):
                                    for px in range(8):
                                        src_px = (7 - px) if o.get("hflip", 0) else px
                                        src_py = (7 - py) if o.get("vflip", 0) else py
                                        if is_8bpp:
                                            val = t_bytes[src_py * 8 + src_px]
                                            if val != 0:
                                                px_pos = cx + ox + tx * 8 + px
                                                py_pos = cy + oy + ty * 8 + py
                                                if 0 <= px_pos < img.width and 0 <= py_pos < img.height:
                                                    img.putpixel((px_pos, py_pos), val)
                                        else:
                                            b = t_bytes[src_py * 4 + src_px // 2]
                                            val = (b >> 4) if (src_px % 2) else (b & 0x0F)
                                            if val != 0:
                                                if len(colors) // 3 > 16 and eff_pal > 0:
                                                    pixel_color = eff_pal * 16 + val
                                                else:
                                                    pixel_color = val
                                                px_pos = cx + ox + tx * 8 + px
                                                py_pos = cy + oy + ty * 8 + py
                                                if 0 <= px_pos < img.width and 0 <= py_pos < img.height:
                                                    img.putpixel((px_pos, py_pos), pixel_color)

                os.makedirs(os.path.dirname(os.path.abspath(out_png_path)), exist_ok=True)
                os.makedirs(os.path.dirname(os.path.abspath(out_json_path)), exist_ok=True)
                img.save(out_png_path, transparency=0)

                meta = {
                    "format": "NCGR",
                    "is_cell_sheet": True,
                    "is_8bpp": is_8bpp,
                    "num_tiles": num_tiles,
                    "sheet_width": sheet_w,
                    "sheet_height": sheet_h,
                    "compression_layers": comp_layers,
                    "ncgr_path": ncgr_path,
                    "ncer_path": ncer_path,
                    "nclr_path": nclr_path,
                    "base_palette_index": base_pal,
                    "occluded_tiles": occluded_tiles,
                    "padding_byte": padding_byte,
                    "mapping_mode": mapping_mode,
                    "labels": labels,
                    "components": components,
                    "header_bytes": decomp[:tiles_start].hex(),
                }

                with open(out_json_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)

                return meta
        except Exception as e:
            print(f"Warning: Failed NCER cell extraction for {ncgr_path}: {e}; falling back to raw tiles.")

    # Fallback: linear raw tile grid layout
    tiles_wide = min(num_tiles, tiles_per_row)
    tiles_high = (num_tiles + tiles_per_row - 1) // tiles_per_row

    img = Image.new("P", (tiles_wide * 8, tiles_high * 8), 0)
    img.putpalette(colors)

    for t_idx in range(num_tiles):
        tx = (t_idx % tiles_per_row) * 8
        ty = (t_idx // tiles_per_row) * 8
        t_data = tiles_data[t_idx * tile_bytes : (t_idx + 1) * tile_bytes]
        for py in range(8):
            for px in range(8):
                if is_8bpp:
                    val = t_data[py * 8 + px]
                else:
                    byte = t_data[py * 4 + px // 2]
                    val = (byte >> 4) if (px % 2) else (byte & 0x0F)
                    if len(colors) // 3 > 16 and base_pal > 0 and val != 0:
                        val = base_pal * 16 + val
                px_pos = tx + px
                py_pos = ty + py
                if 0 <= px_pos < img.width and 0 <= py_pos < img.height:
                    img.putpixel((px_pos, py_pos), val)

    os.makedirs(os.path.dirname(os.path.abspath(out_png_path)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_json_path)), exist_ok=True)
    img.save(out_png_path, transparency=0)

    meta = {
        "format": "NCGR",
        "is_cell_sheet": False,
        "is_8bpp": is_8bpp,
        "tiles_per_row": tiles_per_row,
        "num_tiles": num_tiles,
        "compression_layers": comp_layers,
        "ncgr_path": ncgr_path,
        "nclr_path": nclr_path,
        "base_palette_index": base_pal,
        "header_bytes": decomp[:tiles_start].hex(),
    }

    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return meta


def build_ncgr_sprite(
    png_path: str,
    meta_json_path: str,
    out_ncgr_path: str,
) -> Dict[str, Any]:
    """Rebuilds an NCGR sprite file from an edited PNG and metadata JSON."""
    import json
    from PIL import Image

    with open(meta_json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    if meta.get("format") != "NCGR":
        raise GraphicsEngineError(f"Expected NCGR format in metadata, got: {meta.get('format')}")

    is_8bpp = meta["is_8bpp"]
    num_tiles = meta["num_tiles"]
    tile_bytes = 64 if is_8bpp else 32
    is_cell_sheet = meta.get("is_cell_sheet", False)

    with Image.open(png_path) as orig_img:
        if orig_img.mode == "P":
            img = orig_img.copy()
        else:
            rgba_img = orig_img.convert("RGBA")
            nclr_path = meta.get("nclr_path")
            if nclr_path and os.path.isfile(nclr_path):
                with open(nclr_path, "rb") as f:
                    pal_data = f.read()
                colors = parse_nclr_palette(pal_data)
            else:
                colors = []
                for i in range(256):
                    v = min(255, i * 255 // (15 if not is_8bpp else 255))
                    colors.extend([v, v, v])

            pal_rgb = [(colors[i * 3], colors[i * 3 + 1], colors[i * 3 + 2]) for i in range(len(colors) // 3)]
            color_cache: Dict[Tuple[int, int, int], int] = {}

            def match_color(r: int, g: int, b: int, a: int) -> int:
                if a < 128:
                    return 0
                rgb = (r, g, b)
                if rgb in color_cache:
                    return color_cache[rgb]
                max_pal = len(pal_rgb) if (is_8bpp or len(pal_rgb) > 16) else 16
                best_dist = float("inf")
                best_idx = 0
                for idx in range(max_pal):
                    pc = pal_rgb[idx]
                    dist = (r - pc[0]) ** 2 + (g - pc[1]) ** 2 + (b - pc[2]) ** 2
                    if dist < best_dist:
                        best_dist = dist
                        best_idx = idx
                color_cache[rgb] = best_idx
                return best_idx

            img = Image.new("P", orig_img.size, 0)
            img.putpalette(colors)
            for y in range(orig_img.height):
                for x in range(orig_img.width):
                    r, g, b, a = rgba_img.getpixel((x, y))
                    img.putpixel((x, y), match_color(r, g, b, a))

    if is_cell_sheet:
        pad_val = meta.get("padding_byte", 0xCC)
        tiles_data = bytearray(bytes([pad_val]) * (num_tiles * tile_bytes))
        occluded_tiles = meta.get("occluded_tiles", {})
        if occluded_tiles:
            for t_str, hex_val in occluded_tiles.items():
                t_idx = int(t_str)
                tiles_data[t_idx * tile_bytes : (t_idx + 1) * tile_bytes] = bytes.fromhex(hex_val)

        tile_source_priority: Dict[int, int] = {}

        for comp in meta["components"]:
            cx = comp["canvas_x"]
            cy = comp["canvas_y"]
            min_x = comp["min_x"]
            min_y = comp["min_y"]
            oams = comp["oams"]
            for k, o in enumerate(oams):
                ox = o["x"] - min_x
                oy = o["y"] - min_y
                w = o["w"]
                h = o["h"]
                w_t = w // 8
                h_t = h // 8
                raw_tile = o["tile"]
                is_flipped = bool(o.get("hflip", 0) or o.get("vflip", 0))
                prio = 1 if is_flipped else 2

                for ty in range(h_t):
                    for tx in range(w_t):
                        t_idx = raw_tile + ty * w_t + tx
                        if t_idx >= num_tiles:
                            continue

                        canvas_tx = (w_t - 1 - tx) if o.get("hflip", 0) else tx
                        canvas_ty = (h_t - 1 - ty) if o.get("vflip", 0) else ty

                        if _is_oam_tile_occluded(oams, k, canvas_tx, canvas_ty):
                            continue

                        if tile_source_priority.get(t_idx, 0) > prio:
                            continue

                        t_bytes = bytearray(tile_bytes)
                        for py in range(8):
                            for px in range(8):
                                canvas_px = (7 - px) if o.get("hflip", 0) else px
                                canvas_py = (7 - py) if o.get("vflip", 0) else py
                                px_x = cx + ox + canvas_tx * 8 + canvas_px
                                px_y = cy + oy + canvas_ty * 8 + canvas_py
                                val = (
                                    img.getpixel((px_x, px_y))
                                    if (0 <= px_x < img.width and 0 <= px_y < img.height)
                                    else 0
                                )
                                if is_8bpp:
                                    t_bytes[py * 8 + px] = val & 0xFF
                                else:
                                    val = val % 16
                                    if px % 2 == 0:
                                        t_bytes[py * 4 + px // 2] |= val
                                    else:
                                        t_bytes[py * 4 + px // 2] |= (val << 4)

                        tiles_data[t_idx * tile_bytes : (t_idx + 1) * tile_bytes] = t_bytes
                        tile_source_priority[t_idx] = prio
    else:
        tiles_per_row = meta.get("tiles_per_row", 16)
        tiles_data = bytearray()
        for t_idx in range(num_tiles):
            tx = (t_idx % tiles_per_row) * 8
            ty = (t_idx // tiles_per_row) * 8
            t_data = bytearray(tile_bytes)
            for py in range(8):
                for px in range(8):
                    px_x = tx + px
                    px_y = ty + py
                    val = img.getpixel((px_x, px_y)) if px_x < img.width and px_y < img.height else 0
                    if is_8bpp:
                        t_data[py * 8 + px] = val & 0xFF
                    else:
                        val = val & 0x0F
                        if px % 2 == 0:
                            t_data[py * 4 + px // 2] |= val
                        else:
                            t_data[py * 4 + px // 2] |= (val << 4)
            tiles_data.extend(t_data)

    header_bytes = bytearray(bytes.fromhex(meta["header_bytes"]))
    total_size = len(header_bytes) + len(tiles_data)
    rahc_size = total_size - 0x10
    char_size = len(tiles_data)

    if len(header_bytes) >= 0x0C:
        header_bytes[0x08:0x0C] = struct.pack("<I", total_size)
    if len(header_bytes) >= 0x18:
        header_bytes[0x14:0x18] = struct.pack("<I", rahc_size)
    if len(header_bytes) >= 0x2C:
        header_bytes[0x28:0x2C] = struct.pack("<I", char_size)

    payload = bytes(header_bytes) + bytes(tiles_data)
    payload = pad_to_alignment(payload, 4)

    comp_layers = meta.get("compression_layers", 0)
    for _ in range(comp_layers):
        payload = ndspy.lz10.compress(payload)

    os.makedirs(os.path.dirname(os.path.abspath(out_ncgr_path)), exist_ok=True)
    with open(out_ncgr_path, "wb") as f:
        f.write(payload)

    return {
        "num_tiles": num_tiles,
        "is_8bpp": is_8bpp,
        "total_bytes": len(payload),
    }


def build_ncer_file(
    components: list,
    out_ncer_path: Optional[str] = None,
    mapping_mode: int = 0,
    compression_layers: int = 1,
    labels: Optional[List[str]] = None,
) -> bytes:
    """Builds an NCER (Nitro Cell Resource) binary file from cell components.

    Args:
        components: List of cell components (or lists of OAM dictionaries).
        out_ncer_path: Optional output path to write the generated NCER file.
        mapping_mode: 1D mapping mode (e.g. 0 for 1D 32K, 1 for 64K, 2 for 128K, 3 for 256K).
        compression_layers: Passes of LZ10 compression (0 for uncompressed, 1 for default LZ10).
        labels: Optional list of label strings for cells in the LABL chunk.

    Returns:
        bytes: Serialized (and optionally compressed) NCER binary data.
    """
    tile_multiplier = 1 << mapping_mode

    # Extract valid cell components, ignoring uncovered / auxiliary entries
    cells = []
    for comp in components:
        if isinstance(comp, dict):
            if comp.get("type") == "uncovered" or comp.get("cell_idx", 0) < 0:
                continue
            c_idx = comp.get("cell_idx", len(cells))
            cell_attr = comp.get("cell_attr", comp.get("attr", 0))
            oams = comp.get("oams", [])
            label = comp.get("label", comp.get("name"))
            cells.append({
                "cell_idx": c_idx,
                "cell_attr": cell_attr,
                "oams": oams,
                "label": label,
            })
        elif isinstance(comp, (list, tuple)):
            cells.append({
                "cell_idx": len(cells),
                "cell_attr": 0,
                "oams": comp,
                "label": None,
            })

    if cells:
        max_idx = max(c["cell_idx"] for c in cells)
        cell_by_idx = {c["cell_idx"]: c for c in cells}
        ordered_cells = []
        for i in range(max_idx + 1):
            if i in cell_by_idx:
                ordered_cells.append(cell_by_idx[i])
            else:
                ordered_cells.append({
                    "cell_idx": i,
                    "cell_attr": 0,
                    "oams": [],
                    "label": None,
                })
        cells = ordered_cells

    num_cells = len(cells)

    # 1. Block 0: CEBK (Cell Bank, magic b'KBEC')
    cebk_payload = bytearray()
    # Payload header (24 bytes):
    # num_cells (uint16), cell_bank_type=0 (uint16), cell_data_offset=24 (uint32),
    # mapping_mode (uint32), vram_offset=0 (uint32), unk1=0 (uint32), unk2=0 (uint32)
    cebk_payload += struct.pack("<HHIIIII", num_cells, 0, 24, mapping_mode, 0, 0, 0)

    cell_entries = bytearray()
    oam_pool = bytearray()

    for comp in cells:
        oams = comp.get("oams", [])
        n_oam = len(oams)
        attr = comp.get("cell_attr", 0)
        oam_off = len(oam_pool)
        cell_entries += struct.pack("<HHI", n_oam, attr, oam_off)

        for o in oams:
            x = o.get("x", 0)
            y = o.get("y", 0)
            w = o.get("w", 8)
            h = o.get("h", 8)

            if "shape" in o and "size_code" in o:
                shape = o["shape"]
                size_code = o["size_code"]
            else:
                shape, size_code = WH_TO_OAM_SHAPE_SIZE.get((w, h), (0, 0))

            rot = int(bool(o.get("rot", 0)))
            hflip = int(bool(o.get("hflip", 0)))
            vflip = int(bool(o.get("vflip", 0)))
            pal = int(o.get("pal", 0)) & 0x0F
            raw_tile = o.get("tile", 0)
            tile_val = (raw_tile // tile_multiplier) & 0x3FF

            if "attr0" in o or "a0" in o:
                attr0 = o.get("attr0", o.get("a0"))
            else:
                attr0 = (y & 0xFF) | (rot << 8) | ((shape & 3) << 14)

            if "attr1" in o or "a1" in o:
                attr1 = o.get("attr1", o.get("a1"))
            else:
                if rot:
                    affine_param = int(o.get("affine_param", 0)) & 0x1F
                    attr1 = (x & 0x1FF) | (affine_param << 9) | ((size_code & 3) << 14)
                else:
                    attr1 = (x & 0x1FF) | (hflip << 12) | (vflip << 13) | ((size_code & 3) << 14)

            if "attr2" in o or "a2" in o:
                attr2 = o.get("attr2", o.get("a2"))
            else:
                attr2 = tile_val | (pal << 12)

            oam_pool += struct.pack("<HHH", attr0, attr1, attr2)

    cebk_payload += cell_entries
    cebk_payload += oam_pool
    cebk_payload = pad_to_alignment(cebk_payload, 4)

    cebk_block = struct.pack("<4sI", b"KBEC", len(cebk_payload) + 8) + bytes(cebk_payload)

    # 2. Block 1: LABL (Labels, magic b'LBAL')
    labl_payload = bytearray()
    if labels is None:
        if any(c.get("label") for c in cells):
            active_labels = [c.get("label") or f"CellAnime{i}" for i, c in enumerate(cells)]
        else:
            active_labels = [f"CellAnime{i}" for i in range(num_cells)]
    else:
        active_labels = list(labels)
        if len(active_labels) < num_cells:
            for i in range(len(active_labels), num_cells):
                active_labels.append(f"CellAnime{i}")

    if active_labels:
        str_data = bytearray()
        offsets = []
        for lbl in active_labels:
            offsets.append(len(str_data))
            str_data += lbl.encode("latin1", errors="replace") + b"\x00"
        for off in offsets:
            labl_payload += struct.pack("<I", off)
        labl_payload += str_data
        labl_payload = pad_to_alignment(labl_payload, 4)

    labl_block = struct.pack("<4sI", b"LBAL", len(labl_payload) + 8) + bytes(labl_payload)

    # 3. Block 2: UEXT (Extended User Data, magic b'TXEU')
    uext_payload = b"\x00\x00\x00\x00"
    uext_block = struct.pack("<4sI", b"TXEU", len(uext_payload) + 8) + uext_payload

    # 4. Nitro Header (16 bytes)
    total_size = 16 + len(cebk_block) + len(labl_block) + len(uext_block)
    header = struct.pack("<4sHHIHH", b"RECN", 0xFEFF, 0x0100, total_size, 16, 3)

    raw_ncer = header + cebk_block + labl_block + uext_block

    if compression_layers > 0:
        result = compress_stream(raw_ncer, layers=compression_layers)
    else:
        result = raw_ncer

    if out_ncer_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_ncer_path)), exist_ok=True)
        with open(out_ncer_path, "wb") as f:
            f.write(result)

    return result


def rebuild_ncer_from_metadata(
    meta_json_path: str,
    out_ncer_path: str,
) -> bytes:
    """Rebuilds an NCER file using metadata from a sprite JSON metadata file.

    Args:
        meta_json_path: Path to the metadata JSON file containing cell components.
        out_ncer_path: Path where the rebuilt NCER file will be written.

    Returns:
        bytes: Serialized binary NCER data.
    """
    with open(meta_json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    components = meta.get("components", [])
    mapping_mode = meta.get("mapping_mode")
    compression_layers = meta.get("compression_layers", 1)
    labels = meta.get("labels")

    # If mapping_mode, labels, or cell_attrs are missing, attempt fallback inspection of original NCER
    ncer_path = meta.get("ncer_path")
    if ncer_path:
        cand_paths = [
            ncer_path,
            os.path.join(os.path.dirname(meta_json_path), os.path.basename(ncer_path)),
        ]
        found_ncer = None
        for cand in cand_paths:
            if os.path.isfile(cand):
                found_ncer = cand
                break

        if found_ncer:
            try:
                raw = open(found_ncer, "rb").read()
                decomp, orig_layers = decompress_stream(raw)
                cebk_idx = decomp.find(b"KBEC")
                if cebk_idx == -1:
                    cebk_idx = decomp.find(b"CEBK")
                if cebk_idx != -1:
                    num_c = struct.unpack("<H", decomp[cebk_idx + 8 : cebk_idx + 10])[0]
                    c_data_off = struct.unpack("<I", decomp[cebk_idx + 12 : cebk_idx + 16])[0]
                    if mapping_mode is None:
                        mapping_mode = struct.unpack("<I", decomp[cebk_idx + 16 : cebk_idx + 20])[0]

                    # Read cell_attr for components that lack it
                    c_start = cebk_idx + 8 + c_data_off
                    for comp in components:
                        if isinstance(comp, dict) and comp.get("type", "cell") == "cell":
                            c_idx = comp.get("cell_idx", -1)
                            if 0 <= c_idx < num_c and "cell_attr" not in comp and "attr" not in comp:
                                off = c_start + c_idx * 8
                                _, attr, _ = struct.unpack("<HHI", decomp[off : off + 8])
                                comp["cell_attr"] = attr

                    if labels is None and num_c > 0:
                        labl_idx = decomp.find(b"LBAL")
                        if labl_idx == -1:
                            labl_idx = decomp.find(b"LABL")
                        if labl_idx != -1:
                            l_size = struct.unpack("<I", decomp[labl_idx + 4 : labl_idx + 8])[0]
                            payload = decomp[labl_idx + 8 : labl_idx + l_size]
                            if len(payload) >= num_c * 4:
                                offs = [struct.unpack("<I", payload[k * 4 : (k + 1) * 4])[0] for k in range(num_c)]
                                s_base = num_c * 4
                                extracted_lbls = []
                                for o in offs:
                                    if s_base + o < len(payload):
                                        end = payload.find(b"\x00", s_base + o)
                                        if end == -1:
                                            end = len(payload)
                                        extracted_lbls.append(
                                            payload[s_base + o : end].decode("latin1", errors="replace")
                                        )
                                    else:
                                        extracted_lbls.append("")
                                labels = extracted_lbls
            except Exception:
                pass

    if mapping_mode is None:
        mapping_mode = 0

    return build_ncer_file(
        components=components,
        out_ncer_path=out_ncer_path,
        mapping_mode=mapping_mode,
        compression_layers=compression_layers,
        labels=labels,
    )





