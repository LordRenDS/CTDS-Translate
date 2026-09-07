"""Graphics Engine for Chrono Trigger DS.

Handles extraction and re-insertion of Nintendo DS background screens:
- Multi-layer LZ10 decompression and compression.
- Parsing and serialization of Chrono Trigger DS proprietary NCG, NCL, NSC headers.
- Rendering tilemaps to PNG and metadata JSON.
- Slicing PNGs into 8x8 tiles with smart deduplication (normal, H-flip, V-flip, HV-flip).
- Rebuilding game binary triplets (*_ncg.bin, *_ncl.bin, *_nsc.bin).
"""

import os
import struct
from typing import Any, Dict, List, Optional, Tuple

import ndspy.color
import ndspy.graphics2D
import ndspy.lz10


class GraphicsEngineError(Exception):
    """Base exception for graphics engine errors."""


class TilePoolOverflowError(GraphicsEngineError):
    """Raised when unique tile count exceeds Nintendo DS hardware limit (1024 tiles)."""


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
    return {
        "magic": magic,
        "flags": flags,
        "width_tiles": width_tiles,
        "height_tiles": height_tiles,
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
    tiles = ndspy.graphics2D.loadImageTiles(ncg_decomp[8:], fmt)
    tilemap = ndspy.graphics2D.loadTilemapTiles(nsc_decomp[12:], ndspy.graphics2D.TilemapFormat.I10H1V1P4)

    w_tiles = nsc_info["width_tiles"]
    h_tiles = nsc_info["height_tiles"]

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
        "tile_count": tile_count,
        "raw_tile_count": raw_tile_cnt,
        "width_tiles": w_tiles,
        "height_tiles": h_tiles,
        "width_px": w_tiles * 8,
        "height_px": h_tiles * 8,
        "flags": nsc_info["flags"],
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


def find_palette_for_screen(nsc_path: str) -> Optional[str]:
    """Finds matching _ncl.bin palette for a given _nsc.bin screen."""
    import glob
    stem = nsc_path[:-8]
    direct = stem + "_ncl.bin"
    if os.path.isfile(direct):
        return direct

    dir_path = os.path.dirname(nsc_path)
    # Match prefix
    cand = glob.glob(os.path.join(dir_path, "*_ncl.bin"))
    if cand:
        return cand[0]

    # Check menu/plt
    menu_plt = os.path.join(os.path.dirname(dir_path), "plt", "win_1_ncl.bin")
    if os.path.isfile(menu_plt):
        return menu_plt

    return None


def find_tiles_for_screen(nsc_path: str) -> Optional[str]:
    """Finds matching _ncg.bin tiles for a given _nsc.bin screen."""
    stem = nsc_path[:-8]
    direct = stem + "_ncg.bin"
    if os.path.isfile(direct):
        return direct

    dir_path = os.path.dirname(nsc_path)
    parts = os.path.basename(stem).split("_")
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
) -> int:
    """Scans rom_data_dir for screen tilemaps and dumps them to PNG + JSON.

    Args:
        rom_data_dir: Path to extracted NitroFS data directory.
        output_image_dir: Output base directory (e.g. 'extracted image').
        category: Optional category filter (e.g. 'title', 'Ending', 'menu').
        dump_all: If True, dumps every found screen across all folders.

    Returns:
        int: Number of screens successfully dumped.
    """
    import glob

    default_categories = ["title", "Ending", "menu/Extra", "minimap", "special"]
    search_dirs = []

    if category:
        target = os.path.join(rom_data_dir, category)
        if os.path.isdir(target):
            search_dirs.append(target)
        else:
            raise GraphicsEngineError(f"Category directory not found: {target}")
    elif dump_all:
        search_dirs.append(rom_data_dir)
    else:
        for c in default_categories:
            p = os.path.join(rom_data_dir, c)
            if os.path.isdir(p):
                search_dirs.append(p)

    nsc_files: List[str] = []
    for d in search_dirs:
        nsc_files.extend(glob.glob(os.path.join(d, "**", "*_nsc.bin"), recursive=True))

    nsc_files = sorted(list(set(nsc_files)))
    dumped_count = 0

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
            dumped_count += 1
        except Exception as e:
            print(f"Warning: Failed to dump {rel}: {e}")

    return dumped_count


def pad_to_alignment(data: bytes, align: int = 4) -> bytes:
    """Pads byte buffer to specified alignment boundary with zeros."""
    rem = len(data) % align
    if rem:
        data += b"\x00" * (align - rem)
    return data


def deduplicate_tiles(
    tiles_8x8: List[List[int]],
    is_8bpp: bool,
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
            if idx >= 1024:
                raise TilePoolOverflowError(
                    f"Screen exceeded maximum allowable unique tiles (1024). Got {idx + 1} unique tiles."
                )
            unique_tiles.append(norm_px)

            tile_2d = [norm_px[i * 8 : (i + 1) * 8] for i in range(8)]
            t_h = tuple(p for row in tile_2d for p in reversed(row))
            t_v = tuple(p for row in reversed(tile_2d) for p in row)
            t_hv = tuple(p for row in reversed(tile_2d) for p in reversed(row))

            tile_lookup[t_norm] = (idx, False, False)
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

    unique_tiles, placements = deduplicate_tiles(tiles_8x8, is_8bpp=is_8bpp)

    # Construct ImageTiles and TilemapTiles
    fmt = ndspy.graphics2D.ImageFormat.I8 if is_8bpp else ndspy.graphics2D.ImageFormat.I4
    img_tiles = [ndspy.graphics2D.ImageTile.fromPixels(px, fmt) for px in unique_tiles]

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
) -> int:
    """Scans image_dir for translated PNGs and rebuilds them into target_rom_data_dir.

    Args:
        image_dir: Source folder of translated PNGs (e.g. 'translated image').
        meta_dir: Folder containing metadata JSONs from original dump (e.g. 'extracted image').
        target_rom_data_dir: Target NitroFS data directory (e.g. 'extracted rom/data').

    Returns:
        int: Number of screens rebuilt.
    """
    import glob

    built_count = 0
    png_files = glob.glob(os.path.join(image_dir, "**", "*.png"), recursive=True)

    for png_path in sorted(png_files):
        rel = os.path.relpath(png_path, image_dir)
        rel_stem = os.path.splitext(rel)[0]

        meta_json_path = os.path.join(meta_dir, rel_stem + ".json")
        if not os.path.isfile(meta_json_path):
            print(f"Warning: Metadata JSON not found for {rel}: {meta_json_path}")
            continue

        out_ncg = os.path.join(target_rom_data_dir, rel_stem + "_ncg.bin")
        out_ncl = os.path.join(target_rom_data_dir, rel_stem + "_ncl.bin")
        out_nsc = os.path.join(target_rom_data_dir, rel_stem + "_nsc.bin")

        try:
            build_screen(png_path, meta_json_path, out_ncg, out_ncl, out_nsc)
            built_count += 1
        except Exception as e:
            print(f"Warning: Failed to build {rel}: {e}")

    return built_count


