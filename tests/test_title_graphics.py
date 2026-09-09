"""Tests for Chrono Trigger DS title menu graphics and OAM constraints."""

import json
import os
from pathlib import Path
from PIL import Image
import pytest

from src.graphics_engine import build_ncgr_sprite, dump_ncgr_sprite

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TRANSLATED_PNG = PROJECT_ROOT / "translated image" / "title" / "obj" / "obj_logo_new.png"
TRANSLATED_JSON = PROJECT_ROOT / "translated image" / "title" / "obj" / "obj_logo_new.json"
EXTRACTED_PNG = PROJECT_ROOT / "extracted image" / "title" / "obj" / "obj_logo_new.png"
EXTRACTED_JSON = PROJECT_ROOT / "extracted image" / "title" / "obj" / "obj_logo_new.json"
EXTRACTED_NCLR = PROJECT_ROOT / "extracted rom" / "data" / "title" / "obj" / "obj_logo_new.NCLR"
EXTRACTED_NCER = PROJECT_ROOT / "extracted rom" / "data" / "title" / "obj" / "obj_logo_new.NCER"


@pytest.fixture(scope="module")
def logo_metadata():
    """Load cell sheet metadata for obj_logo_new."""
    json_path = EXTRACTED_JSON if EXTRACTED_JSON.is_file() else TRANSLATED_JSON
    with open(json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    cells = {comp["cell_idx"]: comp for comp in meta.get("components", []) if "cell_idx" in comp}
    return meta, cells


def test_translated_logo_file_properties():
    """Requirement 1: Verify translated logo exists, dimensions (256, 250), mode 'P', and palette matches extracted."""
    assert os.path.isfile(TRANSLATED_PNG), f"Translated logo image not found at {TRANSLATED_PNG}"
    assert os.path.isfile(EXTRACTED_PNG), f"Extracted original logo image not found at {EXTRACTED_PNG}"

    with Image.open(TRANSLATED_PNG) as im_trans, Image.open(EXTRACTED_PNG) as im_orig:
        assert im_trans.size == (256, 250), f"Expected size (256, 250), got {im_trans.size}"
        assert im_trans.mode == "P", f"Expected mode 'P', got {im_trans.mode}"

        pal_trans = im_trans.getpalette() or []
        pal_orig = im_orig.getpalette() or []

        assert len(pal_trans) >= 48, f"Palette too short: {len(pal_trans)}"
        # 16-color palette (first 48 RGB values) must match extracted image
        assert pal_trans[:48] == pal_orig[:48], "16-color indexed palette does not match original extracted logo"
        # Full palette verification
        assert pal_trans == pal_orig, "Full palette does not match original extracted logo"


def test_cell_0_oam_constraints(logo_metadata):
    """Requirement 2 - Cell 0 (canvas_x=8, canvas_y=8, w=96, h=24):
    Left word (OAM x=0..48) non-zero pixels must stay strictly within local x in 0..47 (x <= 47).
    No pixel may touch or cross the x=48 seam!
    Right word (OAM x=48..96) non-zero pixels must stay strictly within local x in 48..95.
    """
    _, cells = logo_metadata
    c0 = cells[0]
    cx, cy = c0["canvas_x"], c0["canvas_y"]
    w, h = c0["width"], c0["height"]
    assert (cx, cy, w, h) == (8, 8, 96, 24)

    with Image.open(TRANSLATED_PNG) as img:
        # Check seam: x=48 seam must not be touched or crossed by the left word
        # (and left boundary pixel at x=47 must also not cross into x=48)
        for y in range(h):
            p48 = img.getpixel((cx + 48, cy + y))
            assert p48 == 0, f"Cell 0 pixel at x=48 seam (y={y}) is non-zero ({p48})"

        # Non-zero pixels check
        left_non_zero = []
        right_non_zero = []
        for y in range(h):
            for x in range(w):
                val = img.getpixel((cx + x, cy + y))
                if val != 0:
                    if x < 48:
                        left_non_zero.append((x, y))
                    else:
                        right_non_zero.append((x, y))

        assert len(left_non_zero) > 0, "Cell 0 left word has no non-zero pixels"
        assert len(right_non_zero) > 0, "Cell 0 right word has no non-zero pixels"

        # Left word non-zero pixels must stay strictly within local x in 0..47 (x <= 47)
        for x, y in left_non_zero:
            assert 0 <= x <= 47, f"Cell 0 left word pixel at ({x}, {y}) out of range [0..47]"

        # Right word non-zero pixels must stay strictly within local x in 48..95
        for x, y in right_non_zero:
            assert 48 <= x <= 95, f"Cell 0 right word pixel at ({x}, {y}) out of range [48..95]"


def test_cell_1_oam_constraints(logo_metadata):
    """Requirement 2 - Cell 1 (canvas_x=112, canvas_y=8, w=96, h=40):
    Left word local x in 0..47 (x <= 47).
    Right word local x in 48..95.
    Subtitle (y=24..40) within local x in 16..80.
    """
    _, cells = logo_metadata
    c1 = cells[1]
    cx, cy = c1["canvas_x"], c1["canvas_y"]
    w, h = c1["width"], c1["height"]
    assert (cx, cy, w, h) == (112, 8, 96, 40)

    with Image.open(TRANSLATED_PNG) as img:
        left_word = []
        right_word = []
        subtitle = []

        for y in range(h):
            for x in range(w):
                val = img.getpixel((cx + x, cy + y))
                if val != 0:
                    if y < 24:
                        if x < 48:
                            left_word.append((x, y))
                        else:
                            right_word.append((x, y))
                    else:
                        subtitle.append((x, y))

        assert len(left_word) > 0, "Cell 1 left word has no non-zero pixels"
        assert len(right_word) > 0, "Cell 1 right word has no non-zero pixels"
        assert len(subtitle) > 0, "Cell 1 subtitle has no non-zero pixels"

        # Left word local x in 0..47 (x <= 47)
        for x, y in left_word:
            assert 0 <= x <= 47, f"Cell 1 left word pixel at ({x}, {y}) out of bounds [0..47]"

        # Right word local x in 48..95
        for x, y in right_word:
            assert 48 <= x <= 95, f"Cell 1 right word pixel at ({x}, {y}) out of bounds [48..95]"

        # Subtitle (y=24..40) within local x in 16..80
        for x, y in subtitle:
            assert 16 <= x <= 80, f"Cell 1 subtitle pixel at ({x}, {y}) out of bounds [16..80]"


def test_cell_2_oam_constraints(logo_metadata):
    """Requirement 2 - Cell 2 (canvas_x=8, canvas_y=56, w=96, h=24):
    Header within local x in 0..96.
    """
    _, cells = logo_metadata
    c2 = cells[2]
    cx, cy = c2["canvas_x"], c2["canvas_y"]
    w, h = c2["width"], c2["height"]
    assert (cx, cy, w, h) == (8, 56, 96, 24)

    with Image.open(TRANSLATED_PNG) as img:
        header_pixels = [
            (x, y) for y in range(h) for x in range(w)
            if img.getpixel((cx + x, cy + y)) != 0
        ]
        assert len(header_pixels) > 0, "Cell 2 header has no non-zero pixels"

        for x, y in header_pixels:
            assert 0 <= x < 96, f"Cell 2 header pixel at ({x}, {y}) out of bounds [0..96]"


def test_cells_3_4_5_replication(logo_metadata):
    """Requirement 2 - Cell 3, 4, 5 replication verification:
    - Cell 3 left OAM matches Cell 0 left OAM.
    - Cell 3 right OAM (local x=52..100) matches Cell 0 right OAM (local x=48..96).
    - Cell 4 matches Cell 1 with the same right OAM shift (+4) and subtitle shift (+2).
    - Cell 5 matches Cell 2.
    """
    _, cells = logo_metadata
    c0 = cells[0]
    c1 = cells[1]
    c2 = cells[2]
    c3 = cells[3]
    c4 = cells[4]
    c5 = cells[5]

    with Image.open(TRANSLATED_PNG) as img:
        # Cell 3 vs Cell 0
        # Cell 3 left OAM (local x=0..48, y=0..24) matches Cell 0 left OAM (local x=0..48, y=0..24)
        for y in range(24):
            for x in range(48):
                p0 = img.getpixel((c0["canvas_x"] + x, c0["canvas_y"] + y))
                p3 = img.getpixel((c3["canvas_x"] + x, c3["canvas_y"] + y))
                assert p3 == p0, f"Cell 3 left OAM pixel mismatch at local ({x}, {y}): {p3} != {p0}"

        # Cell 3 right OAM (local x=52..100) matches Cell 0 right OAM (local x=48..96)
        for y in range(24):
            for x in range(48):
                p0 = img.getpixel((c0["canvas_x"] + 48 + x, c0["canvas_y"] + y))
                p3 = img.getpixel((c3["canvas_x"] + 52 + x, c3["canvas_y"] + y))
                assert p3 == p0, f"Cell 3 right OAM pixel mismatch at offset {x}, y={y}: {p3} != {p0}"

        # Cell 4 vs Cell 1
        # Cell 4 left OAM (local x=0..48, y=0..24) matches Cell 1 left OAM (local x=0..48, y=0..24)
        for y in range(24):
            for x in range(48):
                p1 = img.getpixel((c1["canvas_x"] + x, c1["canvas_y"] + y))
                p4 = img.getpixel((c4["canvas_x"] + x, c4["canvas_y"] + y))
                assert p4 == p1, f"Cell 4 left OAM pixel mismatch at local ({x}, {y}): {p4} != {p1}"

        # Cell 4 right OAM (local x=52..100) matches Cell 1 right OAM (local x=48..96)
        for y in range(24):
            for x in range(48):
                p1 = img.getpixel((c1["canvas_x"] + 48 + x, c1["canvas_y"] + y))
                p4 = img.getpixel((c4["canvas_x"] + 52 + x, c4["canvas_y"] + y))
                assert p4 == p1, f"Cell 4 right OAM pixel mismatch at offset {x}, y={y}: {p4} != {p1}"

        # Cell 4 subtitle shift (+2): local x=18..82 matches Cell 1 local x=16..80 (y=24..40, width=64)
        for y in range(24, 40):
            for x in range(64):
                p1 = img.getpixel((c1["canvas_x"] + 16 + x, c1["canvas_y"] + y))
                p4 = img.getpixel((c4["canvas_x"] + 18 + x, c4["canvas_y"] + y))
                assert p4 == p1, f"Cell 4 subtitle pixel mismatch at offset {x}, y={y}: {p4} != {p1}"

        # Cell 5 matches Cell 2 (local x=0..96, y=0..24)
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

    with Image.open(TRANSLATED_PNG) as img_trans, Image.open(EXTRACTED_PNG) as img_orig:
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
                    if pt != po:
                        diff_pixels.append((x, y, pt, po))

            assert len(diff_pixels) == 0, (
                f"Cell {cell_idx} differs from extracted original by {len(diff_pixels)} pixels. "
                f"First difference at ({diff_pixels[0][0]}, {diff_pixels[0][1]}): trans={diff_pixels[0][2]}, orig={diff_pixels[0][3]}"
            )


def test_title_logo_ncgr_roundtrip(tmp_path, logo_metadata):
    """Requirement 3 - Roundtrip test:
    Run build_ncgr_sprite on translated image/title/obj/obj_logo_new.png and
    translated image/title/obj/obj_logo_new.json to produce NCGR bytes, then
    dump_ncgr_sprite to reconstruct the PNG, and assert that 0 pixels differ between input and output.
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

    ncer_path = meta.get("ncer_path")
    if not ncer_path or not os.path.isfile(ncer_path):
        ncer_path = str(EXTRACTED_NCER)

    dump_ncgr_sprite(
        out_ncgr,
        nclr_path,
        out_png,
        out_json,
        ncer_path=ncer_path,
    )
    assert os.path.isfile(out_png), "dump_ncgr_sprite failed to reconstruct PNG file"

    with Image.open(TRANSLATED_PNG) as img_in, Image.open(out_png) as img_out:
        assert img_in.size == img_out.size, f"Size mismatch: {img_in.size} vs {img_out.size}"
        assert img_in.mode == img_out.mode, f"Mode mismatch: {img_in.mode} vs {img_out.mode}"

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
