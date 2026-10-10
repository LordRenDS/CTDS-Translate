"""Cyrillic glyph definitions, rendering fallbacks, and font injection routines."""

import json
import os
from pathlib import Path
import struct
from PIL import Image, ImageDraw, ImageFont

from src.core.exceptions import FontError
from src.font.formats import (
    FONT_MAGIC,
    pack_fnt_binary,
    sample_pixel_2bpp,
)

# Cyrillic character sets
CYRILLIC_UPPER: str = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"  # 32 chars: 0x80..0x9F
CYRILLIC_LOWER: str = "абвгдежзийклмнопрстуфхцчшщъыьэюя"  # 32 chars: 0xA0..0xBF
CYRILLIC_SPECIAL: list[tuple[str, int]] = [("Ё", 0xC0), ("ё", 0xC1)]  # 2 chars: 0xC0, 0xC1

# Candidate system fonts for TTF rendering fallback
FALLBACK_SYSTEM_FONTS: list[str] = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/seguiemj.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

__all__ = [
    "CYRILLIC_LOWER",
    "CYRILLIC_SPECIAL",
    "CYRILLIC_UPPER",
    "FALLBACK_SYSTEM_FONTS",
    "inject_cyrillic_font",
    "inject_cyrillic_into_fnt",
    "load_cyrillic_glyphs_from_assets",
    "render_cyrillic_glyph_2bpp",
    "_render_cyrillic_glyph_2bpp",
]


def render_cyrillic_glyph_2bpp(
    char: str,
    cell_h: int,
    font_path: str | None = None,
) -> tuple[int, int, bytes]:
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
        except OSError:
            font = None

    if font is None:
        for candidate in FALLBACK_SYSTEM_FONTS:
            if os.path.isfile(candidate):
                try:
                    font = ImageFont.truetype(candidate, font_size)
                    break
                except OSError:
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


_render_cyrillic_glyph_2bpp = render_cyrillic_glyph_2bpp


def load_cyrillic_glyphs_from_assets(
    cell_h: int,
    assets_dir: str | None = None,
) -> dict[str, tuple[int, int, bytes]] | None:
    """Loads pre-rendered Cyrillic pixel glyphs from PNG+JSON asset templates.

    Args:
        cell_h: Font cell height (8 for small, 10 for big).
        assets_dir: Optional directory containing cyrillic_small/big PNG and JSON templates.

    Returns:
        Mapping of character string -> (width, bpr, bitmap_bytes), or None if templates not found.
    """
    search_dirs: list[str] = []
    if assets_dir:
        search_dirs.append(assets_dir)

    pkg_dir = Path(__file__).resolve().parent  # src/font
    src_dir = pkg_dir.parent  # src
    project_root = src_dir.parent  # repo root

    search_dirs.append(str(project_root / "assets" / "fonts"))
    search_dirs.append(str(Path.cwd() / "assets" / "fonts"))
    search_dirs.append(os.path.join("assets", "fonts"))
    search_dirs.append(str(src_dir / "assets" / "fonts"))

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

        glyphs_dict: dict[str, tuple[int, int, bytes]] = {}
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
                    p0 = sample_pixel_2bpp(img, cx + byte_idx * 4 + 0, cy + r)
                    p1 = sample_pixel_2bpp(img, cx + byte_idx * 4 + 1, cy + r)
                    p2 = sample_pixel_2bpp(img, cx + byte_idx * 4 + 2, cy + r)
                    p3 = sample_pixel_2bpp(img, cx + byte_idx * 4 + 3, cy + r)
                    bm.append((p0 & 3) | ((p1 & 3) << 2) | ((p2 & 3) << 4) | ((p3 & 3) << 6))

            glyphs_dict[char] = (w, bpr, bytes(bm))

        return glyphs_dict
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return None


def inject_cyrillic_into_fnt(
    original_fnt_bytes: bytes,
    ttf_font_path: str | None = None,
    assets_dir: str | None = None,
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
        FontError: If input binary is invalid or corrupted.
    """
    if len(original_fnt_bytes) < 14:
        raise FontError("Invalid FNT binary: file size too small")

    zeros = original_fnt_bytes[:4]
    magic = original_fnt_bytes[4:8]
    if magic != FONT_MAGIC:
        raise FontError(f"Invalid FNT magic: expected {FONT_MAGIC!r}, got {magic!r}")

    def_w, height_words, orig_glyph_count, reserved = struct.unpack("<BBHH", original_fnt_bytes[8:14])
    cell_h = def_w

    # Standard Chrono Trigger DS font header has exactly 127 char_map entries (254 bytes) from 14 to 0x10C
    char_map = list(struct.unpack("<127H", original_fnt_bytes[14:0x10C]))
    offsets = list(struct.unpack(f"<{orig_glyph_count}I", original_fnt_bytes[0x10C : 0x10C + orig_glyph_count * 4]))

    # Extract all existing glyph data blocks
    glyphs: list[tuple[int, int, bytes] | None] = []
    for off in offsets:
        if off == 0:
            glyphs.append(None)
        else:
            w = original_fnt_bytes[off]
            bpr = original_fnt_bytes[off + 1]
            bm = original_fnt_bytes[off + 2 : off + 2 + bpr * cell_h]
            glyphs.append((w, bpr, bm))

    # Pad glyphs list up to CYRILLIC_BASE_GLYPH (450) to prevent collisions with game control codes
    cyrillic_base_glyph = 450
    while len(glyphs) < cyrillic_base_glyph:
        glyphs.append(None)

    # Load pixel art templates from assets (unless explicit TTF override was provided)
    pixel_glyphs = None
    if not ttf_font_path:
        pixel_glyphs = load_cyrillic_glyphs_from_assets(cell_h, assets_dir)

    def _get_glyph(ch: str) -> tuple[int, int, bytes]:
        if pixel_glyphs and ch in pixel_glyphs:
            return pixel_glyphs[ch]
        return render_cyrillic_glyph_2bpp(ch, cell_h, ttf_font_path)

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

    return pack_fnt_binary(
        default_width=def_w,
        height_words=height_words,
        glyph_count=new_glyph_count,
        char_map=char_map,
        glyphs=glyphs,
        reserved=reserved,
        zeros=zeros,
    )


# Alias for interface compatibility
inject_cyrillic_font = inject_cyrillic_into_fnt
