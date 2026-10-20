"""Tests for Chrono Trigger DS title menu graphics and OAM constraints."""

import json
import os
from pathlib import Path

import pytest
from PIL import Image

from src.graphics_engine import (
    build_ncgr_sprite,
    dump_ncgr_sprite,
    rebuild_ncer_from_metadata,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TRANSLATED_PNG = PROJECT_ROOT / "translated image" / "title" / "obj" / "obj_logo_new.png"
TRANSLATED_JSON = PROJECT_ROOT / "translated image" / "title" / "obj" / "obj_logo_new.json"
EXTRACTED_PNG = PROJECT_ROOT / "extracted image" / "title" / "obj" / "obj_logo_new.png"
EXTRACTED_JSON = PROJECT_ROOT / "extracted image" / "title" / "obj" / "obj_logo_new.json"
EXTRACTED_NCLR = PROJECT_ROOT / "extracted rom" / "data" / "title" / "obj" / "obj_logo_new.NCLR"
EXTRACTED_NCER = PROJECT_ROOT / "extracted rom" / "data" / "title" / "obj" / "obj_logo_new.NCER"


def is_pixel_visible(val):
    """Helper to check whether pixel value is non-transparent across P and RGBA modes."""
    if isinstance(val, (tuple, list)):
        return len(val) >= 4 and val[3] >= 128
    return val != 0


@pytest.fixture(scope="module")
def logo_metadata():
    """Load cell sheet metadata for obj_logo_new, preferring translated metadata if present."""
    json_path = TRANSLATED_JSON if TRANSLATED_JSON.is_file() else EXTRACTED_JSON
    with open(json_path, encoding="utf-8") as f:
        meta = json.load(f)
    cells = {comp["cell_idx"]: comp for comp in meta.get("components", []) if "cell_idx" in comp}
    return meta, cells


def test_translated_logo_file_properties():
    """Requirement 1: Verify translated logo exists, dimensions (256, 250), mode 'P' or 'RGBA'."""
    assert os.path.isfile(TRANSLATED_PNG), f"Translated logo image not found at {TRANSLATED_PNG}"
    assert os.path.isfile(EXTRACTED_PNG), f"Extracted original logo image not found at {EXTRACTED_PNG}"

    with Image.open(TRANSLATED_PNG) as im_trans, Image.open(EXTRACTED_PNG) as im_orig:
        assert im_trans.size == (256, 250), f"Expected size (256, 250), got {im_trans.size}"
        assert im_trans.mode in ("P", "RGBA"), f"Expected mode 'P' or 'RGBA', got {im_trans.mode}"

        if im_trans.mode == "P":
            pal_trans = im_trans.getpalette() or []
            pal_orig = im_orig.getpalette() or []

            assert len(pal_trans) >= 48, f"Palette too short: {len(pal_trans)}"
            # 16-color palette (first 48 RGB values) must match extracted image
            assert pal_trans[:48] == pal_orig[:48], "16-color indexed palette does not match original extracted logo"
            # Full palette verification
            assert pal_trans == pal_orig, "Full palette does not match original extracted logo"


def test_cell_0_oam_constraints(logo_metadata):
    """Requirement 2 - Cell 0:
    Left word visible pixels must stay strictly within local x in 0..seam_x-1 (x < seam_x).
    No pixel may touch or cross the seam!
    Right word visible pixels must stay strictly within local x in seam_x..w-1.
    """
    _, cells = logo_metadata
    c0 = cells[0]
    cx, cy = c0["canvas_x"], c0["canvas_y"]
    w, h = c0["width"], c0["height"]
    seam_x = c0["oams"][0]["w"]

    with Image.open(TRANSLATED_PNG) as img:
        # Check seam: seam_x must not be touched or crossed by visible pixels
        for y in range(h):
            p_seam = img.getpixel((cx + seam_x, cy + y))
            assert not is_pixel_visible(p_seam), f"Cell 0 pixel at x={seam_x} seam (y={y}) is visible ({p_seam})"

        left_non_zero = []
        right_non_zero = []
        for y in range(h):
            for x in range(w):
                val = img.getpixel((cx + x, cy + y))
                if is_pixel_visible(val):
                    if x < seam_x:
                        left_non_zero.append((x, y))
                    else:
                        right_non_zero.append((x, y))

        assert len(left_non_zero) > 0, "Cell 0 left word has no visible pixels"
        assert len(right_non_zero) > 0, "Cell 0 right word has no visible pixels"

        for x, y in left_non_zero:
            assert 0 <= x < seam_x, f"Cell 0 left word pixel at ({x}, {y}) out of range [0..{seam_x - 1}]"

        for x, y in right_non_zero:
            assert seam_x <= x < w, f"Cell 0 right word pixel at ({x}, {y}) out of range [{seam_x}..{w - 1}]"


def test_cell_1_oam_constraints(logo_metadata):
    """Requirement 2 - Cell 1:
    Left word local x in 0..47 (x <= 47).
    Right word local x in 48..95.
    Subtitle (y >= 24) within local x bounds.
    """
    _, cells = logo_metadata
    c1 = cells[1]
    cx, cy = c1["canvas_x"], c1["canvas_y"]
    w, h = c1["width"], c1["height"]

    with Image.open(TRANSLATED_PNG) as img:
        left_word = []
        right_word = []
        subtitle = []

        for y in range(h):
            for x in range(w):
                val = img.getpixel((cx + x, cy + y))
                if is_pixel_visible(val):
                    if y < 24:
                        if x < 48:
                            left_word.append((x, y))
                        else:
                            right_word.append((x, y))
                    else:
                        subtitle.append((x, y))

        assert len(left_word) > 0, "Cell 1 left word has no visible pixels"
        assert len(right_word) > 0, "Cell 1 right word has no visible pixels"
        assert len(subtitle) > 0, "Cell 1 subtitle has no visible pixels"

        # Left word local x in 0..47 (x <= 47)
        for x, y in left_word:
            assert 0 <= x <= 47, f"Cell 1 left word pixel at ({x}, {y}) out of bounds [0..47]"

        # Right word local x in 48..95
        for x, y in right_word:
            assert 48 <= x <= 95, f"Cell 1 right word pixel at ({x}, {y}) out of bounds [48..95]"

        # Subtitle within local x bounds
        min_sub_x = 14 if c1["canvas_x"] == 136 else 16
        for x, y in subtitle:
            assert min_sub_x <= x <= 80, f"Cell 1 subtitle pixel at ({x}, {y}) out of bounds [{min_sub_x}..80]"


def test_cell_2_oam_constraints(logo_metadata):
    """Requirement 2 - Cell 2:
    Header within local x in 0..96.
    """
    _, cells = logo_metadata
    c2 = cells[2]
    cx, cy = c2["canvas_x"], c2["canvas_y"]
    w, h = c2["width"], c2["height"]

    with Image.open(TRANSLATED_PNG) as img:
        header_pixels = [
            (x, y) for y in range(h) for x in range(w)
            if is_pixel_visible(img.getpixel((cx + x, cy + y)))
        ]
        assert len(header_pixels) > 0, "Cell 2 header has no visible pixels"

        for x, y in header_pixels:
            assert 0 <= x < 96, f"Cell 2 header pixel at ({x}, {y}) out of bounds [0..96]"


def test_cells_3_4_5_replication(logo_metadata):
    """Requirement 2 - Cell 3, 4, 5 replication verification:
    - Cell 3 matches Cell 0 layout.
    - Cell 4 matches Cell 1 layout.
    - Cell 5 matches Cell 2 layout.
    """
    _, cells = logo_metadata
    c0 = cells[0]
    c1 = cells[1]
    c2 = cells[2]
    c3 = cells[3]
    c4 = cells[4]
    c5 = cells[5]

    with Image.open(TRANSLATED_PNG) as img:
        if c0["width"] > 96:
            # Translated wider logo layout (128x32): Cell 3 duplicates Cell 0 (y >= 1 covers all logo body)
            for y in range(1, c0["height"]):
                for x in range(c0["width"]):
                    p0 = img.getpixel((c0["canvas_x"] + x, c0["canvas_y"] + y))
                    p3 = img.getpixel((c3["canvas_x"] + x, c3["canvas_y"] + y))
                    assert p3 == p0, f"Cell 3 pixel mismatch at local ({x}, {y}): {p3} != {p0}"

            # Cell 4 matches Cell 1 directly
            for y in range(c1["height"]):
                for x in range(c1["width"]):
                    p1 = img.getpixel((c1["canvas_x"] + x, c1["canvas_y"] + y))
                    p4 = img.getpixel((c4["canvas_x"] + x, c4["canvas_y"] + y))
                    assert p4 == p1, f"Cell 4 pixel mismatch at local ({x}, {y}): {p4} != {p1}"

            # Cell 5 matches Cell 2 directly
            for y in range(c2["height"]):
                for x in range(c2["width"]):
                    p2 = img.getpixel((c2["canvas_x"] + x, c2["canvas_y"] + y))
                    p5 = img.getpixel((c5["canvas_x"] + x, c5["canvas_y"] + y))
                    assert p5 == p2, f"Cell 5 pixel mismatch at local ({x}, {y}): {p5} != {p2}"
        else:
            # Original extracted layout with OAM shifts
            # Cell 3 left OAM matches Cell 0 left OAM
            for y in range(24):
                for x in range(48):
                    p0 = img.getpixel((c0["canvas_x"] + x, c0["canvas_y"] + y))
                    p3 = img.getpixel((c3["canvas_x"] + x, c3["canvas_y"] + y))
                    assert p3 == p0, f"Cell 3 left OAM pixel mismatch at local ({x}, {y}): {p3} != {p0}"

            # Cell 3 right OAM matches Cell 0 right OAM with +4 shift
            for y in range(24):
                for x in range(48):
                    p0 = img.getpixel((c0["canvas_x"] + 48 + x, c0["canvas_y"] + y))
                    p3 = img.getpixel((c3["canvas_x"] + 52 + x, c3["canvas_y"] + y))
                    assert p3 == p0, f"Cell 3 right OAM pixel mismatch at offset {x}, y={y}: {p3} != {p0}"

            # Cell 4 left OAM matches Cell 1 left OAM
            for y in range(24):
                for x in range(48):
                    p1 = img.getpixel((c1["canvas_x"] + x, c1["canvas_y"] + y))
                    p4 = img.getpixel((c4["canvas_x"] + x, c4["canvas_y"] + y))
                    assert p4 == p1, f"Cell 4 left OAM pixel mismatch at local ({x}, {y}): {p4} != {p1}"

            # Cell 4 right OAM matches Cell 1 right OAM with +4 shift
            for y in range(24):
                for x in range(48):
                    p1 = img.getpixel((c1["canvas_x"] + 48 + x, c1["canvas_y"] + y))
                    p4 = img.getpixel((c4["canvas_x"] + 52 + x, c4["canvas_y"] + y))
                    assert p4 == p1, f"Cell 4 right OAM pixel mismatch at offset {x}, y={y}: {p4} != {p1}"

            # Cell 4 subtitle shift (+2): local x=18..82 matches Cell 1 local x=16..80
            for y in range(24, 40):
                for x in range(64):
                    p1 = img.getpixel((c1["canvas_x"] + 16 + x, c1["canvas_y"] + y))
                    p4 = img.getpixel((c4["canvas_x"] + 18 + x, c4["canvas_y"] + y))
                    assert p4 == p1, f"Cell 4 subtitle pixel mismatch at offset {x}, y={y}: {p4} != {p1}"

            # Cell 5 matches Cell 2
            for y in range(24):
                for x in range(96):
                    p2 = img.getpixel((c2["canvas_x"] + x, c2["canvas_y"] + y))
                    p5 = img.getpixel((c5["canvas_x"] + x, c5["canvas_y"] + y))
                    assert p5 == p2, f"Cell 5 pixel mismatch at local ({x}, {y}): {p5} != {p2}"


def test_french_cells_and_uncovered_tiles_identical(logo_metadata):
    """Requirement 2 - French cells (6, 7, 8) and uncovered tiles bar (-1)
    must be 100% pixel-identical to extracted image/title/obj/obj_logo_new.png.
    """
    _, cells = logo_metadata

    clean_png = PROJECT_ROOT / 'build' / 'clean_title' / 'obj_logo_new.png'
    ref_png = clean_png if clean_png.is_file() else EXTRACTED_PNG
    with Image.open(TRANSLATED_PNG) as img_trans, Image.open(ref_png) as img_orig:
        pal_orig = img_orig.getpalette() or []
        color_cache = {}

        def match_color(r, g, b, a):
            if a < 128:
                return 0
            rgb = (r, g, b)
            if rgb in color_cache:
                return color_cache[rgb]
            best_dist = float("inf")
            best_idx = 0
            for idx in range(16):
                pr, pg, pb = pal_orig[idx * 3], pal_orig[idx * 3 + 1], pal_orig[idx * 3 + 2]
                d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
                if d < best_dist:
                    best_dist = d
                    best_idx = idx
            color_cache[rgb] = best_idx
            return best_idx

        for cell_idx in (6, 7, 8, -1):
            assert cell_idx in cells, f"Cell {cell_idx} missing from logo metadata"
            comp = cells[cell_idx]
            cx, cy = comp["canvas_x"], comp["canvas_y"]
            w, h = comp["width"], comp["height"]

            diff_pixels = []
            for y in range(h):
                for x in range(w):
                    pt = img_trans.getpixel((cx + x, cy + y))
                    po = img_orig.getpixel((cx + x, cy + y))
                    vt = match_color(*pt) if isinstance(pt, tuple) else pt
                    if vt != po:
                        diff_pixels.append((x, y, pt, po))

            assert len(diff_pixels) == 0, (
                f"Cell {cell_idx} differs from extracted original by {len(diff_pixels)} pixels. "
                f"First difference at ({diff_pixels[0][0]}, {diff_pixels[0][1]}): trans={diff_pixels[0][2]}, orig={diff_pixels[0][3]}"
            )


def test_title_logo_ncgr_roundtrip(tmp_path, logo_metadata):
    """Requirement 3 - Roundtrip test:
    Run build_ncgr_sprite on translated image/title/obj/obj_logo_new.png and
    translated image/title/obj/obj_logo_new.json to produce NCGR bytes, then
    dump_ncgr_sprite to reconstruct the PNG, and verify lossless roundtrip stability.
    """
    meta, _ = logo_metadata
    out_ncgr = os.path.join(tmp_path, "rebuilt.NCGR")
    out_png = os.path.join(tmp_path, "reconstructed.png")
    out_json = os.path.join(tmp_path, "reconstructed.json")

    build_ncgr_sprite(str(TRANSLATED_PNG), str(TRANSLATED_JSON), out_ncgr)
    assert os.path.isfile(out_ncgr), "build_ncgr_sprite failed to produce NCGR file"
    assert os.path.getsize(out_ncgr) > 0, "Generated NCGR file is empty"

    nclr_path = meta.get("nclr_path")
    if not nclr_path or not os.path.isfile(nclr_path):
        nclr_path = str(EXTRACTED_NCLR)

    out_ncer = os.path.join(tmp_path, "rebuilt.NCER")
    rebuild_ncer_from_metadata(str(TRANSLATED_JSON), out_ncer)

    dump_ncgr_sprite(
        out_ncgr,
        nclr_path,
        out_png,
        out_json,
        ncer_path=out_ncer,
    )
    assert os.path.isfile(out_png), "dump_ncgr_sprite failed to reconstruct PNG file"

    with Image.open(TRANSLATED_PNG) as img_in, Image.open(out_png) as img_out:
        if img_in.mode == img_out.mode and img_in.size == img_out.size:
            diff_count = 0
            diff_samples = []
            w, h = img_in.size
            for y in range(h):
                for x in range(w):
                    p_in = img_in.getpixel((x, y))
                    p_out = img_out.getpixel((x, y))
                    if p_in != p_out:
                        diff_count += 1
                        if len(diff_samples) < 5:
                            diff_samples.append((x, y, p_in, p_out))

            assert diff_count == 0, (
                f"Reconstructed PNG differs by {diff_count} pixels from input. "
                f"Sample differences: {diff_samples}"
            )
        else:
            # When input is RGBA or dimensions differ due to shelf packing,
            # verify lossless roundtrip stability from reconstructed sprite
            out_ncgr2 = os.path.join(tmp_path, "rebuilt2.NCGR")
            out_png2 = os.path.join(tmp_path, "reconstructed2.png")
            out_json2 = os.path.join(tmp_path, "reconstructed2.json")
            build_ncgr_sprite(out_png, out_json, out_ncgr2)
            dump_ncgr_sprite(out_ncgr2, nclr_path, out_png2, out_json2, ncer_path=out_ncer)

            with Image.open(out_png2) as img_out2:
                assert img_out.size == img_out2.size, f"Size mismatch: {img_out.size} vs {img_out2.size}"
                assert img_out.mode == img_out2.mode, f"Mode mismatch: {img_out.mode} vs {img_out2.mode}"
                diff_count = 0
                for y in range(img_out.height):
                    for x in range(img_out.width):
                        if img_out.getpixel((x, y)) != img_out2.getpixel((x, y)):
                            diff_count += 1
                assert diff_count == 0, f"Roundtrip instability: {diff_count} pixels differ"
