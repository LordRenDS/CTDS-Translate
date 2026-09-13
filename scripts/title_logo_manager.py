"""Title Logo Manager for Chrono Trigger DS.

Provides tools for working with `obj_logo_new` sprite sheets:
- Visual guide generation (markup overlay).
- OAM seam and gap constraint validation.
- Automatic cell synchronization (Cell 0 -> Cell 3, Cell 1 -> Cell 4, Cell 2 -> Cell 5).
- Simulated Nintendo DS screen rendering preview.
- Rebuilding NCGR and NCER binaries into the ROM data directory.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.graphics_engine import (
    build_ncgr_sprite,
    decompress_stream,
    dump_ncgr_sprite,
    parse_nclr_palette,
    rebuild_ncer_from_metadata,
)

DEFAULT_PNG = PROJECT_ROOT / "translated image" / "title" / "obj" / "obj_logo_new.png"
DEFAULT_JSON = PROJECT_ROOT / "translated image" / "title" / "obj" / "obj_logo_new.json"
EXTRACTED_JSON = PROJECT_ROOT / "extracted image" / "title" / "obj" / "obj_logo_new.json"
DEFAULT_NCLR = PROJECT_ROOT / "extracted rom" / "data" / "title" / "obj" / "obj_logo_new.NCLR"
DEFAULT_NCER = PROJECT_ROOT / "extracted rom" / "data" / "title" / "obj" / "obj_logo_new.NCER"


def load_metadata(json_path: Path = DEFAULT_JSON) -> Tuple[dict, Dict[int, dict]]:
    """Loads metadata JSON and returns (metadata_dict, cells_by_id)."""
    target = json_path if json_path.is_file() else EXTRACTED_JSON
    with open(target, "r", encoding="utf-8") as f:
        meta = json.load(f)
    cells = {comp["cell_idx"]: comp for comp in meta.get("components", []) if "cell_idx" in comp}
    return meta, cells


def cmd_validate(png_path: Path = DEFAULT_PNG, json_path: Path = DEFAULT_JSON) -> bool:
    """Validates the sprite sheet image against Nintendo DS OAM hardware constraints.

    Returns True if valid, False if violations are detected.
    """
    if not png_path.is_file():
        print(f"[ERROR] Sprite PNG not found: {png_path}")
        return False

    meta, cells = load_metadata(json_path)
    img = Image.open(png_path)
    is_valid = True

    print(f"Validating sprite sheet: {png_path.name} (mode: {img.mode}, size: {img.size})")

    # 1. Mode check
    if img.mode != "P":
        print(f"  [FAIL] Image mode is '{img.mode}', expected indexed palette mode 'P'.")
        is_valid = False
    else:
        print("  [PASS] Palette mode is 'P' (indexed).")

    # 2. Dimensions check
    expected_size = (meta.get("sheet_width", 256), meta.get("sheet_height", 250))
    if img.size != expected_size:
        print(f"  [FAIL] Dimensions {img.size} do not match expected {expected_size}.")
        is_valid = False
    else:
        print(f"  [PASS] Dimensions match {expected_size}.")

    # 3. Cell 0 Seam check (x=48)
    if 0 in cells:
        c0 = cells[0]
        cx, cy = c0["canvas_x"], c0["canvas_y"]
        h = c0["height"]
        seam_violations = []
        for y in range(h):
            p = img.getpixel((cx + 48, cy + y))
            val = p if isinstance(p, int) else p[0]
            if val != 0:
                seam_violations.append((48, y, val))

        if seam_violations:
            print(f"  [FAIL] Cell 0: {len(seam_violations)} non-zero pixels found on seam x=48!")
            print("         The left word (0..47) and right word (48..95) must be separated by an empty boundary at x=48.")
            is_valid = False
        else:
            print("  [PASS] Cell 0: Seam at x=48 is clean (no overlapping text).")

    # 4. Cell 1 Seam check (x=48)
    if 1 in cells:
        c1 = cells[1]
        cx, cy = c1["canvas_x"], c1["canvas_y"]
        seam_violations = []
        for y in range(24):
            p = img.getpixel((cx + 48, cy + y))
            val = p if isinstance(p, int) else p[0]
            if val != 0:
                seam_violations.append((48, y, val))

        if seam_violations:
            print(f"  [FAIL] Cell 1: {len(seam_violations)} non-zero pixels found on seam x=48!")
            is_valid = False
        else:
            print("  [PASS] Cell 1: Seam at x=48 is clean.")

    # 5. Cell 3 Gap check (x=48..51)
    if 3 in cells:
        c3 = cells[3]
        cx, cy = c3["canvas_x"], c3["canvas_y"]
        h = c3["height"]
        gap_violations = []
        for x in range(48, 52):
            for y in range(h):
                p = img.getpixel((cx + x, cy + y))
                val = p if isinstance(p, int) else p[0]
                if val != 0:
                    gap_violations.append((x, y, val))

        if gap_violations:
            print(f"  [FAIL] Cell 3: {len(gap_violations)} non-zero pixels found in 4px hardware gap (x=48..51)!")
            print("         Pixels in this zone will never be rendered and will cause tile misalignment.")
            is_valid = False
        else:
            print("  [PASS] Cell 3: 4px hardware gap (x=48..51) is clean.")

    # 6. Synchronization check: Cell 3 vs Cell 0
    if 0 in cells and 3 in cells:
        c0 = cells[0]
        c3 = cells[3]
        mismatches = 0
        for y in range(24):
            for x in range(48):
                p0 = img.getpixel((c0["canvas_x"] + x, c0["canvas_y"] + y))
                p3 = img.getpixel((c3["canvas_x"] + x, c3["canvas_y"] + y))
                if p0 != p3:
                    mismatches += 1
            for x in range(48):
                p0 = img.getpixel((c0["canvas_x"] + 48 + x, c0["canvas_y"] + y))
                p3 = img.getpixel((c3["canvas_x"] + 52 + x, c3["canvas_y"] + y))
                if p0 != p3:
                    mismatches += 1
        if mismatches > 0:
            print(f"  [WARN] Cell 3 does not match Cell 0 (+4px shift)! ({mismatches} pixels differ)")
            print("         Because Cell 0 and Cell 3 share tiles in ROM, this will cause visual glitches in the game.")
            print("         Run 'python scripts/title_logo_manager.py sync' to automatically synchronize them.")
            is_valid = False
        else:
            print("  [PASS] Cell 3 perfectly synchronizes with Cell 0.")

    print("\nValidation Result: " + ("PASSED" if is_valid else "FAILED"))
    return is_valid


def cmd_sync(png_path: Path = DEFAULT_PNG, json_path: Path = DEFAULT_JSON, out_path: Optional[Path] = None) -> bool:
    """Synchronizes duplicate cells:
    - Cell 0 -> Cell 3 (with +4px hardware right-OAM shift).
    - Cell 1 -> Cell 4 (with +4px hardware right-OAM shift and +2px subtitle shift).
    - Cell 2 -> Cell 5 (exact copy).

    Allows users to only edit Cell 0, 1, 2, and automatically formats Cell 3, 4, 5.
    """
    if out_path is None:
        out_path = png_path

    meta, cells = load_metadata(json_path)
    img = Image.open(png_path)
    canvas = img.copy()

    print("Synchronizing duplicate cells (Cell 0->3, Cell 1->4, Cell 2->5)...")

    # Cell 0 -> Cell 3
    if 0 in cells and 3 in cells:
        c0, c3 = cells[0], cells[3]
        # Clear Cell 3 area
        for y in range(c3["height"]):
            for x in range(c3["width"]):
                canvas.putpixel((c3["canvas_x"] + x, c3["canvas_y"] + y), 0)
        # Copy left OAM (0..47)
        for y in range(24):
            for x in range(48):
                p = img.getpixel((c0["canvas_x"] + x, c0["canvas_y"] + y))
                canvas.putpixel((c3["canvas_x"] + x, c3["canvas_y"] + y), p)
        # Copy right OAM (48..95) to Cell 3 (52..99)
        for y in range(24):
            for x in range(48):
                p = img.getpixel((c0["canvas_x"] + 48 + x, c0["canvas_y"] + y))
                canvas.putpixel((c3["canvas_x"] + 52 + x, c3["canvas_y"] + y), p)
        print("  [OK] Synchronized Cell 0 -> Cell 3 (applied +4px OAM shift).")

    # Cell 1 -> Cell 4
    if 1 in cells and 4 in cells:
        c1, c4 = cells[1], cells[4]
        for y in range(c4["height"]):
            for x in range(c4["width"]):
                canvas.putpixel((c4["canvas_x"] + x, c4["canvas_y"] + y), 0)
        for y in range(24):
            for x in range(48):
                p = img.getpixel((c1["canvas_x"] + x, c1["canvas_y"] + y))
                canvas.putpixel((c4["canvas_x"] + x, c4["canvas_y"] + y), p)
        for y in range(24):
            for x in range(48):
                p = img.getpixel((c1["canvas_x"] + 48 + x, c1["canvas_y"] + y))
                canvas.putpixel((c4["canvas_x"] + 52 + x, c4["canvas_y"] + y), p)
        # Subtitle shift: c1 x=16..80 (w=64) -> c4 x=18..82
        for y in range(24, 40):
            for x in range(64):
                p = img.getpixel((c1["canvas_x"] + 16 + x, c1["canvas_y"] + y))
                canvas.putpixel((c4["canvas_x"] + 18 + x, c4["canvas_y"] + y), p)
        print("  [OK] Synchronized Cell 1 -> Cell 4 (applied +4px right OAM shift and +2px subtitle shift).")

    # Cell 2 -> Cell 5
    if 2 in cells and 5 in cells:
        c2, c5 = cells[2], cells[5]
        for y in range(c5["height"]):
            for x in range(c5["width"]):
                canvas.putpixel((c5["canvas_x"] + x, c5["canvas_y"] + y), 0)
        for y in range(c5["height"]):
            for x in range(c5["width"]):
                p = img.getpixel((c2["canvas_x"] + x, c2["canvas_y"] + y))
                canvas.putpixel((c5["canvas_x"] + x, c5["canvas_y"] + y), p)
        print("  [OK] Synchronized Cell 2 -> Cell 5 (exact copy).")

    canvas.save(out_path, transparency=0)
    print(f"Saved synchronized sprite sheet to: {out_path}")
    return True


def cmd_preview(cell_idx: int = 0, png_path: Path = DEFAULT_PNG, json_path: Path = DEFAULT_JSON, out_dir: Optional[Path] = None):
    """Renders a simulated Nintendo DS screen preview of a given cell."""
    if out_dir is None:
        out_dir = PROJECT_ROOT / "build" / "previews"
    out_dir.mkdir(parents=True, exist_ok=True)

    meta, cells = load_metadata(json_path)
    if cell_idx not in cells:
        print(f"[ERROR] Cell ID {cell_idx} not found in metadata.")
        return

    comp = cells[cell_idx]
    nclr_path = meta.get("nclr_path")
    if not nclr_path or not os.path.isfile(nclr_path):
        nclr_path = str(DEFAULT_NCLR)

    with open(nclr_path, "rb") as f:
        colors = parse_nclr_palette(f.read())

    # Create 256x192 NDS screen canvas (dark gray background)
    screen = Image.new("RGBA", (256, 192), (32, 34, 40, 255))
    src_img = Image.open(png_path)

    # Center cell on preview screen
    base_x = (256 - comp["width"]) // 2
    base_y = (192 - comp["height"]) // 2

    for o in comp["oams"]:
        ox = o["x"] - comp["min_x"]
        oy = o["y"] - comp["min_y"]
        w = o["w"]
        h = o["h"]
        crop = src_img.crop((comp["canvas_x"] + ox, comp["canvas_y"] + oy, comp["canvas_x"] + ox + w, comp["canvas_y"] + oy + h))
        for py in range(h):
            for px in range(w):
                p = crop.getpixel((px, py))
                val = p if isinstance(p, int) else p[0]
                if val != 0:
                    rgb = (colors[val * 3], colors[val * 3 + 1], colors[val * 3 + 2], 255)
                    screen.putpixel((base_x + ox + px, base_y + oy + py), rgb)

    out_file = out_dir / f"preview_cell_{cell_idx}.png"
    screen.save(out_file)
    print(f"Generated NDS screen preview for Cell {cell_idx}: {out_file}")


def cmd_rebuild(rom_data_dir: Optional[Path] = None):
    """Rebuilds both obj_logo_new.NCGR and obj_logo_new.NCER into the target ROM directory."""
    if rom_data_dir is None:
        rom_data_dir = PROJECT_ROOT / "extracted rom" / "data" / "title" / "obj"
    rom_data_dir.mkdir(parents=True, exist_ok=True)

    out_ncgr = rom_data_dir / "obj_logo_new.NCGR"
    out_ncer = rom_data_dir / "obj_logo_new.NCER"

    print(f"Rebuilding NCGR sprite: {DEFAULT_PNG} -> {out_ncgr}...")
    build_ncgr_sprite(str(DEFAULT_PNG), str(DEFAULT_JSON), str(out_ncgr))

    print(f"Rebuilding NCER cell resource: {DEFAULT_JSON} -> {out_ncer}...")
    rebuild_ncer_from_metadata(str(DEFAULT_JSON), str(out_ncer))

    print("Rebuild complete! Files successfully inserted into ROM data directory.")


def main():
    parser = argparse.ArgumentParser(description="Chrono Trigger DS Title Logo Sprite Sheet Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # validate
    p_val = subparsers.add_parser("validate", help="Validate sprite sheet against OAM constraints")
    p_val.add_argument("--png", type=Path, default=DEFAULT_PNG, help="Path to sprite sheet PNG")
    p_val.add_argument("--json", type=Path, default=DEFAULT_JSON, help="Path to metadata JSON")

    # sync
    p_sync = subparsers.add_parser("sync", help="Sync Cell 0->3, Cell 1->4, Cell 2->5 with hardware offsets")
    p_sync.add_argument("--png", type=Path, default=DEFAULT_PNG, help="Input sprite sheet PNG")
    p_sync.add_argument("--out", type=Path, default=None, help="Output PNG path (overwrites input if not specified)")

    # guide
    p_guide = subparsers.add_parser("guide", help="Generate annotated layout guide PNG")

    # preview
    p_prev = subparsers.add_parser("preview", help="Render simulated NDS screen preview")
    p_prev.add_argument("--cell", type=int, default=0, help="Cell ID to preview (default: 0)")

    # rebuild
    p_reb = subparsers.add_parser("rebuild", help="Rebuild obj_logo_new.NCGR and obj_logo_new.NCER")
    p_reb.add_argument("--rom-data", type=Path, default=None, help="Target ROM title/obj directory")

    args = parser.parse_args()

    if args.command == "validate":
        success = cmd_validate(args.png, args.json)
        sys.exit(0 if success else 1)
    elif args.command == "sync":
        cmd_sync(args.png, DEFAULT_JSON, args.out)
    elif args.command == "guide":
        import subprocess
        subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "render_layout_guide.py")], check=True)
    elif args.command == "preview":
        cmd_preview(args.cell)
    elif args.command == "rebuild":
        cmd_rebuild(args.rom_data)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
