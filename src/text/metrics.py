"""Proportional font metrics, glyph loading, and line width measurement."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any

from src.char_map import BIG_CHAR_TO_GLYPH

__all__ = [
    "DEFAULT_CHAR_WIDTH_PX",
    "DEFAULT_HERO_NAME_WIDTH_PX",
    "DEFAULT_SPACE_WIDTH_PX",
    "GLYPH_PATTERN",
    "HERO_PATTERN",
    "HERO_TOKENS",
    "PLACEHOLDER_PATTERN",
    "TAG_REGEX",
    "GlyphWidths",
    "calculate_line_width_px",
    "load_glyph_metrics",
    "strip_control_tags",
]

# Dynamic hero name tokens that represent variable visual text in-game
HERO_TOKENS = frozenset({
    "{CRONO}",
    "{MARLE}",
    "{LUCCA}",
    "{ROBO}",
    "{FROG}",
    "{AYLA}",
    "{MAGUS}",
    "{EPOCH}",
})

HERO_PATTERN = re.compile(r"\{(?:CRONO|MARLE|LUCCA|ROBO|FROG|AYLA|MAGUS|EPOCH)\}")
GLYPH_PATTERN = re.compile(r"^\{GLYPH:\d+\}$")
PLACEHOLDER_PATTERN = re.compile(
    r"\{(?:(CRONO|MARLE|LUCCA|ROBO|FROG|AYLA|MAGUS|EPOCH)|GLYPH:(\d+))\}"
)
TAG_REGEX = re.compile(r"\{[^{}]+\}")

DEFAULT_CHAR_WIDTH_PX = 5
DEFAULT_SPACE_WIDTH_PX = 3
DEFAULT_HERO_NAME_WIDTH_PX = 30


class GlyphWidths(dict[str, int]):
    """Dictionary mapping characters to their pixel widths with a 5px fallback."""

    def __init__(
        self,
        *args: Any,
        glyph_by_idx: dict[int, int] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.glyph_by_idx: dict[int, int] = glyph_by_idx if glyph_by_idx is not None else {}

    def __missing__(self, key: str) -> int:
        return DEFAULT_CHAR_WIDTH_PX

    def get(self, key: str, default: Any = DEFAULT_CHAR_WIDTH_PX) -> int:
        return super().get(key, default)


def strip_control_tags(text: str) -> str:
    """Strips non-visual control tags while preserving dynamic hero name tokens and glyphs.

    Args:
        text: Input string with control tokens (e.g., {WAIT_KEY}, {PAGE}, {CRONO}, {GLYPH:12}).

    Returns:
        String with non-visual control tokens removed.
    """
    text = re.sub(r"\{GLYPH:405\}[0-9a-fA-F]+\{GLYPH:406\}", "", text)
    text = re.sub(r"\{GLYPH:407\}[0-9a-fA-F]+\{GLYPH:408\}", "", text)
    text = re.sub(r"\{GLYPH:40[5-8]\}", "", text)

    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in HERO_TOKENS or GLYPH_PATTERN.match(token):
            return token
        return ""

    return TAG_REGEX.sub(_replace, text)


def load_glyph_metrics(
    font_json_path: str | Path,
    cyrillic_json_path: str | Path | None = None,
) -> GlyphWidths:
    """Loads font glyph widths from base font JSON and optional Cyrillic overlay.

    Args:
        font_json_path: Path to base font JSON (e.g., extracted fonts/msg/big/msgcmn.json).
        cyrillic_json_path: Optional path to Cyrillic font JSON (e.g., assets/fonts/cyrillic_big.json).

    Returns:
        Mapping of characters to pixel widths with fallback for unmapped characters.

    Raises:
        FileNotFoundError: If font_json_path or cyrillic_json_path does not exist.
        json.JSONDecodeError: If JSON file cannot be parsed.
    """
    with open(font_json_path, "r", encoding="utf-8") as f:
        base_data = json.load(f)

    glyphs = base_data.get("glyphs", [])
    glyph_by_idx: dict[int, int] = {}
    for g in glyphs:
        if "index" in g and "width" in g:
            glyph_by_idx[g["index"]] = g["width"]

    # Load Cyrillic overlay if provided
    cyr_glyphs = []
    if cyrillic_json_path is not None:
        with open(cyrillic_json_path, "r", encoding="utf-8") as f:
            cyr_data = json.load(f)
        cyr_glyphs = cyr_data.get("glyphs", [])
        for g in cyr_glyphs:
            if "font_glyph_id" in g and "width" in g:
                glyph_by_idx[g["font_glyph_id"]] = g["width"]

    widths = GlyphWidths(glyph_by_idx=glyph_by_idx)

    # Map ASCII characters 0x1F..0x7D via char_map table if available
    char_map = base_data.get("char_map", [])
    for code in range(0x1F, min(len(char_map), 0x7E)):
        g_idx = char_map[code]
        if g_idx != 0xFFFF and g_idx in glyph_by_idx:
            widths[chr(code + 1)] = glyph_by_idx[g_idx]

    # Map characters using BIG_CHAR_TO_GLYPH table
    for ch, g_idx in BIG_CHAR_TO_GLYPH.items():
        if g_idx in glyph_by_idx:
            widths[ch] = glyph_by_idx[g_idx]

    # Map any single-character char_repr from base glyphs
    for g in glyphs:
        rep = g.get("char_repr")
        if rep and len(rep) == 1 and rep not in widths and "width" in g:
            widths[rep] = g["width"]

    # Map Cyrillic glyphs
    for g in cyr_glyphs:
        ch = g.get("char") or g.get("char_repr")
        if ch and "width" in g:
            widths[ch] = g["width"]

    # Ensure space character has its correct width
    if ' ' not in widths or widths[' '] <= 0:
        if 1 in glyph_by_idx:
            widths[' '] = glyph_by_idx[1]
        else:
            widths[' '] = DEFAULT_SPACE_WIDTH_PX

    return widths


def calculate_line_width_px(
    line: str,
    glyph_widths: dict[str, int],
    hero_name_width_px: int = DEFAULT_HERO_NAME_WIDTH_PX,
    default_char_width: int = DEFAULT_CHAR_WIDTH_PX,
) -> int:
    """Calculates the total pixel width of a single text line under proportional font metrics.

    Args:
        line: Text line to measure (may contain control tags or hero tokens).
        glyph_widths: Mapping from character to pixel width.
        hero_name_width_px: Pixel width assigned to dynamic hero name tokens.
        default_char_width: Pixel width assigned to characters missing in glyph_widths.

    Returns:
        Total width in pixels.
    """
    clean_line = strip_control_tags(line)
    if not clean_line:
        return 0

    total_width = 0
    last_end = 0

    for match in PLACEHOLDER_PATTERN.finditer(clean_line):
        prefix = clean_line[last_end:match.start()]
        for ch in prefix:
            if ch in ('\r', '\n'):
                continue
            total_width += glyph_widths.get(ch, default_char_width)

        hero_token, glyph_idx_str = match.groups()
        if hero_token is not None:
            total_width += hero_name_width_px
        elif glyph_idx_str is not None:
            glyph_idx = int(glyph_idx_str)
            glyph_by_idx = getattr(glyph_widths, "glyph_by_idx", None)
            if isinstance(glyph_by_idx, dict) and glyph_idx in glyph_by_idx:
                total_width += glyph_by_idx[glyph_idx]
            elif match.group(0) in glyph_widths:
                total_width += glyph_widths[match.group(0)]
            elif f"GLYPH:{glyph_idx}" in glyph_widths:
                total_width += glyph_widths[f"GLYPH:{glyph_idx}"]
            else:
                total_width += default_char_width

        last_end = match.end()

    suffix = clean_line[last_end:]
    for ch in suffix:
        if ch in ('\r', '\n'):
            continue
        total_width += glyph_widths.get(ch, default_char_width)

    return total_width
