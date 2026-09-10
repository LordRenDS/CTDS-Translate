#!/usr/bin/env python3
"""Chrono Trigger DS - Title Menu Sprite Sheet Visual Layout Guide Generator.

Generates a high-resolution annotated image of the title logo sprite sheet
(`translated image/title/obj/obj_logo_new_layout_guide.png`) highlighting:
- Cell boundaries and IDs
- Individual OAM bounding boxes
- The x=48 word seam in Cells 0 and 1
- The 4px hardware gap in Cells 3 and 4
- Tile index ranges and coordinate rulers
- A comprehensive sidebar legend explaining why Russian text broke.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_IMAGE_TRANSLATED = PROJECT_ROOT / "translated image" / "title" / "obj" / "obj_logo_new.png"
DEFAULT_IMAGE_EXTRACTED = PROJECT_ROOT / "extracted image" / "title" / "obj" / "obj_logo_new.png"
DEFAULT_JSON_TRANSLATED = PROJECT_ROOT / "translated image" / "title" / "obj" / "obj_logo_new.json"
DEFAULT_JSON_EXTRACTED = PROJECT_ROOT / "extracted image" / "title" / "obj" / "obj_logo_new.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "translated image" / "title" / "obj" / "obj_logo_new_layout_guide.png"

# Color definitions for each cell
CELL_COLORS: dict[int, tuple[int, int, int]] = {
    0: (0, 229, 255),    # Cyan - Game Mode
    1: (0, 230, 118),    # Emerald - Battle Mode
    2: (41, 121, 255),   # Blue - Movies
    3: (255, 145, 0),    # Orange - Game Mode (Selected)
    4: (224, 64, 251),   # Fuchsia - Battle Mode (Selected)
    5: (29, 233, 182),   # Teal - Movies (Selected)
    6: (255, 82, 82),    # Coral - Mode Jeu (French)
    7: (198, 255, 0),    # Lime - Mode de combat (French)
    8: (255, 64, 129),   # Pink - Cinématiques (French)
    -1: (176, 190, 197), # Slate - Uncovered Tiles
}

CELL_NAMES: dict[int, str] = {
    0: "Game Mode (Normal)",
    1: "Battle Mode (Normal)",
    2: "Movies (Normal)",
    3: "Game Mode (Selected / Gap)",
    4: "Battle Mode (Selected / Gap)",
    5: "Movies (Selected)",
    6: "Mode Jeu (French)",
    7: "Mode de combat (French)",
    8: "Cinématiques (French)",
    -1: "Uncovered Tiles",
}


def load_fonts() -> dict[str, ImageFont.ImageFont]:
    """Load crisp TrueType fonts with fallbacks."""
    font_candidates = [
        ("segoeui.ttf", "segoeuib.ttf", "consola.ttf"),
        ("arial.ttf", "arialbd.ttf", "consola.ttf"),
        ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSansMono.ttf"),
    ]
    for reg, bold, mono in font_candidates:
        try:
            return {
                "title": ImageFont.truetype(bold, 20),
                "h2": ImageFont.truetype(bold, 14),
                "h3": ImageFont.truetype(bold, 12),
                "body": ImageFont.truetype(reg, 12),
                "body_bold": ImageFont.truetype(bold, 12),
                "small": ImageFont.truetype(reg, 10),
                "small_bold": ImageFont.truetype(bold, 10),
                "tiny": ImageFont.truetype(reg, 9),
                "tiny_bold": ImageFont.truetype(bold, 9),
                "mono": ImageFont.truetype(mono, 11),
                "mono_small": ImageFont.truetype(mono, 9),
                "ruler": ImageFont.truetype(mono, 10),
            }
        except Exception:
            continue

    def_font = ImageFont.load_default()
    return {k: def_font for k in [
        "title", "h2", "h3", "body", "body_bold", "small", "small_bold",
        "tiny", "tiny_bold", "mono", "mono_small", "ruler"
    ]}


def draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    pt1: tuple[int, int],
    pt2: tuple[int, int],
    color: tuple[int, int, int] | tuple[int, int, int, int],
    dash: int = 4,
    space: int = 3,
    width: int = 1,
) -> None:
    """Draw a dashed line between two points (horizontal or vertical)."""
    x1, y1 = pt1
    x2, y2 = pt2
    if y1 == y2:  # Horizontal
        start_x, end_x = min(x1, x2), max(x1, x2)
        curr = start_x
        while curr < end_x:
            seg_end = min(curr + dash, end_x)
            draw.line([(curr, y1), (seg_end, y1)], fill=color, width=width)
            curr += dash + space
    elif x1 == x2:  # Vertical
        start_y, end_y = min(y1, y2), max(y1, y2)
        curr = start_y
        while curr < end_y:
            seg_end = min(curr + dash, end_y)
            draw.line([(x1, curr), (x1, seg_end)], fill=color, width=width)
            curr += dash + space
    else:
        draw.line([pt1, pt2], fill=color, width=width)


def draw_dashed_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    color: tuple[int, int, int] | tuple[int, int, int, int],
    dash: int = 4,
    space: int = 3,
    width: int = 1,
) -> None:
    """Draw a dashed rectangle."""
    x1, y1, x2, y2 = box
    draw_dashed_line(draw, (x1, y1), (x2, y1), color, dash, space, width)
    draw_dashed_line(draw, (x2, y1), (x2, y2), color, dash, space, width)
    draw_dashed_line(draw, (x2, y2), (x1, y2), color, dash, space, width)
    draw_dashed_line(draw, (x1, y2), (x1, y1), color, dash, space, width)


def draw_hazard_hatch(
    target_img: Image.Image,
    box: tuple[int, int, int, int],
    color1: tuple[int, int, int, int] = (255, 214, 0, 230),
    color2: tuple[int, int, int, int] = (20, 20, 20, 210),
    stripe_width: int = 4,
) -> None:
    """Draw a strictly clipped hazard warning diagonal hatch pattern inside a bounding box."""
    x1, y1, x2, y2 = box
    w = max(1, x2 - x1)
    h = max(1, y2 - y1)

    # Isolated overlay image guarantees 0 pixel overflow
    overlay = Image.new("RGBA", (w, h), (255, 214, 0, 60))
    ov_draw = ImageDraw.Draw(overlay)

    # Diagonal stripes
    step = stripe_width * 2
    for offset in range(-h, w + h, step):
        ov_draw.line(
            [(offset, 0), (offset + h, h)],
            fill=color1,
            width=stripe_width,
        )

    # Bright yellow border
    ov_draw.rectangle([(0, 0), (w - 1, h - 1)], outline=(255, 235, 59, 255), width=2)
    target_img.alpha_composite(overlay, (x1, y1))


def render_layout_guide(
    image_path: Path,
    json_path: Path,
    output_path: Path,
    scale: int = 4,
) -> Path:
    """Generate visual layout guide."""
    if not image_path.is_file():
        raise FileNotFoundError(f"Input sprite sheet not found: {image_path}")
    if not json_path.is_file():
        raise FileNotFoundError(f"Metadata JSON not found: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    raw_img = Image.open(image_path).convert("RGBA")
    sheet_w, sheet_h = raw_img.size

    # Canvas dimensions & margins
    ruler_left = 64
    ruler_top = 54
    sheet_scaled_w = sheet_w * scale
    sheet_scaled_h = sheet_h * scale
    sidebar_w = 480
    margin_right = 24
    margin_bottom = 30

    total_w = ruler_left + sheet_scaled_w + 24 + sidebar_w + margin_right
    total_h = ruler_top + sheet_scaled_h + margin_bottom

    # Canvas
    bg_color = (21, 24, 33, 255)  # Dark slate
    guide_img = Image.new("RGBA", (total_w, total_h), bg_color)
    draw = ImageDraw.Draw(guide_img, "RGBA")
    fonts = load_fonts()

    # Position of sprite sheet
    ox = ruler_left
    oy = ruler_top

    # Draw sheet background and sprite sheet (scaled crisp nearest-neighbor)
    scaled_sheet = raw_img.resize((sheet_scaled_w, sheet_scaled_h), Image.Resampling.NEAREST)
    guide_img.paste(scaled_sheet, (ox, oy), scaled_sheet)

    # Draw faint 8x8 tile grid (at scale: every 8*scale px)
    grid_color = (255, 255, 255, 22)
    tile_scaled = 8 * scale
    for tx in range(0, sheet_scaled_w + 1, tile_scaled):
        draw.line([(ox + tx, oy), (ox + tx, oy + sheet_scaled_h)], fill=grid_color, width=1)
    for ty in range(0, sheet_scaled_h + 1, tile_scaled):
        draw.line([(ox, oy + ty), (ox + sheet_scaled_w, oy + ty)], fill=grid_color, width=1)

    # -------------------------------------------------------------
    # Coordinate Rulers
    # -------------------------------------------------------------
    ruler_bg = (28, 32, 45, 255)
    ruler_line = (70, 78, 105, 255)
    text_color = (180, 190, 215, 255)

    # Top ruler
    draw.rectangle([(ox, 0), (ox + sheet_scaled_w, ruler_top - 4)], fill=ruler_bg)
    draw.line([(ox, ruler_top - 4), (ox + sheet_scaled_w, ruler_top - 4)], fill=ruler_line, width=1)
    for px in range(0, sheet_w + 1, 8):
        x = ox + px * scale
        is_major = (px % 32 == 0)
        is_mid = (px % 16 == 0) and not is_major
        tick_h = 16 if is_major else (10 if is_mid else 6)
        draw.line([(x, ruler_top - 4), (x, ruler_top - 4 - tick_h)], fill=ruler_line, width=1)
        if is_major or px == sheet_w or px in (48, 52, 96, 112):
            lbl = str(px)
            bbox = fonts["ruler"].getbbox(lbl)
            w_lbl = bbox[2] - bbox[0]
            draw.text((x - w_lbl // 2, ruler_top - 4 - tick_h - 14), lbl, fill=text_color, font=fonts["ruler"])

    # Left ruler
    draw.rectangle([(0, oy), (ruler_left - 4, oy + sheet_scaled_h)], fill=ruler_bg)
    draw.line([(ruler_left - 4, oy), (ruler_left - 4, oy + sheet_scaled_h)], fill=ruler_line, width=1)
    for py in range(0, sheet_h + 1, 8):
        y = oy + py * scale
        is_major = (py % 32 == 0)
        is_mid = (py % 16 == 0) and not is_major
        tick_w = 16 if is_major else (10 if is_mid else 6)
        draw.line([(ruler_left - 4, y), (ruler_left - 4 - tick_w, y)], fill=ruler_line, width=1)
        if is_major or py == sheet_h or py in (8, 24, 40, 56, 88, 136, 186, 226):
            lbl = str(py)
            bbox = fonts["ruler"].getbbox(lbl)
            w_lbl = bbox[2] - bbox[0]
            draw.text((ruler_left - 4 - tick_w - w_lbl - 4, y - 6), lbl, fill=text_color, font=fonts["ruler"])

    # Origin box
    draw.rectangle([(0, 0), (ruler_left - 4, ruler_top - 4)], fill=(24, 27, 38, 255))
    draw.text((12, 18), "X / Y", fill=(130, 140, 165, 255), font=fonts["ruler"])

    # -------------------------------------------------------------
    # Render Cell Components & OAMs
    # -------------------------------------------------------------
    components = meta.get("components", [])

    # First pass: Cell bounds and OAM outlines
    for comp in components:
        cid = comp.get("cell_idx", 0)
        cx = comp["canvas_x"]
        cy = comp["canvas_y"]
        cw = comp["width"]
        ch = comp["height"]
        min_x = comp["min_x"]
        min_y = comp["min_y"]
        oams = comp.get("oams", [])
        c_color = CELL_COLORS.get(cid, (200, 200, 200))
        c_name = CELL_NAMES.get(cid, f"Cell {cid}")

        cell_x1 = ox + cx * scale
        cell_y1 = oy + cy * scale
        cell_x2 = cell_x1 + cw * scale
        cell_y2 = cell_y1 + ch * scale

        # 1. Cell bounding box
        draw.rectangle(
            [(cell_x1, cell_y1), (cell_x2, cell_y2)],
            outline=c_color,
            width=2,
        )

        # 2. Individual OAMs
        for i, oam in enumerate(oams):
            local_x = oam["x"] - min_x
            local_y = oam["y"] - min_y
            oam_sx = cx + local_x
            oam_sy = cy + local_y
            ow = oam["w"]
            oh = oam["h"]

            oam_x1 = ox + oam_sx * scale
            oam_y1 = oy + oam_sy * scale
            oam_x2 = oam_x1 + ow * scale
            oam_y2 = oam_y1 + oh * scale

            # Dashed OAM outline
            draw_dashed_rect(
                draw,
                (oam_x1, oam_y1, oam_x2, oam_y2),
                color=(*c_color, 160),
                dash=4,
                space=3,
                width=1,
            )

            # Small OAM tile tag if enough room
            if ow >= 16 and oh >= 8:
                tile_txt = f"T:{oam['tile']}"
                draw.rectangle(
                    [(oam_x1 + 2, oam_y1 + 2), (oam_x1 + 30, oam_y1 + 12)],
                    fill=(10, 12, 18, 200),
                )
                draw.text(
                    (oam_x1 + 3, oam_y1 + 2),
                    tile_txt,
                    fill=(*c_color, 255),
                    font=fonts["tiny"],
                )

        # 3. Cell Badge Label
        tile_indices = [o["tile"] for o in oams]
        min_tile = min(tile_indices) if tile_indices else 0
        max_tile = max(tile_indices) if tile_indices else 0
        badge_txt = f"[{cid}] {c_name} | {len(oams)} OAMs | Tiles: {min_tile}..{max_tile}"

        badge_bbox = fonts["small_bold"].getbbox(badge_txt)
        badge_w = badge_bbox[2] - badge_bbox[0] + 12
        badge_h = badge_bbox[3] - badge_bbox[1] + 6

        # Position badge above cell
        badge_x = cell_x1
        badge_y = cell_y1 - badge_h - 2
        if badge_y < oy:  # If too high, place inside
            badge_y = cell_y1 + 2

        draw.rectangle(
            [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
            fill=(15, 18, 26, 230),
            outline=c_color,
            width=1,
        )
        draw.text(
            (badge_x + 6, badge_y + 2),
            badge_txt,
            fill=(*c_color, 255),
            font=fonts["small_bold"],
        )

    # -------------------------------------------------------------
    # High-Visibility Warnings Pass: Seams & Gaps (Rendered on top)
    # -------------------------------------------------------------
    for comp in components:
        cid = comp.get("cell_idx", 0)
        cx = comp["canvas_x"]
        cy = comp["canvas_y"]
        cw = comp["width"]
        ch = comp["height"]
        cell_x1 = ox + cx * scale
        cell_y1 = oy + cy * scale
        cell_x2 = cell_x1 + cw * scale
        cell_y2 = cell_y1 + ch * scale

        # Warning 1: Cell 0 & Cell 1 SEAM at local x=48
        if cid in (0, 1):
            seam_sheet_x = cx + 48
            sx = ox + seam_sheet_x * scale
            sy1 = cell_y1
            # Word row is y=0..24
            sy2_word = cell_y1 + 24 * scale

            # Glow effect & bright red line
            draw.line([(sx - 1, sy1), (sx - 1, sy2_word)], fill=(255, 23, 68, 90), width=1)
            draw.line([(sx + 1, sy1), (sx + 1, sy2_word)], fill=(255, 23, 68, 90), width=1)
            draw.line([(sx, sy1), (sx, sy2_word)], fill=(255, 23, 68, 255), width=2)

            # Warning label badge
            seam_badge = "SEAM: x=48 (Max word width: 48px)"
            sbbox = fonts["tiny_bold"].getbbox(seam_badge)
            sw = sbbox[2] - sbbox[0] + 10
            sh = sbbox[3] - sbbox[1] + 6
            bx = sx - sw // 2
            # Clean placement right below word row
            by = sy2_word + 2
            draw.rectangle([(bx, by), (bx + sw, by + sh)], fill=(213, 0, 0, 245), outline=(255, 255, 255, 230), width=1)
            draw.text((bx + 5, by + 2), seam_badge, fill=(255, 255, 255, 255), font=fonts["tiny_bold"])

        # Warning 2: Cell 3 & Cell 4 4px HARDWARE GAP at local x=48..52
        if cid in (3, 4):
            gap_sheet_x1 = cx + 48
            gap_sheet_x2 = cx + 52
            gx1 = ox + gap_sheet_x1 * scale
            gx2 = ox + gap_sheet_x2 * scale
            gy1 = cell_y1
            # Gap specifically separates the two words at y=0..24
            gy2_word = cell_y1 + 24 * scale

            # Draw strictly clipped hazard pattern
            draw_hazard_hatch(guide_img, (gx1, gy1, gx2, gy2_word))

            # Warning badge
            gap_badge = "4px GAP / DO NOT DRAW"
            gbbox = fonts["tiny_bold"].getbbox(gap_badge)
            gw = gbbox[2] - gbbox[0] + 8
            gh = gbbox[3] - gbbox[1] + 6
            gbx = gx1 - (gw - (gx2 - gx1)) // 2
            # Place right below word row
            gby = gy2_word + 2
            draw.rectangle([(gbx, gby), (gbx + gw, gby + gh)], fill=(255, 214, 0, 245), outline=(0, 0, 0, 255), width=1)
            draw.text((gbx + 4, gby + 2), gap_badge, fill=(0, 0, 0, 255), font=fonts["tiny_bold"])

    # -------------------------------------------------------------
    # Sidebar / Legend Panel
    # -------------------------------------------------------------
    sb_x = ox + sheet_scaled_w + 24
    sb_y = oy
    sb_h = sheet_scaled_h

    # Sidebar container card
    draw.rectangle(
        [(sb_x, sb_y), (sb_x + sidebar_w, sb_y + sb_h)],
        fill=(26, 30, 42, 255),
        outline=(48, 54, 76, 255),
        width=2,
    )

    pad = 18
    cur_y = sb_y + pad
    inner_w = sidebar_w - pad * 2

    # Title
    draw.text((sb_x + pad, cur_y), "Chrono Trigger DS", fill=(255, 214, 0, 255), font=fonts["h2"])
    cur_y += 22
    draw.text((sb_x + pad, cur_y), "Title Logo Sprite Sheet Layout Guide", fill=(255, 255, 255, 255), font=fonts["title"])
    cur_y += 28
    draw.text((sb_x + pad, cur_y), "NCGR / NCER Multi-Cell Analysis & OAM Constraint Reference", fill=(140, 150, 180, 255), font=fonts["small"])
    cur_y += 24

    draw.line([(sb_x + pad, cur_y), (sb_x + pad + inner_w, cur_y)], fill=(48, 54, 76, 255), width=1)
    cur_y += 14

    # Critical Warning Box: Why Russian Text Broke
    warn_box_h = 194
    draw.rectangle(
        [(sb_x + pad, cur_y), (sb_x + pad + inner_w, cur_y + warn_box_h)],
        fill=(38, 20, 24, 255),
        outline=(255, 23, 68, 255),
        width=1,
    )
    w_pad = 12
    wy = cur_y + w_pad
    draw.text((sb_x + pad + w_pad, wy), "CRITICAL: WHY RUSSIAN TEXT BROKE", fill=(255, 82, 82, 255), font=fonts["h3"])
    wy += 20

    warn_bullets = [
        "1. SHARED TILES IN ROM: Cell 0 & 3 share tiles 0..36;",
        "   Cell 1 & 4 share tiles 40..88. They are NOT independent!",
        "2. SEAM AT x=48: In Cell 0 & 1, Left OAM (0..48) and Right",
        "   OAM (48..96) touch seamlessly. Left word width <= 48px.",
        "3. 4px GAP IN CELL 3 & 4: When an option is selected, the NDS",
        "   shifts the Right OAM +4px (gap at x=48..52).",
        "   If letters cross x=48, words get torn apart in Cell 3/4!",
        "4. NO OAM IN GAP: Pixels drawn inside x=48..52 in Cell 3/4",
        "   are NEVER packed into NCGR tiles and will vanish!",
    ]
    for bullet in warn_bullets:
        draw.text((sb_x + pad + w_pad, wy), bullet, fill=(230, 210, 215, 255), font=fonts["mono_small"])
        wy += 18

    cur_y += warn_box_h + 16

    # Cell Directory Table
    draw.text((sb_x + pad, cur_y), "CELL DIRECTORY & OAM SPECS", fill=(255, 255, 255, 255), font=fonts["h3"])
    cur_y += 20

    # Table header
    draw.rectangle([(sb_x + pad, cur_y), (sb_x + pad + inner_w, cur_y + 20)], fill=(34, 40, 56, 255))
    draw.text((sb_x + pad + 6, cur_y + 4), "ID", fill=(170, 180, 205, 255), font=fonts["tiny_bold"])
    draw.text((sb_x + pad + 32, cur_y + 4), "Name / Role", fill=(170, 180, 205, 255), font=fonts["tiny_bold"])
    draw.text((sb_x + pad + 240, cur_y + 4), "Canvas", fill=(170, 180, 205, 255), font=fonts["tiny_bold"])
    draw.text((sb_x + pad + 320, cur_y + 4), "Size", fill=(170, 180, 205, 255), font=fonts["tiny_bold"])
    draw.text((sb_x + pad + 380, cur_y + 4), "Tiles", fill=(170, 180, 205, 255), font=fonts["tiny_bold"])
    cur_y += 24

    for comp in sorted(components, key=lambda c: (c.get("cell_idx") < 0, c.get("cell_idx"))):
        cid = comp.get("cell_idx")
        c_color = CELL_COLORS.get(cid, (200, 200, 200))
        name = CELL_NAMES.get(cid, f"Cell {cid}")
        pos_txt = f"({comp['canvas_x']},{comp['canvas_y']})"
        size_txt = f"{comp['width']}x{comp['height']}"
        tiles = [o["tile"] for o in comp.get("oams", [])]
        tile_txt = f"{min(tiles)}..{max(tiles)}" if tiles else "N/A"

        # Color pip
        draw.rectangle([(sb_x + pad + 6, cur_y + 3), (sb_x + pad + 16, cur_y + 13)], fill=c_color)
        draw.text((sb_x + pad + 20, cur_y + 1), f"{cid:2d}", fill=(240, 240, 240, 255), font=fonts["mono_small"])
        short_name = name[:26]
        draw.text((sb_x + pad + 40, cur_y + 1), short_name, fill=(220, 225, 235, 255), font=fonts["small"])
        draw.text((sb_x + pad + 240, cur_y + 1), pos_txt, fill=(160, 170, 190, 255), font=fonts["mono_small"])
        draw.text((sb_x + pad + 320, cur_y + 1), size_txt, fill=(160, 170, 190, 255), font=fonts["mono_small"])
        draw.text((sb_x + pad + 380, cur_y + 1), tile_txt, fill=c_color, font=fonts["mono_small"])

        cur_y += 21

    cur_y += 12
    draw.line([(sb_x + pad, cur_y), (sb_x + pad + inner_w, cur_y)], fill=(48, 54, 76, 255), width=1)
    cur_y += 14

    # Visual Legend
    draw.text((sb_x + pad, cur_y), "VISUAL LEGEND", fill=(255, 255, 255, 255), font=fonts["h3"])
    cur_y += 20

    # Draw legend icons
    legend_items = [
        ("Solid Colored Box", "Cell bounding boundary on sprite sheet",
         lambda bx, by: draw.rectangle([(bx, by + 2), (bx + 26, by + 12)], outline=(0, 229, 255), width=2)),
        ("Dashed Box", "Individual OAM sprite piece boundary",
         lambda bx, by: draw_dashed_rect(draw, (bx, by + 2, bx + 26, by + 12), color=(255, 255, 255, 200), dash=3, space=2)),
        ("Red Line (x=48)", "Word split seam (no pixel may touch/cross)",
         lambda bx, by: draw.line([(bx + 13, by), (bx + 13, by + 16)], fill=(255, 23, 68, 255), width=3)),
        ("Yellow Hatch (4px)", "Hardware gap in Cell 3 & 4 (DO NOT DRAW)",
         lambda bx, by: draw_hazard_hatch(guide_img, (bx, by, bx + 26, by + 16))),
        ("Faint Grid", "8x8 Nintendo DS Hardware Tile boundaries",
         lambda bx, by: draw.rectangle([(bx, by + 2), (bx + 26, by + 12)], outline=(255, 255, 255, 60), width=1)),
    ]

    for title, desc, draw_icon in legend_items:
        draw_icon(sb_x + pad + 6, cur_y)
        draw.text((sb_x + pad + 42, cur_y), title, fill=(255, 255, 255, 255), font=fonts["small_bold"])
        draw.text((sb_x + pad + 180, cur_y), desc, fill=(150, 160, 180, 255), font=fonts["small"])
        cur_y += 24

    # Footer note
    cur_y = sb_y + sb_h - 32
    draw.text(
        (sb_x + pad, cur_y),
        "Scale: 4x (1px = 4x4) | Generated automatically by scripts/render_layout_guide.py",
        fill=(110, 120, 145, 255),
        font=fonts["tiny"],
    )

    # Save output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    guide_img.save(output_path, "PNG")
    print(f"Layout guide successfully saved to: {output_path}")
    print(f"Dimensions: {total_w}x{total_h} px (Sprite sheet 4x scale: {sheet_scaled_w}x{sheet_scaled_h} px)")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Visual Layout Guide for CT DS Title Sprite Sheet.")
    parser.add_argument("--image", type=Path, default=None, help="Input sprite sheet PNG")
    parser.add_argument("--json", type=Path, default=None, help="Input metadata JSON")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output layout guide PNG")
    parser.add_argument("--scale", type=int, default=4, help="Scale factor (default: 4)")
    args = parser.parse_args()

    # Image resolution fallback
    if args.image:
        img_path = args.image
    elif DEFAULT_IMAGE_TRANSLATED.is_file():
        img_path = DEFAULT_IMAGE_TRANSLATED
    else:
        img_path = DEFAULT_IMAGE_EXTRACTED

    # JSON resolution fallback
    if args.json:
        json_path = args.json
    elif DEFAULT_JSON_TRANSLATED.is_file():
        json_path = DEFAULT_JSON_TRANSLATED
    else:
        json_path = DEFAULT_JSON_EXTRACTED

    render_layout_guide(
        image_path=img_path,
        json_path=json_path,
        output_path=args.output,
        scale=args.scale,
    )


if __name__ == "__main__":
    main()
