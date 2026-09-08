"""Tests for Chrono Trigger DS graphics engine."""

import os
import struct
import pytest
from src.graphics_engine import (
    decompress_stream,
    compress_stream,
    parse_ncl_header,
    parse_ncg_header,
    parse_nsc_header,
    build_ncl_header,
    build_ncg_header,
    build_nsc_header,
)


def test_decompress_and_compress_stream():
    payload = b"NCG\x00\x10\x00\x00\x00" + b"\x12\x34\x56\x78" * 8
    # Single layer compression
    c1 = compress_stream(payload, layers=1)
    d1, l1 = decompress_stream(c1)
    assert l1 == 1
    assert d1 == payload

    # Double layer compression
    c2 = compress_stream(payload, layers=2)
    d2, l2 = decompress_stream(c2)
    assert l2 == 2
    assert d2 == payload


def test_ncl_header_roundtrip():
    header = build_ncl_header(color_count=256)
    info = parse_ncl_header(header)
    assert info["magic"] == b"NCL\x00"
    assert info["color_count"] == 256


def test_ncg_header_roundtrip():
    header = build_ncg_header(tile_count=89)
    info = parse_ncg_header(header)
    assert info["magic"] == b"NCG\x00"
    assert info["tile_count"] == 89


def test_nsc_header_roundtrip():
    header = build_nsc_header(width_tiles=32, height_tiles=24, flags=0x00030000)
    info = parse_nsc_header(header)
    assert info["magic"] == b"NSC\x00"
    assert info["width_tiles"] == 32
    assert info["height_tiles"] == 24
    assert info["flags"] == 0x00030000


def test_dump_kenri_screen(tmp_path):
    from PIL import Image
    from src.graphics_engine import dump_screen

    ncg = "extracted rom/data/title/bg/kenri_ncg.bin"
    ncl = "extracted rom/data/title/bg/kenri_ncl.bin"
    nsc = "extracted rom/data/title/bg/kenri_nsc.bin"
    out_png = os.path.join(tmp_path, "kenri.png")
    out_json = os.path.join(tmp_path, "kenri.json")

    info = dump_screen(ncg, ncl, nsc, out_png, out_json)
    assert os.path.isfile(out_png)
    assert os.path.isfile(out_json)

    with Image.open(out_png) as img:
        assert img.size == (256, 192)
    assert info["width_px"] == 256
    assert info["height_px"] == 192


def test_dump_all_screens_category(tmp_path):
    from src.graphics_engine import dump_all_screens

    out_dir = os.path.join(tmp_path, "extracted_img")
    count = dump_all_screens(
        rom_data_dir="extracted rom/data",
        output_image_dir=out_dir,
        category="special",
    )
    assert count > 0
    assert os.path.isdir(os.path.join(out_dir, "special"))


def test_rebuild_screen_roundtrip(tmp_path):
    from PIL import Image
    from src.graphics_engine import dump_screen, build_screen

    ncg = "extracted rom/data/title/bg/kenri_ncg.bin"
    ncl = "extracted rom/data/title/bg/kenri_ncl.bin"
    nsc = "extracted rom/data/title/bg/kenri_nsc.bin"
    dump_png = os.path.join(tmp_path, "kenri.png")
    dump_json = os.path.join(tmp_path, "kenri.json")
    dump_screen(ncg, ncl, nsc, dump_png, dump_json)

    reb_ncg = os.path.join(tmp_path, "rebuilt_ncg.bin")
    reb_ncl = os.path.join(tmp_path, "rebuilt_ncl.bin")
    reb_nsc = os.path.join(tmp_path, "rebuilt_nsc.bin")
    build_screen(dump_png, dump_json, reb_ncg, reb_ncl, reb_nsc)

    assert os.path.isfile(reb_ncg)
    assert os.path.isfile(reb_ncl)
    assert os.path.isfile(reb_nsc)

    # Re-dump from rebuilt files to verify pixel-perfect roundtrip
    reb_png = os.path.join(tmp_path, "rebuilt.png")
    reb_json = os.path.join(tmp_path, "rebuilt.json")
    dump_screen(reb_ncg, reb_ncl, reb_nsc, reb_png, reb_json)

    with Image.open(dump_png) as orig_img, Image.open(reb_png) as test_img:
        assert orig_img.convert("RGB").tobytes() == test_img.convert("RGB").tobytes()


def test_rebuild_8bpp_screen_roundtrip(tmp_path):
    from PIL import Image
    from src.graphics_engine import dump_screen, build_screen

    ncg = "extracted rom/data/title/bg/square_enix_tm_ncg.bin"
    ncl = "extracted rom/data/title/bg/square_enix_tm_ncl.bin"
    nsc = "extracted rom/data/title/bg/square_enix_tm_nsc.bin"
    dump_png = os.path.join(tmp_path, "sq.png")
    dump_json = os.path.join(tmp_path, "sq.json")
    dump_screen(ncg, ncl, nsc, dump_png, dump_json)

    reb_ncg = os.path.join(tmp_path, "rebuilt_sq_ncg.bin")
    reb_ncl = os.path.join(tmp_path, "rebuilt_sq_ncl.bin")
    reb_nsc = os.path.join(tmp_path, "rebuilt_sq_nsc.bin")
    build_screen(dump_png, dump_json, reb_ncg, reb_ncl, reb_nsc)

    reb_png = os.path.join(tmp_path, "rebuilt_sq.png")
    reb_json = os.path.join(tmp_path, "rebuilt_sq.json")
    dump_screen(reb_ncg, reb_ncl, reb_nsc, reb_png, reb_json)

    with Image.open(dump_png) as orig_img, Image.open(reb_png) as test_img:
        assert orig_img.convert("RGB").tobytes() == test_img.convert("RGB").tobytes()


def test_cli_dump_single_screen(tmp_path):
    from src.cli import main

    out_dir = os.path.join(tmp_path, "extracted_img")
    code = main([
        "dump-graphics",
        "--screen", "extracted rom/data/title/bg/kenri",
        "--out", out_dir,
    ])
    assert code == 0
    assert os.path.isfile(os.path.join(out_dir, "title/bg/kenri.png"))
    assert os.path.isfile(os.path.join(out_dir, "title/bg/kenri.json"))


def test_cli_build_single_screen(tmp_path):
    from src.cli import main

    out_dir = os.path.join(tmp_path, "extracted_img")
    target_rom_dir = os.path.join(tmp_path, "rom_data")

    # 1. Dump screen
    dump_code = main([
        "dump-graphics",
        "--screen", "extracted rom/data/title/bg/kenri",
        "--out", out_dir,
    ])
    assert dump_code == 0

    # 2. Build screen into target_rom_dir
    build_code = main([
        "build-graphics",
        "--screen", os.path.join(out_dir, "title/bg/kenri.png"),
        "--meta-dir", out_dir,
        "--rom-data", target_rom_dir,
    ])
    assert build_code == 0
    assert os.path.isfile(os.path.join(target_rom_dir, "title/bg/kenri_ncg.bin"))
    assert os.path.isfile(os.path.join(target_rom_dir, "title/bg/kenri_ncl.bin"))

def test_rebuild_affine_minimap_roundtrip(tmp_path):
    from PIL import Image
    from src.graphics_engine import dump_screen, build_screen

    ncg = "extracted rom/data/minimap/bg/gendai_fiona_ncg.bin"
    ncl = "extracted rom/data/minimap/bg/gendai_fiona_ncl.bin"
    nsc = "extracted rom/data/minimap/bg/gendai_fiona_nsc.bin"
    dump_png = os.path.join(tmp_path, "fiona.png")
    dump_json = os.path.join(tmp_path, "fiona.json")
    info = dump_screen(ncg, ncl, nsc, dump_png, dump_json)

    assert info["is_affine"] is True
    assert info["width_px"] == 256
    assert info["height_px"] == 256
    assert len(info["extra_data"]) == 1024 * 2  # 1024 bytes in hex

    reb_ncg = os.path.join(tmp_path, "rebuilt_fiona_ncg.bin")
    reb_ncl = os.path.join(tmp_path, "rebuilt_fiona_ncl.bin")
    reb_nsc = os.path.join(tmp_path, "rebuilt_fiona_nsc.bin")
    build_screen(dump_png, dump_json, reb_ncg, reb_ncl, reb_nsc)

    reb_png = os.path.join(tmp_path, "rebuilt_fiona.png")
    reb_json = os.path.join(tmp_path, "rebuilt_fiona.json")
    reb_info = dump_screen(reb_ncg, reb_ncl, reb_nsc, reb_png, reb_json)

    assert reb_info["extra_data"] == info["extra_data"]
    with Image.open(dump_png) as orig_img, Image.open(reb_png) as test_img:
        assert orig_img.convert("RGB").tobytes() == test_img.convert("RGB").tobytes()


def test_ncgr_sprite_roundtrip(tmp_path):
    from PIL import Image
    from src.graphics_engine import dump_ncgr_sprite, build_ncgr_sprite, decompress_stream

    ncgr = "extracted rom/data/menu/obj/icon.NCGR"
    nclr = "extracted rom/data/menu/obj/icon.NCLR"
    ncer = "extracted rom/data/menu/obj/icon.NCER"
    out_png = os.path.join(tmp_path, "icon.png")
    out_json = os.path.join(tmp_path, "icon.json")

    meta = dump_ncgr_sprite(ncgr, nclr, out_png, out_json)
    assert meta["format"] == "NCGR"
    assert meta["is_cell_sheet"] is True
    assert meta["num_tiles"] == 364
    assert os.path.isfile(out_png)

    reb_ncgr = os.path.join(tmp_path, "rebuilt_icon.NCGR")
    build_ncgr_sprite(out_png, out_json, reb_ncgr)
    assert os.path.isfile(reb_ncgr)

    # 100% bit-exact binary roundtrip verification
    orig_decomp, _ = decompress_stream(open(ncgr, "rb").read())
    reb_decomp, _ = decompress_stream(open(reb_ncgr, "rb").read())
    assert orig_decomp == reb_decomp

    # Re-dump to verify pixel equivalence
    redump_png = os.path.join(tmp_path, "redump_icon.png")
    redump_json = os.path.join(tmp_path, "redump_icon.json")
    dump_ncgr_sprite(reb_ncgr, nclr, redump_png, redump_json, ncer_path=ncer)

    with Image.open(out_png) as img1, Image.open(redump_png) as img2:
        assert img1.tobytes() == img2.tobytes()


def test_cli_sprite_roundtrip(tmp_path):
    from src.cli import main

    out_dir = os.path.join(tmp_path, "extracted_img")
    target_rom_dir = os.path.join(tmp_path, "rom_data")

    # 1. Dump sprite
    dump_code = main([
        "dump-graphics",
        "--screen", "extracted rom/data/menu/obj/icon.NCGR",
        "--out", out_dir,
    ])
    assert dump_code == 0
    assert os.path.isfile(os.path.join(out_dir, "menu/obj/icon.png"))
    assert os.path.isfile(os.path.join(out_dir, "menu/obj/icon.json"))

    # 2. Build sprite
    build_code = main([
        "build-graphics",
        "--screen", os.path.join(out_dir, "menu/obj/icon.png"),
        "--meta-dir", out_dir,
        "--rom-data", target_rom_dir,
    ])
    assert build_code == 0
    assert os.path.isfile(os.path.join(target_rom_dir, "menu/obj/icon.NCGR"))


def test_nclr_palette_parsing_accurate_colors():
    from src.graphics_engine import parse_nclr_palette
    with open("extracted rom/data/menu/obj/icon.NCLR", "rb") as f:
        data = f.read()
    colors = parse_nclr_palette(data)

    # Color 0 must be 0x61ad -> RGB(106, 106, 197), not 0x0020
    assert colors[0] == 106
    assert colors[1] == 106
    assert colors[2] == 197

    # Color 7 must be 0x7fff -> RGB(255, 255, 255)
    assert colors[7 * 3] == 255
    assert colors[7 * 3 + 1] == 255
    assert colors[7 * 3 + 2] == 255

    # Color 12 must be 0x2108 -> RGB(65, 65, 65)
    assert colors[12 * 3] == 65
    assert colors[12 * 3 + 1] == 65
    assert colors[12 * 3 + 2] == 65


def test_find_palette_for_sprite():
    from src.graphics_engine import find_palette_for_sprite

    # Direct match
    pal_icon = find_palette_for_sprite("extracted rom/data/menu/obj/icon.NCGR")
    assert pal_icon is not None
    assert pal_icon.replace("\\", "/").endswith("menu/obj/icon.NCLR")

    # Language variant fallback
    pal_fra = find_palette_for_sprite("extracted rom/data/menu/obj/icon_fra.NCGR")
    assert pal_fra is not None
    assert pal_fra.replace("\\", "/").endswith("menu/obj/icon.NCLR")

    # Menu window element
    pal_win = find_palette_for_sprite("extracted rom/data/menu/obj/obj_win_item.NCGR")
    assert pal_win is not None
    assert pal_win.replace("\\", "/").endswith("menu/obj/win_ncl.bin")


def test_ncgr_sprite_transparency_and_rgba_rebuild(tmp_path):
    from PIL import Image
    from src.graphics_engine import dump_ncgr_sprite, build_ncgr_sprite, decompress_stream

    ncgr_path = "extracted rom/data/menu/obj/icon.NCGR"
    nclr_path = "extracted rom/data/menu/obj/icon.NCLR"
    out_png = os.path.join(tmp_path, "icon.png")
    out_json = os.path.join(tmp_path, "icon.json")

    dump_ncgr_sprite(ncgr_path, nclr_path, out_png, out_json)

    # Verify PNG has transparency=0
    with Image.open(out_png) as img:
        assert img.mode == "P"
        assert img.info.get("transparency") == 0

    # Test roundtrip directly with indexed image
    reb_ncgr_p = os.path.join(tmp_path, "reb_p.NCGR")
    build_ncgr_sprite(out_png, out_json, reb_ncgr_p)

    orig_decomp, _ = decompress_stream(open(ncgr_path, "rb").read())
    reb_decomp, _ = decompress_stream(open(reb_ncgr_p, "rb").read())
    assert orig_decomp == reb_decomp

    # Test roundtrip when user saved PNG as RGBA in an external image editor
    rgba_png = os.path.join(tmp_path, "icon_rgba.png")
    with Image.open(out_png) as img:
        img.convert("RGBA").save(rgba_png)

    reb_ncgr_rgba = os.path.join(tmp_path, "reb_rgba.NCGR")
    build_ncgr_sprite(rgba_png, out_json, reb_ncgr_rgba)
    reb_rgba_decomp, _ = decompress_stream(open(reb_ncgr_rgba, "rb").read())
    assert len(reb_rgba_decomp) == len(orig_decomp)


def test_find_cell_bank_for_sprite():
    from src.graphics_engine import find_cell_bank_for_sprite

    # Direct match
    cb_icon = find_cell_bank_for_sprite("extracted rom/data/menu/obj/icon.NCGR")
    assert cb_icon is not None
    assert cb_icon.replace("\\", "/").endswith("menu/obj/icon.NCER")

    # Language variant fallback
    cb_fra = find_cell_bank_for_sprite("extracted rom/data/menu/obj/icon_fra.NCGR")
    assert cb_fra is not None
    assert cb_fra.replace("\\", "/").endswith("menu/obj/icon_fra.NCER") or cb_fra.replace("\\", "/").endswith("menu/obj/icon.NCER")


def test_ncer_cell_sheet_icon_fra_roundtrip(tmp_path):
    from src.graphics_engine import dump_ncgr_sprite, build_ncgr_sprite, decompress_stream

    ncgr_path = "extracted rom/data/menu/obj/icon_fra.NCGR"
    nclr_path = "extracted rom/data/menu/obj/icon.NCLR"
    out_png = os.path.join(tmp_path, "icon_fra.png")
    out_json = os.path.join(tmp_path, "icon_fra.json")

    meta = dump_ncgr_sprite(ncgr_path, nclr_path, out_png, out_json)
    assert meta["is_cell_sheet"] is True
    assert meta["num_tiles"] == 356

    reb_ncgr = os.path.join(tmp_path, "rebuilt_icon_fra.NCGR")
    build_ncgr_sprite(out_png, out_json, reb_ncgr)

    orig_decomp, _ = decompress_stream(open(ncgr_path, "rb").read())
    reb_decomp, _ = decompress_stream(open(reb_ncgr, "rb").read())
    assert orig_decomp == reb_decomp


def test_dump_worldbreak_minimap_no_index_error(tmp_path):
    from src.graphics_engine import dump_screen, find_tiles_for_screen, find_palette_for_screen

    nsc = "extracted rom/data/WorldMap/worldBreakMinimap_nsc.bin"
    ncg = find_tiles_for_screen(nsc)
    ncl = find_palette_for_screen(nsc)
    assert ncg is not None
    assert ncl is not None

    out_png = os.path.join(tmp_path, "wm.png")
    out_json = os.path.join(tmp_path, "wm.json")
    info = dump_screen(ncg, ncl, nsc, out_png, out_json)
    assert os.path.isfile(out_png)
    assert info["width_px"] == 256
    assert info["height_px"] == 256


def test_dump_all_screens_dir_sprites(tmp_path):
    from src.graphics_engine import dump_all_screens

    out_dir = os.path.join(tmp_path, "extracted_img")
    res = dump_all_screens(
        rom_data_dir="extracted rom/data",
        output_image_dir=out_dir,
        directory="menu/obj",
    )
    assert res > 0
    assert res.sprites > 200
    assert os.path.isfile(os.path.join(out_dir, "menu/obj/icon.png"))
    assert os.path.isfile(os.path.join(out_dir, "menu/obj/icon.json"))


def test_dump_all_screens_shared_slides(tmp_path):
    from src.graphics_engine import dump_all_screens

    out_dir = os.path.join(tmp_path, "extracted_img")
    res = dump_all_screens(
        rom_data_dir="extracted rom/data",
        output_image_dir=out_dir,
        directory="menu/Extra/illust",
    )
    assert res > 0
    assert res.slides == 31
    assert os.path.isfile(os.path.join(out_dir, "menu/Extra/illust/000.png"))
    assert os.path.isfile(os.path.join(out_dir, "menu/Extra/illust/000.json"))


def test_cli_dump_graphics_dir_flag(tmp_path):
    from src.cli import main

    out_dir = os.path.join(tmp_path, "extracted_img")
    code = main([
        "dump-graphics",
        "--dir", "title/bg",
        "--out", out_dir,
    ])
    assert code == 0
    assert os.path.isfile(os.path.join(out_dir, "title/bg/kenri.png"))


