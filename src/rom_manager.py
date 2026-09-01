"""ROM Manager module for unpacking, rebuilding, and verifying Nintendo DS ROMs."""

import os
import re
from typing import Any, Dict, List, Optional
import ndspy.code
import ndspy.fnt
import ndspy.rom


def get_nitrofs_paths(rom: ndspy.rom.NintendoDSRom) -> List[str]:
    """Retrieve all file paths stored in the ROM's NitroFS filename table.

    Args:
        rom: The loaded NintendoDSRom instance.

    Returns:
        List of POSIX relative file paths within NitroFS.
    """
    if not rom.filenames:
        return []
    paths: List[str] = []
    for i in range(rom.filenames.firstID, len(rom.files)):
        filename = rom.filenames.filenameOf(i)
        if filename is not None:
            paths.append(filename)
    return paths


def _create_folder_from_dir(dir_path: str, start_id: int = 0) -> tuple[ndspy.fnt.Folder, List[bytes], int]:
    """Recursively builds an ndspy.fnt.Folder and list of file contents from a directory.

    Args:
        dir_path: Path to root directory on disk.
        start_id: Starting file ID for this folder level.

    Returns:
        Tuple of (Folder instance, list of file byte objects, next available file ID).
    """
    entries = sorted(os.listdir(dir_path))
    file_names = [e for e in entries if os.path.isfile(os.path.join(dir_path, e))]
    dir_names = [e for e in entries if os.path.isdir(os.path.join(dir_path, e))]

    file_bytes: List[bytes] = []
    for fname in file_names:
        with open(os.path.join(dir_path, fname), "rb") as f:
            file_bytes.append(f.read())

    current_id = start_id + len(file_names)
    subfolders: List[tuple[str, ndspy.fnt.Folder]] = []

    for dname in dir_names:
        sub_folder, sub_file_bytes, current_id = _create_folder_from_dir(
            os.path.join(dir_path, dname), current_id
        )
        subfolders.append((dname, sub_folder))
        file_bytes.extend(sub_file_bytes)

    folder = ndspy.fnt.Folder(folders=subfolders, files=file_names, firstID=start_id)
    return folder, file_bytes, current_id


def unpack_rom(nds_path: str, output_dir: str) -> Dict[str, Any]:
    """Extracts all components from an NDS ROM into a target directory.

    Extracts:
    - ARM9 binary -> output_dir/arm9.bin
    - ARM7 binary -> output_dir/arm7.bin
    - Icon/Banner -> output_dir/banner.bin (if present)
    - ARM9 Overlays -> output_dir/overlays/overlay9_XXXX.bin (if present)
    - NitroFS files -> output_dir/data/<path>

    Args:
        nds_path: Path to source .nds file.
        output_dir: Destination directory for extracted assets.

    Returns:
        Metadata dictionary containing name, id_code, arm9_size, arm7_size, and file_count.
    """
    rom = ndspy.rom.NintendoDSRom.fromFile(nds_path)
    os.makedirs(output_dir, exist_ok=True)

    if rom.arm9:
        with open(os.path.join(output_dir, "arm9.bin"), "wb") as f:
            f.write(rom.arm9)

    if rom.arm7:
        with open(os.path.join(output_dir, "arm7.bin"), "wb") as f:
            f.write(rom.arm7)

    if rom.iconBanner:
        with open(os.path.join(output_dir, "banner.bin"), "wb") as f:
            f.write(rom.iconBanner)

    overlays = rom.loadArm9Overlays()
    if overlays:
        ov_dir = os.path.join(output_dir, "overlays")
        os.makedirs(ov_dir, exist_ok=True)
        for ov_id, ov in overlays.items():
            ov_filename = f"overlay9_{ov_id:04d}.bin"
            with open(os.path.join(ov_dir, ov_filename), "wb") as f:
                f.write(ov.data)

    file_count = 0
    if rom.filenames is not None:
        def _extract_folder(folder, current_dir):
            nonlocal file_count
            os.makedirs(current_dir, exist_ok=True)
            for i, filename in enumerate(folder.files):
                fid = folder.firstID + i
                if fid < len(rom.files):
                    with open(os.path.join(current_dir, filename), "wb") as f:
                        f.write(rom.files[fid])
                    file_count += 1
            for folder_name, subfolder in folder.folders:
                _extract_folder(subfolder, os.path.join(current_dir, folder_name))

        _extract_folder(rom.filenames, os.path.join(output_dir, "data"))

    name = rom.name.decode("latin-1", errors="ignore").rstrip("\x00") if rom.name else ""
    id_code = rom.idCode.decode("latin-1", errors="ignore").rstrip("\x00") if rom.idCode else ""

    return {
        "name": name,
        "id_code": id_code,
        "arm9_size": len(rom.arm9) if rom.arm9 is not None else 0,
        "arm7_size": len(rom.arm7) if rom.arm7 is not None else 0,
        "file_count": file_count,
    }


def build_rom(extracted_dir: str, output_nds_path: str, base_nds_path: Optional[str] = None) -> None:
    """Rebuilds an NDS ROM image from an extracted directory.

    Args:
        extracted_dir: Path to directory containing extracted assets (data/, arm9.bin, etc.).
        output_nds_path: Destination path for the rebuilt .nds file.
        base_nds_path: Optional path to clean base ROM to retain original header/timing/settings.
    """
    if base_nds_path and os.path.isfile(base_nds_path):
        rom = ndspy.rom.NintendoDSRom.fromFile(base_nds_path)
    else:
        rom = ndspy.rom.NintendoDSRom()

    arm9_path = os.path.join(extracted_dir, "arm9.bin")
    if os.path.isfile(arm9_path):
        with open(arm9_path, "rb") as f:
            rom.arm9 = bytearray(f.read())

    arm7_path = os.path.join(extracted_dir, "arm7.bin")
    if os.path.isfile(arm7_path):
        with open(arm7_path, "rb") as f:
            rom.arm7 = bytearray(f.read())

    banner_path = os.path.join(extracted_dir, "banner.bin")
    if os.path.isfile(banner_path):
        with open(banner_path, "rb") as f:
            rom.iconBanner = bytearray(f.read())

    ov_dir = os.path.join(extracted_dir, "overlays")
    if os.path.isdir(ov_dir) and rom.arm9OverlayTable:
        overlays = rom.loadArm9Overlays()
        modified_overlays = False
        for fname in os.listdir(ov_dir):
            m = re.search(r"(\d+)\.bin$", fname)
            if m:
                ov_id = int(m.group(1))
                if ov_id in overlays:
                    with open(os.path.join(ov_dir, fname), "rb") as f:
                        new_data = bytearray(f.read())
                    if overlays[ov_id].data != new_data:
                        overlays[ov_id].data = new_data
                        rom.files[overlays[ov_id].fileID] = overlays[ov_id].save(
                            compress=overlays[ov_id].compressed
                        )
                        modified_overlays = True
        if modified_overlays:
            rom.arm9OverlayTable = ndspy.code.saveOverlayTable(overlays)

    data_dir = os.path.join(extracted_dir, "data")
    if os.path.isdir(data_dir):
        if base_nds_path and os.path.isfile(base_nds_path):
            path_to_id = {}

            def _map_folder(folder, prefix=""):
                for i, name in enumerate(folder.files):
                    fid = folder.firstID + i
                    p = f"{prefix}/{name}" if prefix else name
                    path_to_id[p] = fid
                for name, sub in folder.folders:
                    sub_p = f"{prefix}/{name}" if prefix else name
                    _map_folder(sub, sub_p)

            if rom.filenames:
                _map_folder(rom.filenames)

            for root, _, files in os.walk(data_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, data_dir).replace("\\", "/")
                    fid = path_to_id.get(rel_path)
                    if fid is not None and fid < len(rom.files):
                        with open(full_path, "rb") as f:
                            file_data = f.read()
                        if rom.files[fid] != file_data:
                            rom.files[fid] = file_data
        else:
            folder, file_bytes, _ = _create_folder_from_dir(data_dir, start_id=0)
            rom.filenames = folder
            rom.files = file_bytes

    out_parent = os.path.dirname(os.path.abspath(output_nds_path))
    if out_parent:
        os.makedirs(out_parent, exist_ok=True)
    rom.saveToFile(output_nds_path)


def verify_rom_integrity(original_nds_path: str, rebuilt_nds_path: str) -> bool:
    """Compares two NDS ROM files and verifies that all filenames and file contents match.

    Args:
        original_nds_path: Path to original reference .nds ROM.
        rebuilt_nds_path: Path to rebuilt .nds ROM.

    Returns:
        True if all files, code sections, banners, and overlays match exactly; False otherwise.
    """
    if not os.path.isfile(original_nds_path) or not os.path.isfile(rebuilt_nds_path):
        return False

    r1 = ndspy.rom.NintendoDSRom.fromFile(original_nds_path)
    r2 = ndspy.rom.NintendoDSRom.fromFile(rebuilt_nds_path)

    if (r1.arm9 or b"") != (r2.arm9 or b""):
        return False
    if (r1.arm7 or b"") != (r2.arm7 or b""):
        return False
    if (r1.iconBanner or b"") != (r2.iconBanner or b""):
        return False
    if (r1.arm9OverlayTable or b"") != (r2.arm9OverlayTable or b""):
        return False

    if len(r1.files) != len(r2.files):
        return False

    for f1, f2 in zip(r1.files, r2.files):
        if f1 != f2:
            return False

    paths1 = get_nitrofs_paths(r1)
    paths2 = get_nitrofs_paths(r2)
    if paths1 != paths2:
        return False

    return True
