"""Font Engine for Chrono Trigger DS (.fnt format).

Handles extracting proprietary 2bpp font binaries into editable PNG glyph sheets
and JSON metric descriptors, bit-exact rebuilding of .fnt binaries from PNG+JSON,
and injecting 66 Cyrillic characters (А..Я, а..я, Ё, ё) for localization.
"""

import json
import math
import os
import struct
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

FONT_MAGIC = b"FONT"
GRID_COLUMNS = 16

GRID_COLOR_CELL = 4   # (50, 80, 140) - Muted slate blue for cell boundaries
GRID_COLOR_WIDTH = 5  # (180, 70, 50) - Muted coral red for glyph width marker

# Standard 2bpp palette expanded with guide colors:
# 0: Transparent/Black (0,0,0)
# 1: Main font body/White (255,255,255)
# 2: Anti-aliasing/Light Gray (180,180,180)
# 3: Outline/Shadow/Dark Gray (90,90,90)
# 4: Cell border grid (50,80,140)
# 5: Glyph width boundary (180,70,50)
PALETTE_2BPP = [
    0, 0, 0,
    255, 255, 255,
    180, 180, 180,
    90, 90, 90,
    50, 80, 140,
    180, 70, 50,
] + [0] * (256 * 3 - 18)

# Cyrillic character sets
CYRILLIC_UPPER = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"  # 32 chars: 0x80..0x9F
CYRILLIC_LOWER = "абвгдежзийклмнопрстуфхцчшщъыьэюя"  # 32 chars: 0xA0..0xBF
CYRILLIC_SPECIAL = [("Ё", 0xC0), ("ё", 0xC1)]          # 2 chars: 0xC0, 0xC1

# Candidate system fonts for TTF rendering fallback
FALLBACK_SYSTEM_FONTS = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/seguiemj.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _get_char_repr(char_code: int) -> str:
    """Returns a readable representation of a character bytecode index."""
    if char_code == 0x09:
        return "{TAB}"
    if 0x1F <= char_code <= 0x7D:
        return chr(char_code + 1)
    if 0x80 <= char_code <= 0x9F:
        return chr(0x0410 + (char_code - 0x80))
    if 0xA0 <= char_code <= 0xBF:
        return chr(0x0430 + (char_code - 0xA0))
    if char_code == 0xC0:
        return "Ё"
    if char_code == 0xC1:
        return "ё"
    return f"0x{char_code:02X}"


def _find_offsets_start(fnt_bytes: bytes, glyph_count: int) -> int:
    """Dynamically locates the start byte offset of the uint32 offset table."""
    table_size = glyph_count * 4
    for cand_start in range(14, len(fnt_bytes) - table_size + 1, 2):
        cand_offsets = struct.unpack(f"<{glyph_count}I", fnt_bytes[cand_start : cand_start + table_size])
        non_zeros = [o for o in cand_offsets if o > 0]
        if non_zeros and min(non_zeros) == cand_start + table_size:
            return cand_start
    return 0x10C


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
        ValueError: If header magic is invalid, binary is corrupted, or grid_mode is unknown.
    """
    if grid_mode not in ("both", "cells", "none"):
        raise ValueError(f"Invalid grid_mode: {grid_mode!r}. Must be 'both', 'cells', or 'none'.")

    if len(fnt_bytes) < 14:
        raise ValueError("Invalid FNT binary: file size too small")

    zeros = fnt_bytes[:4]
    magic = fnt_bytes[4:8]
    if magic != FONT_MAGIC:
        raise ValueError(f"Invalid FNT magic: expected {FONT_MAGIC!r}, got {magic!r}")

    def_w, height_words, glyph_count, reserved = struct.unpack("<BBHH", fnt_bytes[8:14])
    cell_h = def_w  # Glyph height equals default_width (10 for big, 8 for small)

    offsets_start = _find_offsets_start(fnt_bytes, glyph_count)
    char_map_len = (offsets_start - 14) // 2
    char_map = list(struct.unpack(f"<{char_map_len}H", fnt_bytes[14 : 14 + char_map_len * 2]))
    offsets = list(struct.unpack(f"<{glyph_count}I", fnt_bytes[offsets_start : offsets_start + glyph_count * 4]))

    # Build reverse map for character representation
    glyph_to_char: Dict[int, str] = {}
    for code, g_idx in enumerate(char_map):
        if g_idx != 0xFFFF and g_idx not in glyph_to_char:
            glyph_to_char[g_idx] = _get_char_repr(code)

    # Determine max bytes per row across glyphs to establish cell width
    max_bpr = max([fnt_bytes[off + 1] for off in offsets if off > 0] or [1])
    cell_w = max(def_w, max_bpr * 4)

    cols = GRID_COLUMNS
    rows = math.ceil(glyph_count / cols) if glyph_count > 0 else 1

    img = Image.new("P", (cols * cell_w, rows * cell_h), 0)
    img.putpalette(PALETTE_2BPP)

    glyphs_meta: List[Dict[str, Any]] = []

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
    os.makedirs(os.path.dirname(os.path.abspath(output_png_path)), exist_ok=True)
    img.save(output_png_path)

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

    os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


# Alias for interface compatibility
dump_fnt = dump_fnt_to_png_and_json


def _sample_pixel_2bpp(img: Image.Image, x: int, y: int) -> int:
    """Samples a single 2bpp pixel (0..3) from an image regardless of color mode.

    Grid guide lines (palette index >= 4 or colored RGB guide pixels) are automatically
    treated as background (0).
    """
    if x >= img.width or y >= img.height or x < 0 or y < 0:
        return 0

    mode = img.mode
    if mode == "P":
        val = img.getpixel((x, y))
        if val >= 4:
            return 0
        return val % 4
    elif mode in ("RGBA", "RGB", "LA", "L"):
        px = img.getpixel((x, y))
        if mode == "RGBA":
            r, g, b, a = px
            if a < 32:
                return 0
            if max(r, g, b) - min(r, g, b) > 20:
                # Colored grid guide line (slate blue or coral red)
                return 0
            lum = int(0.299 * r + 0.587 * g + 0.114 * b)
        elif mode == "RGB":
            r, g, b = px
            if max(r, g, b) - min(r, g, b) > 20:
                # Colored grid guide line
                return 0
            lum = int(0.299 * r + 0.587 * g + 0.114 * b)
        elif mode == "LA":
            l, a = px
            if a < 32:
                return 0
            lum = l
        else:  # L
            lum = px

        if lum < 32:
            return 0
        elif lum > 200:
            return 1
        elif lum >= 130:
            return 2
        else:
            return 3

    return 0


def build_fnt_from_png_and_json(input_png_path: str, input_json_path: str) -> bytes:
    """Rebuilds a .fnt binary from a PNG glyph sheet and JSON metadata descriptor.

    Guarantees 1:1 bit-exact roundtrip against the original game binary.

    Args:
        input_png_path: Path to the PNG glyph sheet image.
        input_json_path: Path to the metadata JSON file.

    Returns:
        Exact binary .fnt data.

    Raises:
        ValueError: If JSON metadata or PNG image is malformed.
    """
    with open(input_json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    img = Image.open(input_png_path)

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
    rebuilt_glyphs: List[Optional[Tuple[int, int, bytes]]] = []

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
                    p0 = _sample_pixel_2bpp(img, cx + byte_idx * 4 + 0, cy + r)
                    p1 = _sample_pixel_2bpp(img, cx + byte_idx * 4 + 1, cy + r)
                    p2 = _sample_pixel_2bpp(img, cx + byte_idx * 4 + 2, cy + r)
                    p3 = _sample_pixel_2bpp(img, cx + byte_idx * 4 + 3, cy + r)
                    b = (p0 & 3) | ((p1 & 3) << 2) | ((p2 & 3) << 4) | ((p3 & 3) << 6)
                    bm.append(b)
            rebuilt_glyphs.append((w, bpr, bytes(bm)))
        else:
            rebuilt_glyphs.append((w, bpr, b""))

    # Assemble binary
    out = bytearray()
    out.extend(b"\x00\x00\x00\x00")
    out.extend(FONT_MAGIC)
    out.extend(struct.pack("<BBHH", def_w, height_words, glyph_count, reserved))
    out.extend(struct.pack(f"<{len(char_map)}H", *char_map))

    offsets_start = len(out)
    # Reserve space for 32-bit offsets
    out.extend(b"\x00" * (glyph_count * 4))

    offsets: List[int] = []
    for g_data in rebuilt_glyphs:
        if g_data is None:
            offsets.append(0)
        else:
            w, bpr, bm = g_data
            cur_off = len(out)
            offsets.append(cur_off)
            out.extend(struct.pack("<BB", w, bpr))
            out.extend(bm)

    # Write back offset table
    out[offsets_start : offsets_start + glyph_count * 4] = struct.pack(f"<{glyph_count}I", *offsets)

    return bytes(out)


# Alias for interface compatibility
build_fnt = build_fnt_from_png_and_json


def _render_cyrillic_glyph_2bpp(
    char: str,
    cell_h: int,
    font_path: Optional[str] = None,
) -> Tuple[int, int, bytes]:
    """Renders a single Cyrillic character into 2bpp bitmap with outline/shadow.

    Args:
        char: Single Cyrillic character string.
        cell_h: Glyph cell height (10 for big, 8 for small).
        font_path: Optional path to TTF font file.

    Returns:
        Tuple of (width, bpr, bitmap_bytes).
    """
    font_size = 9 if cell_h >= 10 else 7
    font = None

    if font_path and os.path.isfile(font_path):
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            font = None

    if font is None:
        for candidate in FALLBACK_SYSTEM_FONTS:
            if os.path.isfile(candidate):
                try:
                    font = ImageFont.truetype(candidate, font_size)
                    break
                except Exception:
                    continue

    if font is None:
        font = ImageFont.load_default()

    canvas_w = 16
    img = Image.new("L", (canvas_w, cell_h), 0)
    draw = ImageDraw.Draw(img)

    bbox = draw.textbbox((0, 0), char, font=font)
    text_h = max(1, bbox[3] - bbox[1])
    y_off = max(0, (cell_h - text_h) // 2 - 1) if cell_h >= 10 else max(0, (cell_h - text_h) // 2)

    draw.text((1, y_off), char, fill=255, font=font)

    # Calculate actual character bounds
    max_x = 0
    for y in range(cell_h):
        for x in range(canvas_w):
            if img.getpixel((x, y)) > 48:
                max_x = max(max_x, x)

    width = max(3, min(12, max_x + 2))

    # Construct 2bpp grid with body (1) and shadow (3)
    grid = [[0] * width for _ in range(cell_h)]
    for y in range(cell_h):
        for x in range(width):
            if img.getpixel((x, y)) > 96:
                grid[y][x] = 1

    # Add drop shadow / border to match Chrono Trigger font style
    for y in range(cell_h):
        for x in range(width):
            if grid[y][x] == 1:
                for dy, dx in [(0, 1), (1, 0), (1, 1)]:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < cell_h and 0 <= nx < width and grid[ny][nx] == 0:
                        grid[ny][nx] = 3

    bpr = (width + 3) // 4
    bm = bytearray()
    for y in range(cell_h):
        for byte_idx in range(bpr):
            p0 = grid[y][byte_idx * 4 + 0] if byte_idx * 4 + 0 < width else 0
            p1 = grid[y][byte_idx * 4 + 1] if byte_idx * 4 + 1 < width else 0
            p2 = grid[y][byte_idx * 4 + 2] if byte_idx * 4 + 2 < width else 0
            p3 = grid[y][byte_idx * 4 + 3] if byte_idx * 4 + 3 < width else 0
            bm.append((p0 & 3) | ((p1 & 3) << 2) | ((p2 & 3) << 4) | ((p3 & 3) << 6))

    return width, bpr, bytes(bm)


def load_cyrillic_glyphs_from_assets(
    cell_h: int,
    assets_dir: Optional[str] = None,
) -> Optional[Dict[str, Tuple[int, int, bytes]]]:
    """Loads pre-rendered Cyrillic pixel glyphs from PNG+JSON asset templates.

    Args:
        cell_h: Font cell height (8 for small, 10 for big).
        assets_dir: Optional directory containing cyrillic_small/big PNG and JSON templates.

    Returns:
        Mapping of character string -> (width, bpr, bitmap_bytes), or None if templates not found.
    """
    search_dirs: List[str] = []
    if assets_dir:
        search_dirs.append(assets_dir)
    module_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(module_dir)
    search_dirs.append(os.path.join(project_root, "assets", "fonts"))
    search_dirs.append(os.path.join(os.getcwd(), "assets", "fonts"))
    search_dirs.append(os.path.join("assets", "fonts"))

    prefix = "cyrillic_small" if cell_h <= 8 else "cyrillic_big"
    png_path = None
    json_path = None

    for d in search_dirs:
        cand_png = os.path.join(d, f"{prefix}.png")
        cand_json = os.path.join(d, f"{prefix}.json")
        if os.path.isfile(cand_png) and os.path.isfile(cand_json):
            png_path = cand_png
            json_path = cand_json
            break

    if not png_path or not json_path:
        return None

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        img = Image.open(png_path)
        cell_w = meta.get("cell_width", cell_h)
        cols = meta.get("grid_columns", 16)

        glyphs_dict: Dict[str, Tuple[int, int, bytes]] = {}
        for item in meta.get("glyphs", []):
            char = item["char"]
            w = item["width"]
            bpr = item.get("bpr", (w + 3) // 4)
            gx = item.get("grid_x", item["index"] % cols)
            gy = item.get("grid_y", item["index"] // cols)
            cx = gx * cell_w
            cy = gy * cell_h

            bm = bytearray()
            for r in range(cell_h):
                for byte_idx in range(bpr):
                    p0 = _sample_pixel_2bpp(img, cx + byte_idx * 4 + 0, cy + r)
                    p1 = _sample_pixel_2bpp(img, cx + byte_idx * 4 + 1, cy + r)
                    p2 = _sample_pixel_2bpp(img, cx + byte_idx * 4 + 2, cy + r)
                    p3 = _sample_pixel_2bpp(img, cx + byte_idx * 4 + 3, cy + r)
                    bm.append((p0 & 3) | ((p1 & 3) << 2) | ((p2 & 3) << 4) | ((p3 & 3) << 6))

            glyphs_dict[char] = (w, bpr, bytes(bm))

        return glyphs_dict
    except Exception:
        return None


def inject_cyrillic_into_fnt(
    original_fnt_bytes: bytes,
    ttf_font_path: Optional[str] = None,
    assets_dir: Optional[str] = None,
) -> bytes:
    """Extends a .fnt binary with 66 Cyrillic glyphs (А..Я, а..я, Ё, ё) starting at glyph index 450.

    Preserves the standard 127-entry char_map (0x0E..0x10C) so that the uint32 glyph offset
    table starts at fixed offset 0x10C expected by the Chrono Trigger DS ARM9 engine.

    By default, loads pixel-crafted glyph templates from assets/fonts/ (matching the original
    game font style). If ttf_font_path is explicitly provided, it rasterizes the TTF instead.

    Args:
        original_fnt_bytes: Clean original .fnt binary data.
        ttf_font_path: Optional path to a TTF font file for Cyrillic rasterization override.
        assets_dir: Optional path to directory containing custom cyrillic_small/big templates.

    Returns:
        Extended .fnt binary data containing Cyrillic glyphs with valid 0x10C offset table.

    Raises:
        ValueError: If input binary is invalid or corrupted.
    """
    if len(original_fnt_bytes) < 14:
        raise ValueError("Invalid FNT binary: file size too small")

    zeros = original_fnt_bytes[:4]
    magic = original_fnt_bytes[4:8]
    if magic != FONT_MAGIC:
        raise ValueError(f"Invalid FNT magic: expected {FONT_MAGIC!r}, got {magic!r}")

    def_w, height_words, orig_glyph_count, reserved = struct.unpack("<BBHH", original_fnt_bytes[8:14])
    cell_h = def_w

    # Standard Chrono Trigger DS font header has exactly 127 char_map entries (254 bytes) from 14 to 0x10C
    char_map = list(struct.unpack("<127H", original_fnt_bytes[14:0x10C]))
    offsets = list(struct.unpack(f"<{orig_glyph_count}I", original_fnt_bytes[0x10C : 0x10C + orig_glyph_count * 4]))

    # Extract all existing glyph data blocks
    glyphs: List[Optional[Tuple[int, int, bytes]]] = []
    for off in offsets:
        if off == 0:
            glyphs.append(None)
        else:
            w = original_fnt_bytes[off]
            bpr = original_fnt_bytes[off + 1]
            bm = original_fnt_bytes[off + 2 : off + 2 + bpr * cell_h]
            glyphs.append((w, bpr, bm))

    # Pad glyphs list up to CYRILLIC_BASE_GLYPH (450) to prevent collisions with game control codes
    CYRILLIC_BASE_GLYPH = 450
    while len(glyphs) < CYRILLIC_BASE_GLYPH:
        glyphs.append(None)

    # Load pixel art templates from assets (unless explicit TTF override was provided)
    pixel_glyphs = None
    if not ttf_font_path:
        pixel_glyphs = load_cyrillic_glyphs_from_assets(cell_h, assets_dir)

    def _get_glyph(ch: str) -> Tuple[int, int, bytes]:
        if pixel_glyphs and ch in pixel_glyphs:
            return pixel_glyphs[ch]
        return _render_cyrillic_glyph_2bpp(ch, cell_h, ttf_font_path)

    # Inject Uppercase Cyrillic (0x80..0x9F -> glyphs 450..481)
    for ch in CYRILLIC_UPPER:
        glyphs.append(_get_glyph(ch))

    # Inject Lowercase Cyrillic (0xA0..0xBF -> glyphs 482..513)
    for ch in CYRILLIC_LOWER:
        glyphs.append(_get_glyph(ch))

    # Inject Cyrillic Ё and ё (glyphs 514, 515)
    for ch, _code in CYRILLIC_SPECIAL:
        glyphs.append(_get_glyph(ch))

    new_glyph_count = len(glyphs)

    # Rebuild new binary
    out = bytearray()
    out.extend(zeros)
    out.extend(magic)
    out.extend(struct.pack("<BBHH", def_w, height_words, new_glyph_count, reserved))
    out.extend(struct.pack("<127H", *char_map))

    assert len(out) == 0x10C, f"Header size mismatch: {len(out)} != 0x10C"

    # Reserve space for 32-bit offsets starting at 0x10C
    new_offsets_start = 0x10C
    out.extend(b"\x00" * (new_glyph_count * 4))

    new_offsets: List[int] = []
    for g_data in glyphs:
        if g_data is None:
            new_offsets.append(0)
        else:
            w, bpr, bm = g_data
            cur_off = len(out)
            new_offsets.append(cur_off)
            out.extend(struct.pack("<BB", w, bpr))
            out.extend(bm)

    out[new_offsets_start : new_offsets_start + new_glyph_count * 4] = struct.pack(f"<{new_glyph_count}I", *new_offsets)
    return bytes(out)


# Alias for interface compatibility
inject_cyrillic_font = inject_cyrillic_into_fnt


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
