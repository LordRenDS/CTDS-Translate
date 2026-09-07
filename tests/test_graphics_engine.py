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
    assert os.path.isfile(os.path.join(target_rom_dir, "title/bg/kenri_nsc.bin"))





