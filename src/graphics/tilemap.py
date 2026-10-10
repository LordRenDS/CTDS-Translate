"""Screen tilemap handling, deduplication, and binary conversion for Chrono Trigger DS.

Supports:
- Parsing and building proprietary NCG, NSC headers.
- Dumping screen triplets (NCG + NCL + NSC) to PNG + JSON metadata.
- Tile deduplication with horizontal/vertical/both flip optimization.
- Rebuilding NCG character, NCL palette, NSC screen binaries from edited PNGs.
- Batch dumping and rebuilding of screen tilemaps, slide sequences, and sprites.
"""

from __future__ import annotations

import glob
import json
import os
import struct
from collections import Counter
from pathlib import Path
from typing import Any

import ndspy.color
import ndspy.graphics2D
from PIL import Image

from src.core.exceptions import GraphicsError
from src.graphics.compression import compress_stream, decompress_stream, pad_to_alignment

__all__ = [
    "DumpResult",
    "GraphicsEngineError",
    "TilePoolOverflowError",
    "build_all_screens",
    "build_ncg_header",
    "build_nsc_header",
    "build_screen",
    "deduplicate_tiles",
    "dump_all_screens",
    "dump_screen",
    "find_shared_nsc_for_tiles",
    "find_tiles_for_screen",
    "parse_ncg_header",
    "parse_nsc_header",
    "resolve_rom_directory",
]


class GraphicsEngineError(GraphicsError):
    """Base exception for graphics engine errors."""


class TilePoolOverflowError(GraphicsEngineError):
    """Raised when unique tile count exceeds Nintendo DS hardware limit (1024 tiles)."""


class DumpResult(int):
    """Result of a graphics dump operation, behaves as an int total count."""

    total: int
    screens: int
    slides: int
    sprites: int

    def __new__(cls, total: int, screens: int = 0, slides: int = 0, sprites: int = 0) -> DumpResult:
        obj = super().__new__(cls, total)
        obj.total = total
        obj.screens = screens
        obj.slides = slides
        obj.sprites = sprites
        return obj

    def __repr__(self) -> str:
        return f"<DumpResult total={self.total} screens={self.screens} slides={self.slides} sprites={self.sprites}>"


def parse_ncg_header(data: bytes) -> dict[str, Any]:
    """Parses an NCG character/tile file header (8 bytes).

    Args:
        data: NCG raw binary data.

    Returns:
        dict[str, Any]: Dictionary containing magic, tile_count, header_size.

    Raises:
        GraphicsEngineError: If data is too short or magic is invalid.
    """
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
    """Builds an 8-byte NCG tile header.

    Args:
        tile_count: Number of unique tiles.

    Returns:
        bytes: 8-byte binary NCG header.
    """
    return struct.pack("<4sI", b"NCG\x00", tile_count)


def parse_nsc_header(data: bytes) -> dict[str, Any]:
    """Parses an NSC screen tilemap header (12 bytes).

    Args:
        data: NSC raw binary data.

    Returns:
        dict[str, Any]: Dictionary containing magic, flags, width_tiles, height_tiles, is_affine, header_size.

    Raises:
        GraphicsEngineError: If data is too short or magic is invalid.
    """
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
    """Builds a 12-byte NSC screen tilemap header.

    Args:
        width_tiles: Screen width in 8x8 tiles.
        height_tiles: Screen height in 8x8 tiles.
        flags: Screen mode flags (defaults to 0x00030000).

    Returns:
        bytes: 12-byte binary NSC header.
    """
    return struct.pack("<4sIBBH", b"NSC\x00", flags, width_tiles, height_tiles, 0)


def dump_screen(
    ncg_path: Path | str,
    ncl_path: Path | str,
    nsc_path: Path | str,
    out_png_path: Path | str,
    out_json_path: Path | str,
) -> dict[str, Any]:
    """Extracts a background screen triplet into an editable PNG image and metadata JSON.

    Args:
        ncg_path: Path to NCG tile binary.
        ncl_path: Path to NCL palette binary.
        nsc_path: Path to NSC screen tilemap binary.
        out_png_path: Target PNG output path.
        out_json_path: Target JSON metadata output path.

    Returns:
        dict[str, Any]: Screen metadata dictionary.
    """
    from src.graphics.palette import parse_ncl_header

    ncg_path_str = str(ncg_path)
    ncl_path_str = str(ncl_path)
    nsc_path_str = str(nsc_path)
    out_png_path_str = str(out_png_path)
    out_json_path_str = str(out_json_path)

    with open(ncl_path_str, "rb") as f:
        ncl_data = f.read()
    with open(ncg_path_str, "rb") as f:
        ncg_data = f.read()
    with open(nsc_path_str, "rb") as f:
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

    os.makedirs(os.path.dirname(os.path.abspath(out_png_path_str)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_json_path_str)), exist_ok=True)
    img.save(out_png_path_str)

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
        "ncg_path": ncg_path_str,
        "ncl_path": ncl_path_str,
        "nsc_path": nsc_path_str,
    }

    with open(out_json_path_str, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return meta


def resolve_rom_directory(rom_data_dir: Path | str, target: Path | str) -> str:
    """Resolves a target directory path that may be relative to rom_data_dir, absolute, or standalone.

    Args:
        rom_data_dir: Extracted NitroFS data directory.
        target: Target relative or absolute directory path.

    Returns:
        str: Absolute path to directory.

    Raises:
        GraphicsEngineError: If directory cannot be found.
    """
    target_str = str(target)
    rom_data_dir_str = str(rom_data_dir)

    if os.path.isdir(target_str):
        return os.path.abspath(target_str)
    cand = os.path.join(rom_data_dir_str, target_str)
    if os.path.isdir(cand):
        return os.path.abspath(cand)
    raise GraphicsEngineError(f"Directory not found: '{target_str}' (checked '{target_str}' and '{cand}')")


def find_shared_nsc_for_tiles(ncg_path: Path | str) -> str | None:
    """Finds a shared _nsc.bin template for illustration/slide tilesets in a folder.

    Args:
        ncg_path: Path to target NCG tile binary.

    Returns:
        str | None: Matched shared NSC path, or None if not found.
    """
    ncg_path_str = str(ncg_path)
    d = os.path.dirname(ncg_path_str)
    b = os.path.basename(ncg_path_str)

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


def find_tiles_for_screen(nsc_path: Path | str) -> str | None:
    """Finds matching _ncg.bin tiles for a given _nsc.bin screen.

    Args:
        nsc_path: Path to target NSC screen binary.

    Returns:
        str | None: Matched NCG path, or None if not found.
    """
    nsc_path_str = str(nsc_path)
    stem = nsc_path_str[:-8]
    direct = stem + "_ncg.bin"
    if os.path.isfile(direct):
        return direct

    dir_path = os.path.dirname(nsc_path_str)
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
    rom_data_dir: Path | str,
    output_image_dir: Path | str,
    category: str | None = None,
    dump_all: bool = False,
    directory: str | None = None,
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
    from src.graphics.palette import find_palette_for_screen, find_palette_for_sprite
    from src.graphics.sprites import dump_ncgr_sprite, find_cell_bank_for_sprite

    rom_data_dir_str = str(rom_data_dir)
    output_image_dir_str = str(output_image_dir)

    target_dir_arg = directory or category
    search_dirs: list[str] = []

    if target_dir_arg:
        search_dirs.append(resolve_rom_directory(rom_data_dir_str, target_dir_arg))
    elif dump_all:
        search_dirs.append(os.path.abspath(rom_data_dir_str))
    else:
        default_categories = ["title", "Ending", "menu", "minimap", "special"]
        for c in default_categories:
            p = os.path.join(rom_data_dir_str, c)
            if os.path.isdir(p):
                search_dirs.append(os.path.abspath(p))

    dumped_screens = 0
    dumped_slides = 0
    dumped_sprites = 0
    dumped_ncg_paths: set[str] = set()

    # 1. Screen tilemaps (*_nsc.bin)
    nsc_files: list[str] = []
    for d in search_dirs:
        nsc_files.extend(glob.glob(os.path.join(d, "**", "*_nsc.bin"), recursive=True))
    nsc_files = sorted(list(set(nsc_files)))

    for nsc in nsc_files:
        ncg = find_tiles_for_screen(nsc)
        ncl = find_palette_for_screen(nsc)
        if not ncg or not ncl:
            continue

        rel = os.path.relpath(nsc, rom_data_dir_str)
        rel_stem = rel[:-8]  # strip '_nsc.bin'
        out_png = os.path.join(output_image_dir_str, rel_stem + ".png")
        out_json = os.path.join(output_image_dir_str, rel_stem + ".json")

        try:
            dump_screen(ncg, ncl, nsc, out_png, out_json)
            dumped_screens += 1
            dumped_ncg_paths.add(os.path.abspath(ncg))
        except Exception as e:
            print(f"Warning: Failed to dump {rel}: {e}")

    # 2. Shared-NSC slide collections (*_ncg.bin using a shared template *_nsc.bin)
    ncg_files: list[str] = []
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

        rel = os.path.relpath(ncg, rom_data_dir_str)
        rel_stem = rel[:-8]  # strip '_ncg.bin'
        out_png = os.path.join(output_image_dir_str, rel_stem + ".png")
        out_json = os.path.join(output_image_dir_str, rel_stem + ".json")

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
    ncgr_files: list[str] = []
    for d in search_dirs:
        ncgr_files.extend(glob.glob(os.path.join(d, "**", "*.ncgr"), recursive=True))
        ncgr_files.extend(glob.glob(os.path.join(d, "**", "*.NCGR"), recursive=True))
    ncgr_files = sorted(list(set(ncgr_files)))

    for ncgr in ncgr_files:
        rel = os.path.relpath(ncgr, rom_data_dir_str)
        rel_stem = os.path.splitext(rel)[0]
        out_png = os.path.join(output_image_dir_str, rel_stem + ".png")
        out_json = os.path.join(output_image_dir_str, rel_stem + ".json")

        nclr = find_palette_for_sprite(ncgr)
        ncer = find_cell_bank_for_sprite(ncgr)

        try:
            dump_ncgr_sprite(ncgr, nclr, out_png, out_json, ncer_path=ncer)
            dumped_sprites += 1
        except Exception as e:
            print(f"Warning: Failed to dump sprite {rel}: {e}")

    total = dumped_screens + dumped_slides + dumped_sprites
    return DumpResult(total, screens=dumped_screens, slides=dumped_slides, sprites=dumped_sprites)


def deduplicate_tiles(
    tiles_8x8: list[list[int]],
    is_8bpp: bool,
    allow_flips: bool = True,
) -> tuple[list[list[int]], list[tuple[int, bool, bool, int]]]:
    """Deduplicates 8x8 pixel tiles and returns unique tiles + tilemap placement parameters.

    Returns:
        tuple: (unique_tiles, tile_placements)
        where each placement is (tile_index, h_flip, v_flip, palette_num)
    """
    unique_tiles: list[list[int]] = []
    tile_lookup: dict[tuple[int, ...], tuple[int, bool, bool]] = {}
    placements: list[tuple[int, bool, bool, int]] = []

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
    png_path: Path | str,
    meta_json_path: Path | str,
    out_ncg_path: Path | str,
    out_ncl_path: Path | str,
    out_nsc_path: Path | str,
) -> dict[str, Any]:
    """Rebuilds NCG, NCL, NSC binaries from an edited PNG and metadata JSON.

    Args:
        png_path: Path to edited PNG image.
        meta_json_path: Path to original JSON metadata.
        out_ncg_path: Path for output NCG binary.
        out_ncl_path: Path for output NCL binary.
        out_nsc_path: Path for output NSC binary.

    Returns:
        dict[str, Any]: Summary dictionary of rebuild statistics.
    """
    from src.graphics.palette import build_ncl_header

    png_path_str = str(png_path)
    meta_json_path_str = str(meta_json_path)
    out_ncg_path_str = str(out_ncg_path)
    out_ncl_path_str = str(out_ncl_path)
    out_nsc_path_str = str(out_nsc_path)

    with open(meta_json_path_str, "r", encoding="utf-8") as f:
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
    color_map: dict[tuple[int, int, int], int] = {}

    def get_best_color(rgba: tuple[int, int, int, int]) -> int:
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

    with Image.open(png_path_str) as orig_img:
        img = orig_img.convert("RGBA")

    # Slice into 8x8 tiles
    tiles_8x8: list[list[int]] = []
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

    os.makedirs(os.path.dirname(os.path.abspath(out_ncg_path_str)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_ncl_path_str)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_nsc_path_str)), exist_ok=True)

    with open(out_ncg_path_str, "wb") as f:
        f.write(ncg_final)
    with open(out_ncl_path_str, "wb") as f:
        f.write(ncl_final)
    with open(out_nsc_path_str, "wb") as f:
        f.write(nsc_final)

    return {
        "unique_tiles": len(unique_tiles),
        "total_screen_tiles": len(tiles_8x8),
        "is_8bpp": is_8bpp,
        "width_tiles": w_tiles,
        "height_tiles": h_tiles,
    }


def build_all_screens(
    image_dir: Path | str,
    meta_dir: Path | str,
    target_rom_data_dir: Path | str,
    sub_dir: str | None = None,
    rebuild_ncer: bool = False,
) -> int:
    """Scans image_dir for translated PNGs and rebuilds them into target_rom_data_dir.

    Args:
        image_dir: Source folder of translated PNGs (e.g. 'translated image').
        meta_dir: Folder containing metadata JSONs from original dump (e.g. 'extracted image').
        target_rom_data_dir: Target NitroFS data directory (e.g. 'extracted rom/data').
        sub_dir: Optional subfolder within image_dir to rebuild.
        rebuild_ncer: Whether to rebuild corresponding .NCER cell bank files.

    Returns:
        int: Number of screens rebuilt.
    """
    from src.graphics.sprites import build_ncgr_sprite, rebuild_ncer_from_metadata

    image_dir_str = str(image_dir)
    meta_dir_str = str(meta_dir)
    target_rom_data_dir_str = str(target_rom_data_dir)

    built_count = 0
    search_root = os.path.join(image_dir_str, sub_dir) if sub_dir else image_dir_str
    png_files = glob.glob(os.path.join(search_root, "**", "*.png"), recursive=True)

    for png_path in sorted(png_files):
        rel = os.path.relpath(png_path, image_dir_str)
        rel_stem = os.path.splitext(rel)[0]

        cand_img_json = os.path.join(image_dir_str, rel_stem + ".json")
        if os.path.isfile(cand_img_json):
            meta_json_path = cand_img_json
        else:
            meta_json_path = os.path.join(meta_dir_str, rel_stem + ".json")

        if not os.path.isfile(meta_json_path):
            print(f"Warning: Metadata JSON not found for {rel}: {meta_json_path}")
            continue

        with open(meta_json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        if meta.get("format") == "NCGR":
            out_ncgr = os.path.join(target_rom_data_dir_str, rel_stem + ".NCGR")
            try:
                build_ncgr_sprite(png_path, meta_json_path, out_ncgr)
                if rebuild_ncer and meta.get("is_cell_sheet") and meta.get("ncer_path"):
                    out_ncer = os.path.join(target_rom_data_dir_str, rel_stem + ".NCER")
                    rebuild_ncer_from_metadata(meta_json_path, out_ncer)
                    print(f"Successfully rebuilt cell bank '{out_ncer}'.")
                built_count += 1
            except Exception as e:
                print(f"Warning: Failed to build NCGR sprite {rel}: {e}")
            continue

        out_ncg = os.path.join(target_rom_data_dir_str, rel_stem + "_ncg.bin")
        out_ncl = os.path.join(target_rom_data_dir_str, rel_stem + "_ncl.bin")
        if meta.get("is_shared_nsc") and "nsc_path" in meta:
            rel_nsc = os.path.basename(meta["nsc_path"])
            out_nsc = os.path.join(os.path.dirname(out_ncg), rel_nsc)
        else:
            out_nsc = os.path.join(target_rom_data_dir_str, rel_stem + "_nsc.bin")

        try:
            build_screen(png_path, meta_json_path, out_ncg, out_ncl, out_nsc)
            built_count += 1
        except Exception as e:
            print(f"Warning: Failed to build {rel}: {e}")

    return built_count
