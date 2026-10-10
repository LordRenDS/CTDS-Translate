"""NCER cell bank and NCGR sprite processing for Chrono Trigger DS.

Supports:
- OAM shape and size mapping tables.
- Decompressing and assembling NCGR sprites (linear or 2D NCER cell bank layout).
- Rebuilding NCGR character binaries and NCER cell bank structures.
- Sprite cell deduplication and occlusion detection.
"""

from __future__ import annotations

import json
import os
import re
import struct
from pathlib import Path
from typing import Any

import ndspy.lz10
from PIL import Image

from src.graphics.compression import compress_stream, decompress_stream, pad_to_alignment
from src.graphics.palette import parse_nclr_palette
from src.graphics.tilemap import GraphicsEngineError

__all__ = [
    "OAM_SHAPES",
    "WH_TO_OAM_SHAPE_SIZE",
    "build_ncer_file",
    "build_ncgr_sprite",
    "dump_ncgr_sprite",
    "find_cell_bank_for_sprite",
    "rebuild_ncer_from_metadata",
]

OAM_SHAPES: dict[int, dict[int, tuple[int, int]]] = {
    0: {0: (8, 8), 1: (16, 16), 2: (32, 32), 3: (64, 64)},
    1: {0: (16, 8), 1: (32, 8), 2: (32, 16), 3: (64, 32)},
    2: {0: (8, 16), 1: (8, 32), 2: (16, 32), 3: (32, 64)},
}

WH_TO_OAM_SHAPE_SIZE: dict[tuple[int, int], tuple[int, int]] = {
    (w, h): (shape, size_code)
    for shape, sizes in OAM_SHAPES.items()
    for size_code, (w, h) in sizes.items()
}


def find_cell_bank_for_sprite(ncgr_path: Path | str) -> str | None:
    """Finds matching NCER cell bank for a given NCGR sprite file.

    Args:
        ncgr_path: Path to the target NCGR file.

    Returns:
        str | None: Path to matching NCER file if found, else None.
    """
    ncgr_path_str = str(ncgr_path)
    stem = os.path.splitext(ncgr_path_str)[0]
    dir_path = os.path.dirname(ncgr_path_str)
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


def _is_oam_tile_occluded(oams: list[dict[str, Any]], k: int, tx: int, ty: int) -> bool:
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
    ncgr_path: Path | str,
    nclr_path: Path | str | None,
    out_png_path: Path | str,
    out_json_path: Path | str,
    ncer_path: Path | str | None = None,
    tiles_per_row: int = 16,
) -> dict[str, Any]:
    """Extracts an NCGR sprite character container into an editable PNG and metadata JSON.

    If an NCER companion cell bank is found or specified, exports assembled 2D cell sprites
    without 1D tile slicing distortions or alignment padding artifacts.

    Args:
        ncgr_path: Path to target NCGR file.
        nclr_path: Optional path to NCLR palette file.
        out_png_path: Target output PNG path.
        out_json_path: Target output JSON metadata path.
        ncer_path: Optional companion NCER cell bank file.
        tiles_per_row: Slicing row width in tiles if linear fallback layout is used.

    Returns:
        dict[str, Any]: Sprite metadata dictionary.

    Raises:
        GraphicsEngineError: If NCGR header or RAHC block is corrupted.
    """
    ncgr_path_str = str(ncgr_path)
    nclr_path_str = str(nclr_path) if nclr_path is not None else None
    out_png_path_str = str(out_png_path)
    out_json_path_str = str(out_json_path)
    ncer_path_str = str(ncer_path) if ncer_path is not None else None

    with open(ncgr_path_str, "rb") as f:
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
    base = os.path.basename(ncgr_path_str)
    m_face = re.search(r"face_(\d+)", base)
    m_win = re.search(r"obj_win_.*_(\d+)", base)
    m_slv = re.search(r"obj_slv_name_(\d+)", base)
    m_soroll = re.search(r"obj_soroll_(\d+)", base)

    # Check if the palette is already style-specific (e.g. win_4.NCLR has style in subpalette 0)
    pal_base = os.path.basename(nclr_path_str) if nclr_path_str else ""
    is_style_specific_pal = bool(re.search(r"win_\d+", pal_base))

    if m_face:
        base_pal = int(m_face.group(1))
    elif m_win:
        base_pal = 0 if is_style_specific_pal else max(0, int(m_win.group(1)) - 1)
    elif m_slv:
        base_pal = int(m_slv.group(1))
    elif m_soroll:
        base_pal = 0 if is_style_specific_pal else max(0, int(m_soroll.group(1)) - 1)
    else:
        base_pal = 0

    # Load palette
    is_world_obj_0000 = (base == "WorldObj_0000.NCGR" or base == "WorldObj_0000")
    is_face = (base == "face.NCGR" or base == "face")

    if is_world_obj_0000:
        colors: list[int] = []
        curr = os.path.dirname(ncgr_path_str)
        data_root = None
        while curr and os.path.basename(curr):
            if os.path.basename(curr) == "data":
                data_root = curr
                break
            curr = os.path.dirname(curr)
        if data_root:
            for i in range(7):
                plt_path = os.path.join(data_root, "Chara", f"ObjPlt_{i:04d}.NCLR")
                if os.path.isfile(plt_path):
                    with open(plt_path, "rb") as f:
                        c_pal = list(parse_nclr_palette(f.read())[:48])
                        c_pal[0:3] = [0, 0, 0]
                        colors.extend(c_pal)
                else:
                    colors.extend([0] * 48)
            plt_0007 = os.path.join(os.path.dirname(ncgr_path_str), "WorldObjPlt_0007.NCLR")
            if os.path.isfile(plt_0007):
                with open(plt_0007, "rb") as f:
                    c_pal = list(parse_nclr_palette(f.read())[:48])
                    c_pal[0:3] = [0, 0, 0]
                    colors.extend(c_pal)
            else:
                colors.extend([0] * 48)
            while len(colors) < 256 * 3:
                colors.extend([0, 0, 0])
            nclr_path_str = os.path.join(os.path.dirname(ncgr_path_str), "WorldObjPlt_0000.NCLR")
    elif nclr_path_str and os.path.isfile(nclr_path_str):
        with open(nclr_path_str, "rb") as f:
            pal_bytes = f.read()
        colors = list(parse_nclr_palette(pal_bytes))
        if len(colors) >= 3:
            colors[0:3] = [0, 0, 0]
    else:
        colors = []
        for i in range(256):
            if is_8bpp:
                v = min(255, i * 255 // 255)
            else:
                v = min(255, (i % 16) * 255 // 15)
            colors.extend([v, v, v])
        if len(colors) >= 3:
            colors[0:3] = [0, 0, 0]

    if ncer_path_str is None:
        ncer_path_str = find_cell_bank_for_sprite(ncgr_path_str)

    # Attempt NCER cell-aware export if NCER file is available
    if ncer_path_str and os.path.isfile(ncer_path_str):
        try:
            with open(ncer_path_str, "rb") as f:
                ncer_decomp, _ = decompress_stream(f.read())
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

                labels: list[str] = []
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

                components: list[dict[str, Any]] = []
                covered_tiles: set[int] = set()

                for i in range(num_cells):
                    n_oam, attr, oam_off = struct.unpack(
                        "<HHI", ncer_decomp[cell_start + i * 8 : cell_start + (i + 1) * 8]
                    )
                    oams: list[dict[str, Any]] = []
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
                        comp_entry: dict[str, Any] = {
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
                occluded_tiles: dict[str, str] = {}
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
                        cell_idx = comp.get("cell_idx", 0)
                        if is_face and 0 <= cell_idx < 7:
                            eff_pal = cell_idx + o.get("pal", 0)
                        elif is_world_obj_0000:
                            char_id = min(7, cell_idx // 8)
                            eff_pal = char_id + o.get("pal", 0)
                        else:
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

                os.makedirs(os.path.dirname(os.path.abspath(out_png_path_str)), exist_ok=True)
                os.makedirs(os.path.dirname(os.path.abspath(out_json_path_str)), exist_ok=True)
                img.save(out_png_path_str, transparency=0)

                meta = {
                    "format": "NCGR",
                    "is_cell_sheet": True,
                    "is_8bpp": is_8bpp,
                    "num_tiles": num_tiles,
                    "sheet_width": sheet_w,
                    "sheet_height": sheet_h,
                    "compression_layers": comp_layers,
                    "ncgr_path": ncgr_path_str,
                    "ncer_path": ncer_path_str,
                    "nclr_path": nclr_path_str,
                    "base_palette_index": base_pal,
                    "occluded_tiles": occluded_tiles,
                    "padding_byte": padding_byte,
                    "mapping_mode": mapping_mode,
                    "labels": labels,
                    "components": components,
                    "header_bytes": decomp[:tiles_start].hex(),
                }

                with open(out_json_path_str, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)

                return meta
        except Exception as e:
            print(f"Warning: Failed NCER cell extraction for {ncgr_path_str}: {e}; falling back to raw tiles.")

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

    os.makedirs(os.path.dirname(os.path.abspath(out_png_path_str)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_json_path_str)), exist_ok=True)
    img.save(out_png_path_str, transparency=0)

    meta = {
        "format": "NCGR",
        "is_cell_sheet": False,
        "is_8bpp": is_8bpp,
        "tiles_per_row": tiles_per_row,
        "num_tiles": num_tiles,
        "compression_layers": comp_layers,
        "ncgr_path": ncgr_path_str,
        "nclr_path": nclr_path_str,
        "base_palette_index": base_pal,
        "header_bytes": decomp[:tiles_start].hex(),
    }

    with open(out_json_path_str, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return meta


def build_ncgr_sprite(
    png_path: Path | str,
    meta_json_path: Path | str,
    out_ncgr_path: Path | str,
) -> dict[str, Any]:
    """Rebuilds an NCGR sprite file from an edited PNG and metadata JSON.

    Args:
        png_path: Path to edited input PNG.
        meta_json_path: Path to metadata JSON.
        out_ncgr_path: Path where rebuilt NCGR binary will be written.

    Returns:
        dict[str, Any]: Summary of rebuilt sprite.

    Raises:
        GraphicsEngineError: If format in metadata is not NCGR.
    """
    png_path_str = str(png_path)
    meta_json_path_str = str(meta_json_path)
    out_ncgr_path_str = str(out_ncgr_path)

    with open(meta_json_path_str, "r", encoding="utf-8") as f:
        meta = json.load(f)

    if meta.get("format") != "NCGR":
        raise GraphicsEngineError(f"Expected NCGR format in metadata, got: {meta.get('format')}")

    is_8bpp = meta["is_8bpp"]
    num_tiles = meta["num_tiles"]
    tile_bytes = 64 if is_8bpp else 32
    is_cell_sheet = meta.get("is_cell_sheet", False)

    with Image.open(png_path_str) as orig_img:
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
            color_cache: dict[tuple[int, int, int], int] = {}

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

        tile_source_priority: dict[int, int] = {}

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

    os.makedirs(os.path.dirname(os.path.abspath(out_ncgr_path_str)), exist_ok=True)
    with open(out_ncgr_path_str, "wb") as f:
        f.write(payload)

    return {
        "num_tiles": num_tiles,
        "is_8bpp": is_8bpp,
        "total_bytes": len(payload),
    }


def build_ncer_file(
    components: list[Any],
    out_ncer_path: Path | str | None = None,
    mapping_mode: int = 0,
    compression_layers: int = 1,
    labels: list[str] | None = None,
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
    cells: list[dict[str, Any]] = []
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
        out_ncer_path_str = str(out_ncer_path)
        os.makedirs(os.path.dirname(os.path.abspath(out_ncer_path_str)), exist_ok=True)
        with open(out_ncer_path_str, "wb") as f:
            f.write(result)

    return result


def rebuild_ncer_from_metadata(
    meta_json_path: Path | str,
    out_ncer_path: Path | str,
) -> bytes:
    """Rebuilds an NCER file using metadata from a sprite JSON metadata file.

    Args:
        meta_json_path: Path to the metadata JSON file containing cell components.
        out_ncer_path: Path where the rebuilt NCER file will be written.

    Returns:
        bytes: Serialized binary NCER data.
    """
    meta_json_path_str = str(meta_json_path)
    out_ncer_path_str = str(out_ncer_path)

    with open(meta_json_path_str, "r", encoding="utf-8") as f:
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
            os.path.join(os.path.dirname(meta_json_path_str), os.path.basename(ncer_path)),
        ]
        found_ncer = None
        for cand in cand_paths:
            if os.path.isfile(cand):
                found_ncer = cand
                break

        if found_ncer:
            try:
                with open(found_ncer, "rb") as f:
                    raw = f.read()
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
        out_ncer_path=out_ncer_path_str,
        mapping_mode=mapping_mode,
        compression_layers=compression_layers,
        labels=labels,
    )
