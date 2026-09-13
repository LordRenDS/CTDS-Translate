"""Unit tests for NCER (Nitro Cell Resource) binary serialization and roundtrip."""

import os
import struct
import tempfile
import pytest

from src.graphics_engine import (
    build_ncer_file,
    rebuild_ncer_from_metadata,
    dump_ncgr_sprite,
    decompress_stream,
    OAM_SHAPES,
    WH_TO_OAM_SHAPE_SIZE,
)

ORIG_NCER = "extracted rom/data/title/obj/obj_logo_new.NCER"
ORIG_NCGR = "extracted rom/data/title/obj/obj_logo_new.NCGR"
ORIG_NCLR = "extracted rom/data/title/obj/obj_logo_new.NCLR"
TRANSLATED_JSON = "translated image/title/obj/obj_logo_new.json"


def test_ncer_roundtrip_obj_logo_new(tmp_path):
    """Verify roundtrip: read obj_logo_new.NCER, decompress, parse with dump_ncgr_sprite metadata,
    rebuild with build_ncer_file, and verify that the rebuilt NCER produces identical cells, OAMs,
    coordinates, shapes, sizes, and tiles."""
    if not os.path.isfile(ORIG_NCER) or not os.path.isfile(ORIG_NCGR):
        pytest.skip(f"Original ROM sprite files not found at '{ORIG_NCER}'")

    out_png = os.path.join(tmp_path, "orig_logo.png")
    out_json = os.path.join(tmp_path, "orig_logo.json")
    meta = dump_ncgr_sprite(ORIG_NCGR, ORIG_NCLR, out_png, out_json, ncer_path=ORIG_NCER)

    assert meta["is_cell_sheet"] is True
    assert "components" in meta

    # Rebuild NCER using build_ncer_file
    rebuilt_ncer_path = os.path.join(tmp_path, "rebuilt_logo.NCER")
    mapping_mode = meta.get("mapping_mode", 2)
    comp_layers = meta.get("compression_layers", 1)
    labels = meta.get("labels")

    rebuilt_bytes = build_ncer_file(
        components=meta["components"],
        out_ncer_path=rebuilt_ncer_path,
        mapping_mode=mapping_mode,
        compression_layers=comp_layers,
        labels=labels,
    )
    assert os.path.isfile(rebuilt_ncer_path)
    assert len(rebuilt_bytes) > 0

    # Decompress both and assert byte-for-byte match
    orig_raw = open(ORIG_NCER, "rb").read()
    orig_decomp, orig_layers = decompress_stream(orig_raw)
    reb_decomp, reb_layers = decompress_stream(rebuilt_bytes)

    assert reb_layers == orig_layers
    assert len(reb_decomp) == len(orig_decomp)
    assert reb_decomp == orig_decomp

    # Now re-dump with dump_ncgr_sprite using the rebuilt NCER
    redump_png = os.path.join(tmp_path, "redump_logo.png")
    redump_json = os.path.join(tmp_path, "redump_logo.json")
    remeta = dump_ncgr_sprite(ORIG_NCGR, ORIG_NCLR, redump_png, redump_json, ncer_path=rebuilt_ncer_path)

    orig_cells = [c for c in meta["components"] if c.get("type") == "cell"]
    reb_cells = [c for c in remeta["components"] if c.get("type") == "cell"]

    assert len(orig_cells) == len(reb_cells)
    for i in range(len(orig_cells)):
        c_orig = orig_cells[i]
        c_reb = reb_cells[i]
        assert c_orig["cell_idx"] == c_reb["cell_idx"]
        assert c_orig["min_x"] == c_reb["min_x"]
        assert c_orig["min_y"] == c_reb["min_y"]
        assert c_orig["width"] == c_reb["width"]
        assert c_orig["height"] == c_reb["height"]
        assert len(c_orig["oams"]) == len(c_reb["oams"])

        for o_orig, o_reb in zip(c_orig["oams"], c_reb["oams"]):
            assert o_orig["x"] == o_reb["x"]
            assert o_orig["y"] == o_reb["y"]
            assert o_orig["w"] == o_reb["w"]
            assert o_orig["h"] == o_reb["h"]
            assert o_orig["tile"] == o_reb["tile"]
            assert o_orig["pal"] == o_reb["pal"]
            assert o_orig["rot"] == o_reb["rot"]
            assert o_orig["hflip"] == o_reb["hflip"]
            assert o_orig["vflip"] == o_reb["vflip"]


def test_rebuild_ncer_from_metadata(tmp_path):
    """Verify rebuild_ncer_from_metadata rebuilds an NCER from a JSON metadata file."""
    if not os.path.isfile(TRANSLATED_JSON):
        pytest.skip(f"Metadata JSON not found at '{TRANSLATED_JSON}'")

    out_ncer = os.path.join(tmp_path, "from_meta.NCER")
    data = rebuild_ncer_from_metadata(TRANSLATED_JSON, out_ncer)

    assert os.path.isfile(out_ncer)
    assert os.path.getsize(out_ncer) == len(data)

    decomp, layers = decompress_stream(data)
    assert decomp[:4] == b"RECN"

    # If original NCER is present, verify decompressed byte equivalence
    if os.path.isfile(ORIG_NCER):
        orig_decomp, _ = decompress_stream(open(ORIG_NCER, "rb").read())
        assert decomp == orig_decomp


def test_build_ncer_synthetic_various_shapes(tmp_path):
    """Verify build_ncer_file with synthetic cells covering all OAM shapes, negative coordinates, and flips."""
    # Test all 12 standard OAM dimensions
    test_dimensions = list(WH_TO_OAM_SHAPE_SIZE.keys())
    oams = []
    for idx, (w, h) in enumerate(test_dimensions):
        oams.append({
            "x": -30 + idx * 8,
            "y": -10 + idx * 4,
            "w": w,
            "h": h,
            "tile": idx * 8,
            "pal": idx % 16,
            "rot": 0,
            "hflip": idx % 2,
            "vflip": (idx // 2) % 2,
        })

    components = [
        {"type": "cell", "cell_idx": 0, "cell_attr": 42, "oams": oams[:6], "label": "CustomCell0"},
        {"type": "cell", "cell_idx": 1, "cell_attr": 99, "oams": oams[6:], "label": "CustomCell1"},
        {"type": "uncovered", "cell_idx": -1, "oams": []},
    ]

    out_path = os.path.join(tmp_path, "synthetic.NCER")
    raw_bytes = build_ncer_file(
        components,
        out_ncer_path=out_path,
        mapping_mode=0,
        compression_layers=0,
    )

    assert os.path.isfile(out_path)
    assert len(raw_bytes) % 4 == 0  # 4-byte alignment rule

    # Check header
    magic, endian, version, total_size, hdr_size, num_blocks = struct.unpack("<4sHHIHH", raw_bytes[:16])
    assert magic == b"RECN"
    assert endian == 0xFEFF
    assert version == 0x0100
    assert total_size == len(raw_bytes)
    assert hdr_size == 16
    assert num_blocks == 3

    # Check Block 0: CEBK
    cebk_magic, cebk_size = struct.unpack("<4sI", raw_bytes[16:24])
    assert cebk_magic == b"KBEC"
    assert cebk_size % 4 == 0

    num_cells = struct.unpack("<H", raw_bytes[24:26])[0]
    assert num_cells == 2

    # Check cell entries
    cell_data_off = struct.unpack("<I", raw_bytes[28:32])[0]
    cell_start = 16 + 8 + cell_data_off
    n0, attr0, oam_off0 = struct.unpack("<HHI", raw_bytes[cell_start : cell_start + 8])
    assert n0 == 6
    assert attr0 == 42
    assert oam_off0 == 0

    n1, attr1, oam_off1 = struct.unpack("<HHI", raw_bytes[cell_start + 8 : cell_start + 16])
    assert n1 == 6
    assert attr1 == 99
    assert oam_off1 == 6 * 6

    # Check Block 1: LABL
    labl_start = 16 + cebk_size
    labl_magic, labl_size = struct.unpack("<4sI", raw_bytes[labl_start : labl_start + 8])
    assert labl_magic == b"LBAL"
    assert labl_size % 4 == 0

    labl_payload = raw_bytes[labl_start + 8 : labl_start + labl_size]
    off0, off1 = struct.unpack("<II", labl_payload[:8])
    str_base = 8
    s0 = labl_payload[str_base + off0 : labl_payload.find(b"\x00", str_base + off0)].decode("latin1")
    s1 = labl_payload[str_base + off1 : labl_payload.find(b"\x00", str_base + off1)].decode("latin1")
    assert s0 == "CustomCell0"
    assert s1 == "CustomCell1"

    # Check Block 2: UEXT
    uext_start = labl_start + labl_size
    uext_magic, uext_size = struct.unpack("<4sI", raw_bytes[uext_start : uext_start + 8])
    assert uext_magic == b"TXEU"
    assert uext_size == 12
    assert raw_bytes[uext_start + 8 : uext_start + 12] == b"\x00\x00\x00\x00"


def test_build_ncer_compression_layers(tmp_path):
    """Verify build_ncer_file compression options (uncompressed, 1-layer, 2-layer)."""
    components = [
        {"cell_idx": 0, "oams": [{"x": 0, "y": 0, "w": 8, "h": 8, "tile": 0}]}
    ]

    # Uncompressed
    uncomp = build_ncer_file(components, compression_layers=0)
    assert uncomp[:4] == b"RECN"

    # 1 layer
    comp1 = build_ncer_file(components, compression_layers=1)
    assert comp1[0] == 0x10
    decomp1, layers1 = decompress_stream(comp1)
    assert layers1 == 1
    assert decomp1 == uncomp

    # 2 layers
    comp2 = build_ncer_file(components, compression_layers=2)
    assert comp2[0] == 0x10
    decomp2, layers2 = decompress_stream(comp2)
    assert layers2 == 2
    assert decomp2 == uncomp
