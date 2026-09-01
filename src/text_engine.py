"""Text script engine for Chrono Trigger DS (.msg binary parser, serializer, and batch tools)."""

import os
import json
import struct
from typing import List, Dict, Any, Optional
from src.char_map import tokenize_bytes, detokenize_string


def dump_msg(msg_bytes: bytes, font_type: str = "big") -> List[Dict[str, Any]]:
    """Parses binary .msg data into a list of structured entry dictionaries.

    Args:
        msg_bytes: Raw binary content of a .msg file.
        font_type: 'big' for dialogue files, 'small' for system/menu files.

    Returns:
        List of dictionaries with keys: 'id', 'original_en', 'original_fr', 'translation'.

    Raises:
        ValueError: If file is too short or missing magic 'TEXT'.
    """
    if len(msg_bytes) < 16:
        raise ValueError(f"Invalid .msg binary: length {len(msg_bytes)} is less than header size 16")

    magic = msg_bytes[4:8]
    if magic != b"TEXT":
        raise ValueError(f"Invalid .msg magic: expected b'TEXT', got {magic!r}")

    lang_count, entry_count, _unk, file_size = struct.unpack_from("<BHBI", msg_bytes, 8)

    if entry_count == 0:
        return []

    ptr_count = entry_count * lang_count
    ptrs = [
        struct.unpack_from("<I", msg_bytes, 16 + j * 4)[0]
        for j in range(ptr_count)
    ]

    delim = bytes([msg_bytes[ptrs[0]]]) if ptrs[0] < len(msg_bytes) else (b"\x02" if font_type == "big" else b"\x00")

    entries: List[Dict[str, Any]] = []

    for i in range(entry_count):
        if lang_count >= 4:
            p0, p1, p2, p3 = ptrs[i * lang_count : i * lang_count + 4]

            # English text at p1
            end1 = msg_bytes.find(delim, p1)
            if end1 == -1 or (p2 > p1 and end1 > p2):
                end1 = p2 - 1 if p2 > p1 else p1
            raw_en = msg_bytes[p1:end1]
            en_text = tokenize_bytes(raw_en, font_type=font_type)

            # French text at p3
            next_p0 = (
                ptrs[(i + 1) * lang_count]
                if (i + 1) < entry_count
                else (file_size if file_size <= len(msg_bytes) else len(msg_bytes))
            )
            end3 = msg_bytes.find(delim, p3)
            if end3 == -1 or (next_p0 > p3 and end3 > next_p0):
                end3 = next_p0 - 1 if next_p0 > p3 else p3
            raw_fr = msg_bytes[p3:end3]
            fr_text = tokenize_bytes(raw_fr, font_type=font_type)

            entries.append({
                "id": i,
                "original_en": en_text,
                "original_fr": fr_text,
                "translation": "",
            })
        else:
            # Fallback for single-pointer or custom language slots
            p0 = ptrs[i * lang_count]
            p1 = p0 + 1 if p0 + 1 < len(msg_bytes) else p0
            next_p = (
                ptrs[(i + 1) * lang_count]
                if (i + 1) < entry_count
                else len(msg_bytes)
            )
            end1 = msg_bytes.find(delim, p1)
            if end1 == -1 or end1 > next_p:
                end1 = next_p - 1 if next_p > p1 else p1
            raw_text = msg_bytes[p1:end1]
            text = tokenize_bytes(raw_text, font_type=font_type)

            entries.append({
                "id": i,
                "original_en": text,
                "original_fr": "",
                "translation": "",
            })

    return entries


def build_msg(
    entries: List[Dict[str, Any]],
    original_msg_bytes: Optional[bytes] = None,
    font_type: str = "big",
) -> bytes:
    """Rebuilds binary .msg from entry dictionaries with updated pointer table.

    Args:
        entries: List of entry dicts containing 'original_en', 'original_fr', and optional 'translation'.
        original_msg_bytes: Optional original .msg binary for 100% bit-exact untouched preservation.
        font_type: 'big' for dialogue files, 'small' for system/menu files.

    Returns:
        Compiled binary bytes of the .msg file.
    """
    if original_msg_bytes is not None:
        has_translation = any(bool(e.get("translation")) for e in entries)
        if not has_translation:
            try:
                orig_entries = dump_msg(original_msg_bytes, font_type=font_type)
                if entries == orig_entries:
                    return original_msg_bytes
            except Exception:
                pass

        lang_count = original_msg_bytes[8]
        first_p0 = struct.unpack_from("<I", original_msg_bytes, 16)[0]
        delim = bytes([original_msg_bytes[first_p0]]) if first_p0 < len(original_msg_bytes) else (b"\x02" if font_type == "big" else b"\x00")
    else:
        lang_count = 4
        delim = b"\x02" if font_type == "big" else b"\x00"

    entry_count = len(entries)
    payload_start_offset = 16 + entry_count * lang_count * 4
    out_table: List[int] = []
    out_payload = bytearray()

    for entry in entries:
        en_text = entry.get("translation") or entry.get("original_en", "")
        fr_text = entry.get("original_fr", "")

        raw_en = detokenize_string(en_text, font_type=font_type)
        raw_fr = detokenize_string(fr_text, font_type=font_type)

        p0 = payload_start_offset + len(out_payload)
        p1 = p0 + 1
        p2 = p1 + len(raw_en) + 1
        p3 = p2 + 1

        out_payload.extend(delim + raw_en + delim)
        out_payload.extend(delim + raw_fr + delim)
        out_table.extend([p0, p1, p2, p3])

    total_size = payload_start_offset + len(out_payload)
    header = bytearray(16)
    header[4:8] = b"TEXT"
    struct.pack_into("<BHBI", header, 8, lang_count, entry_count, 0, total_size)

    table_bytes = bytearray()
    for ptr in out_table:
        table_bytes.extend(struct.pack("<I", ptr))

    return bytes(header + table_bytes + out_payload)


def dump_all_msg(nitrofs_dir: str, output_json_dir: str) -> int:
    """Recursively dumps all .msg files found in nitrofs_dir to JSON files.

    Args:
        nitrofs_dir: Path to extracted NitroFS root or msg folder.
        output_json_dir: Destination directory for JSON files.

    Returns:
        Total count of dumped .msg files.
    """
    dumped_count = 0

    for root, _dirs, files in os.walk(nitrofs_dir):
        for file in files:
            if file.lower().endswith(".msg"):
                msg_path = os.path.join(root, file)
                rel_path = os.path.relpath(msg_path, nitrofs_dir)
                rel_json = os.path.splitext(rel_path)[0] + ".json"
                json_path = os.path.join(output_json_dir, rel_json)

                os.makedirs(os.path.dirname(json_path), exist_ok=True)

                with open(msg_path, "rb") as f:
                    msg_bytes = f.read()

                font_type = "small" if "small" in rel_path.lower() else "big"
                entries = dump_msg(msg_bytes, font_type=font_type)

                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(entries, f, ensure_ascii=False, indent=2)

                dumped_count += 1

    return dumped_count


def insert_all_msg(json_dir: str, target_nitrofs_dir: str) -> int:
    """Recursively compiles and inserts all JSON translation files into target NitroFS directory.

    Args:
        json_dir: Directory containing dumped/translated JSON files.
        target_nitrofs_dir: Destination directory where .msg files are located.

    Returns:
        Total count of updated .msg files.
    """
    inserted_count = 0

    for root, _dirs, files in os.walk(json_dir):
        for file in files:
            if file.lower().endswith(".json"):
                json_path = os.path.join(root, file)
                rel_path = os.path.relpath(json_path, json_dir)
                rel_msg = os.path.splitext(rel_path)[0] + ".msg"
                target_msg_path = os.path.join(target_nitrofs_dir, rel_msg)

                with open(json_path, "r", encoding="utf-8") as f:
                    entries = json.load(f)

                orig_bytes = None
                if os.path.isfile(target_msg_path):
                    with open(target_msg_path, "rb") as f:
                        orig_bytes = f.read()

                font_type = "small" if "small" in rel_path.lower() else "big"
                compiled_msg = build_msg(entries, original_msg_bytes=orig_bytes, font_type=font_type)

                os.makedirs(os.path.dirname(target_msg_path), exist_ok=True)
                with open(target_msg_path, "wb") as f:
                    f.write(compiled_msg)

                inserted_count += 1

    return inserted_count
