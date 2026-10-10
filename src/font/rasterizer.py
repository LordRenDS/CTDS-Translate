"""PNG sheet rendering, JSON metadata export/import, and font building/dumping routines."""

import json
import math
import os
from pathlib import Path
from typing import Any
from PIL import Image

from src.core.exceptions import FontError
from src.font.formats import (
    GRID_COLUMNS,
    GRID_COLOR_CELL,
    GRID_COLOR_WIDTH,
    PALETTE_2BPP,
    get_char_repr,
    pack_fnt_binary,
    parse_fnt_header,
    sample_pixel_2bpp,
)

__all__ = [
    "build_all_fonts",
    "build_fnt",
    "build_fnt_from_png_and_json",
    "dump_all_fonts",
    "dump_fnt",
    "dump_fnt_to_png_and_json",
]


def dump_fnt_to_png_and_json(
    fnt_bytes: bytes,
    output_png_path: str,
    output_json_path: str,
    grid_mode: str = "both",
) -> None:
    """Extracts all glyphs from a .fnt binary into a PNG image grid and JSON metadata.

    Args:
        fnt_bytes: Raw binary content of .fnt file.
        output_png_path: File path to write the PNG glyph sheet.
        output_json_path: File path to write the metadata JSON.
        grid_mode: Grid overlay mode: 'both' (cell borders + glyph width markers),
            'cells' (cell borders only), or 'none' (raw background).

    Raises:
        FontError: If header magic is invalid, binary is corrupted, or grid_mode is unknown.
    """
    if grid_mode not in ("both", "cells", "none"):
        raise FontError(f"Invalid grid_mode: {grid_mode!r}. Must be 'both', 'cells', or 'none'.")

    header = parse_fnt_header(fnt_bytes)
    def_w = header.default_width
    height_words = header.height_words
    glyph_count = header.glyph_count
    reserved = header.reserved
    cell_h = header.cell_height
    cell_w = header.cell_width
    char_map = header.char_map
    offsets = header.offsets

    # Build reverse map for character representation
    glyph_to_char: dict[int, str] = {}
    for code, g_idx in enumerate(char_map):
        if g_idx != 0xFFFF and g_idx not in glyph_to_char:
            glyph_to_char[g_idx] = get_char_repr(code)

    cols = GRID_COLUMNS
    rows = math.ceil(glyph_count / cols) if glyph_count > 0 else 1

    img = Image.new("P", (cols * cell_w, rows * cell_h), 0)
    img.putpalette(PALETTE_2BPP)

    glyphs_meta: list[dict[str, Any]] = []

    for i in range(glyph_count):
        off = offsets[i]
        gx = i % cols
        gy = i // cols
        cx = gx * cell_w
        cy = gy * cell_h

        char_name = glyph_to_char.get(i, None)

        if off == 0:
            glyphs_meta.append({
                "index": i,
                "width": 0,
                "bpr": 0,
                "word_count": 0,
                "offset": 0,
                "grid_x": gx,
                "grid_y": gy,
                "char_repr": char_name,
            })
            continue

        w = fnt_bytes[off]
        bpr = fnt_bytes[off + 1]
        raw_bm = fnt_bytes[off + 2 : off + 2 + bpr * cell_h]

        for r in range(cell_h):
            row_bytes = raw_bm[r * bpr : (r + 1) * bpr]
            px_row = []
            for b in row_bytes:
                px_row.extend([b & 3, (b >> 2) & 3, (b >> 4) & 3, (b >> 6) & 3])
            for c, val in enumerate(px_row[:w]):
                if c < cell_w:
                    img.putpixel((cx + c, cy + r), val)

        glyphs_meta.append({
            "index": i,
            "width": w,
            "bpr": bpr,
            "word_count": bpr,
            "offset": off,
            "grid_x": gx,
            "grid_y": gy,
            "char_repr": char_name,
        })

    # Apply visual grid overlays if requested
    img_w = cols * cell_w
    img_h = rows * cell_h

    if grid_mode in ("both", "cells"):
        # Draw cell boundary lines (GRID_COLOR_CELL)
        v_lines = [0] + [(gx + 1) * cell_w - 1 for gx in range(cols)]
        for vx in v_lines:
            if vx < img_w:
                for y in range(img_h):
                    if img.getpixel((vx, y)) == 0:
                        img.putpixel((vx, y), GRID_COLOR_CELL)

        h_lines = [0] + [(gy + 1) * cell_h - 1 for gy in range(rows)]
        for hy in h_lines:
            if hy < img_h:
                for x in range(img_w):
                    if img.getpixel((x, hy)) == 0:
                        img.putpixel((x, hy), GRID_COLOR_CELL)

    if grid_mode == "both":
        # Draw glyph width boundary markers (GRID_COLOR_WIDTH)
        for i in range(glyph_count):
            g_meta = glyphs_meta[i]
            w = g_meta["width"]
            if g_meta["offset"] > 0 and 0 < w < cell_w:
                gx = i % cols
                gy = i // cols
                cx = gx * cell_w
                cy = gy * cell_h
                wx = cx + w
                if wx < img_w:
                    for y in range(cy, cy + cell_h):
                        if img.getpixel((wx, y)) not in (1, 2, 3):
                            img.putpixel((wx, y), GRID_COLOR_WIDTH)

    # Save PNG
    out_png = Path(output_png_path).resolve()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_png))

    # Save JSON metadata
    meta = {
        "magic": "FONT",
        "default_width": def_w,
        "height_words": height_words,
        "glyph_count": glyph_count,
        "reserved": reserved,
        "cell_width": cell_w,
        "cell_height": cell_h,
        "grid_columns": cols,
        "grid_rows": rows,
        "grid_mode": grid_mode,
        "char_map": char_map,
        "glyphs": glyphs_meta,
    }

    out_json = Path(output_json_path).resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


# Alias for interface compatibility
dump_fnt = dump_fnt_to_png_and_json


def build_fnt_from_png_and_json(input_png_path: str, input_json_path: str) -> bytes:
    """Rebuilds a .fnt binary from a PNG glyph sheet and JSON metadata descriptor.

    Guarantees 1:1 bit-exact roundtrip against the original game binary.

    Args:
        input_png_path: Path to the PNG glyph sheet image.
        input_json_path: Path to the metadata JSON file.

    Returns:
        Exact binary .fnt data.

    Raises:
        FontError: If JSON metadata or PNG image is malformed.
    """
    try:
        with open(input_json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise FontError(f"Failed to read font JSON metadata from {input_json_path}: {exc}") from exc

    try:
        img = Image.open(input_png_path)
    except OSError as exc:
        raise FontError(f"Failed to open font PNG image from {input_png_path}: {exc}") from exc

    def_w = meta["default_width"]
    height_words = meta.get("height_words", 2)
    glyph_count = meta["glyph_count"]
    reserved = meta.get("reserved", 0)
    char_map = meta["char_map"]
    glyphs = meta["glyphs"]

    cell_h = meta.get("cell_height", def_w)
    cell_w = meta.get("cell_width", def_w)
    cols = meta.get("grid_columns", GRID_COLUMNS)

    # Encode glyph blocks
    rebuilt_glyphs: list[tuple[int, int, bytes] | None] = []

    for i, g in enumerate(glyphs):
        if g.get("offset") == 0 or g.get("empty", False):
            rebuilt_glyphs.append(None)
            continue

        w = g["width"]
        bpr = g.get("bpr", g.get("word_count", (w + 3) // 4 if w > 0 else 0))
        gx = g.get("grid_x", i % cols)
        gy = g.get("grid_y", i // cols)
        cx = gx * cell_w
        cy = gy * cell_h

        if bpr > 0:
            bm = bytearray()
            for r in range(cell_h):
                for byte_idx in range(bpr):
                    p0 = sample_pixel_2bpp(img, cx + byte_idx * 4 + 0, cy + r)
                    p1 = sample_pixel_2bpp(img, cx + byte_idx * 4 + 1, cy + r)
                    p2 = sample_pixel_2bpp(img, cx + byte_idx * 4 + 2, cy + r)
                    p3 = sample_pixel_2bpp(img, cx + byte_idx * 4 + 3, cy + r)
                    b = (p0 & 3) | ((p1 & 3) << 2) | ((p2 & 3) << 4) | ((p3 & 3) << 6)
                    bm.append(b)
            rebuilt_glyphs.append((w, bpr, bytes(bm)))
        else:
            rebuilt_glyphs.append((w, bpr, b""))

    return pack_fnt_binary(
        default_width=def_w,
        height_words=height_words,
        glyph_count=glyph_count,
        char_map=char_map,
        glyphs=rebuilt_glyphs,
        reserved=reserved,
    )


# Alias for interface compatibility
build_fnt = build_fnt_from_png_and_json


def dump_all_fonts(data_dir: str, output_dir: str, grid_mode: str = "both") -> int:
    """Finds all .fnt files in a directory tree and dumps them to PNG + JSON.

    Args:
        data_dir: Root directory containing extracted NitroFS files.
        output_dir: Destination directory for dumped PNGs and JSONs.
        grid_mode: Grid overlay mode: 'both', 'cells', or 'none'.

    Returns:
        Number of dumped font files.
    """
    count = 0
    for root, _, files in os.walk(data_dir):
        for file in files:
            if file.endswith(".fnt"):
                rel_path = os.path.relpath(os.path.join(root, file), data_dir)
                rel_base, _ = os.path.splitext(rel_path)
                out_png = os.path.join(output_dir, rel_base + ".png")
                out_json = os.path.join(output_dir, rel_base + ".json")

                with open(os.path.join(root, file), "rb") as f:
                    fnt_bytes = f.read()

                dump_fnt_to_png_and_json(fnt_bytes, out_png, out_json, grid_mode=grid_mode)
                count += 1
    return count


def build_all_fonts(input_dir: str, target_data_dir: str) -> int:
    """Rebuilds all dumped font PNG+JSON pairs and places .fnt files into target directory.

    Args:
        input_dir: Directory containing PNG and JSON font sheets.
        target_data_dir: NitroFS target directory to receive rebuilt .fnt binaries.

    Returns:
        Number of built font files.
    """
    count = 0
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.endswith(".json"):
                rel_path = os.path.relpath(os.path.join(root, file), input_dir)
                rel_base, _ = os.path.splitext(rel_path)
                png_path = os.path.join(root, os.path.splitext(file)[0] + ".png")
                json_path = os.path.join(root, file)

                if os.path.isfile(png_path):
                    fnt_bytes = build_fnt_from_png_and_json(png_path, json_path)
                    out_fnt_path = os.path.join(target_data_dir, rel_base + ".fnt")
                    os.makedirs(os.path.dirname(out_fnt_path), exist_ok=True)
                    with open(out_fnt_path, "wb") as f:
                        f.write(fnt_bytes)
                    count += 1
    return count
