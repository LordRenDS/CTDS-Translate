"""Font subpackage for Chrono Trigger DS font parsing, rendering, and localization."""

from src.font.cyrillic_injector import (
    inject_cyrillic_font,
    inject_cyrillic_into_fnt,
    load_cyrillic_glyphs_from_assets,
)
from src.font.formats import (
    FONT_MAGIC,
    GRID_COLUMNS,
    GRID_COLOR_CELL,
    GRID_COLOR_WIDTH,
    PALETTE_2BPP,
)
from src.font.rasterizer import (
    build_all_fonts,
    build_fnt,
    build_fnt_from_png_and_json,
    dump_all_fonts,
    dump_fnt,
    dump_fnt_to_png_and_json,
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
