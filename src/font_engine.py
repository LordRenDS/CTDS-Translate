"""Backward-compatible facade for src.font."""

from src.font import (
    FONT_MAGIC,
    GRID_COLUMNS,
    GRID_COLOR_CELL,
    GRID_COLOR_WIDTH,
    PALETTE_2BPP,
    build_all_fonts,
    build_fnt,
    build_fnt_from_png_and_json,
    dump_all_fonts,
    dump_fnt,
    dump_fnt_to_png_and_json,
    inject_cyrillic_font,
    inject_cyrillic_into_fnt,
    load_cyrillic_glyphs_from_assets,
)
from src.font.cyrillic_injector import (
    CYRILLIC_LOWER,
    CYRILLIC_SPECIAL,
    CYRILLIC_UPPER,
    FALLBACK_SYSTEM_FONTS,
    render_cyrillic_glyph_2bpp as _render_cyrillic_glyph_2bpp,
)
from src.font.formats import (
    find_offsets_start as _find_offsets_start,
    get_char_repr as _get_char_repr,
    sample_pixel_2bpp as _sample_pixel_2bpp,
)

__all__ = [
    "dump_fnt_to_png_and_json",
    "build_fnt_from_png_and_json",
    "dump_fnt",
    "build_fnt",
    "inject_cyrillic_into_fnt",
    "inject_cyrillic_font",
    "dump_all_fonts",
    "build_all_fonts",
    "load_cyrillic_glyphs_from_assets",
    "GRID_COLOR_CELL",
    "GRID_COLOR_WIDTH",
    "FONT_MAGIC",
    "GRID_COLUMNS",
    "PALETTE_2BPP",
]
