"""Character mapping and control code tokenizer for Chrono Trigger DS text engine."""

import re
from typing import Dict

# ---------------------------------------------------------------------------
# Character Mapping Tables
# ---------------------------------------------------------------------------

CHAR_TO_BYTE: Dict[str, int] = {}
BYTE_TO_CHAR: Dict[int, str] = {}

# Tab character (0x09)
CHAR_TO_BYTE["\t"] = 0x09
BYTE_TO_CHAR[0x09] = "\t"

# Standard printable ASCII (0x20..0x7E) maps to bytecode ord(c) - 1 (0x1F..0x7D)
for code in range(0x20, 0x7F):
    char = chr(code)
    byte_val = code - 1
    CHAR_TO_BYTE[char] = byte_val
    BYTE_TO_CHAR[byte_val] = char

# Extended Cyrillic characters (Russian alphabet):
# Uppercase А..Я (0x0410..0x042F) -> 0x80..0x9F
for i in range(32):
    char = chr(0x0410 + i)
    byte_val = 0x80 + i
    CHAR_TO_BYTE[char] = byte_val
    BYTE_TO_CHAR[byte_val] = char

# Lowercase а..я (0x0430..0x044F) -> 0xA0..0xBF
for i in range(32):
    char = chr(0x0430 + i)
    byte_val = 0xA0 + i
    CHAR_TO_BYTE[char] = byte_val
    BYTE_TO_CHAR[byte_val] = char

# Cyrillic Ё and ё -> 0xC0 and 0xC1
CHAR_TO_BYTE["Ё"] = 0xC0
BYTE_TO_CHAR[0xC0] = "Ё"
CHAR_TO_BYTE["ё"] = 0xC1
BYTE_TO_CHAR[0xC1] = "ё"

# ---------------------------------------------------------------------------
# Control Code Definitions
# ---------------------------------------------------------------------------

MULTI_BYTE_TO_TAG: Dict[bytes, str] = {
    b"\xC5\xB7": "{CRONO}",
    b"\xC5\xB8": "{MARLE}",
    b"\xC5\xB9": "{LUCCA}",
    b"\xC5\xBA": "{ROBO}",
    b"\xC5\xBB": "{FROG}",
    b"\xC5\xBC": "{AYLA}",
    b"\xC5\xBD": "{MAGUS}",
    b"\xC5\xBE": "{EPOCH}",
    b"\xC5\xBF": "{WAIT_KEY}",
}

TAG_TO_MULTI_BYTE: Dict[str, bytes] = {
    "{CRONO}": b"\xC5\xB7",
    "{MARLE}": b"\xC5\xB8",
    "{LUCCA}": b"\xC5\xB9",
    "{ROBO}": b"\xC5\xBA",
    "{FROG}": b"\xC5\xBB",
    "{AYLA}": b"\xC5\xBC",
    "{MAGUS}": b"\xC5\xBD",
    "{EPOCH}": b"\xC5\xBE",
    "{WAIT_KEY}": b"\xC5\xBF",
    "{WAIT}": b"\xC5\xBF",
}

# Regex pattern to match tags, escape codes, or newlines in text
TAG_PATTERN = re.compile(r"\{[^\}]+\}|\r?\n|\\x[0-9A-Fa-f]{2}")


def encode_char(char: str) -> int:
    """Encodes a single character into its corresponding game bytecode value.

    Args:
        char: Single character to encode.

    Returns:
        Integer bytecode value.

    Raises:
        ValueError: If character is not present in character mapping table.
    """
    if char in CHAR_TO_BYTE:
        return CHAR_TO_BYTE[char]
    raise ValueError(f"Unmapped character: {char!r}")


def decode_char(byte_val: int) -> str:
    """Decodes a single bytecode value into its corresponding character.

    Args:
        byte_val: Integer bytecode value.

    Returns:
        Decoded character string.

    Raises:
        ValueError: If byte value is not present in character mapping table.
    """
    if byte_val in BYTE_TO_CHAR:
        return BYTE_TO_CHAR[byte_val]
    raise ValueError(f"Unmapped byte value: 0x{byte_val:02X}")


def tokenize_bytes(raw_bytes: bytes) -> str:
    """Converts raw binary bytecode into a human-readable string with anchors/tags.

    Args:
        raw_bytes: Binary bytecode to decode.

    Returns:
        Human-readable text string with control tags (e.g. {CRONO}, {WAIT_KEY}, \\n).
    """
    tokens: list[str] = []
    i = 0
    n = len(raw_bytes)

    while i < n:
        # Check multi-byte fixed control sequences
        if i + 1 < n:
            two_bytes = bytes(raw_bytes[i : i + 2])
            if two_bytes in MULTI_BYTE_TO_TAG:
                tokens.append(MULTI_BYTE_TO_TAG[two_bytes])
                i += 2
                continue

            # Check EVENT_SYNC / SOUND sequences: \xC6\x95 ... \xC6\x96
            if two_bytes == b"\xC6\x95":
                end_idx = raw_bytes.find(b"\xC6\x96", i + 2)
                if end_idx != -1 and (end_idx - (i + 2)) <= 16:
                    payload = raw_bytes[i + 2 : end_idx]
                    tokens.append(f"{{EVENT_SYNC:{payload.hex().upper()}}}")
                    i = end_idx + 2
                    continue

        b = raw_bytes[i]
        if b == 0x00:
            tokens.append("{NULL}")
        elif b == 0x01:
            tokens.append("\n")
        elif b == 0x02:
            tokens.append("{PAGE}")
        elif b in BYTE_TO_CHAR:
            tokens.append(BYTE_TO_CHAR[b])
        else:
            tokens.append(f"{{TAG:{b:02X}}}")
        i += 1

    return "".join(tokens)


def detokenize_string(text: str) -> bytes:
    """Converts a human-readable string with tags back into raw binary bytecode.

    Args:
        text: Human-readable text string with control tags.

    Returns:
        Binary bytecode.

    Raises:
        ValueError: If unmapped characters or unrecognized tags are encountered.
    """
    out = bytearray()
    pos = 0

    for match in TAG_PATTERN.finditer(text):
        start, end = match.span()

        # Process characters preceding the tag
        if start > pos:
            for ch in text[pos:start]:
                if ch == "\r":
                    continue
                if ch in CHAR_TO_BYTE:
                    out.append(CHAR_TO_BYTE[ch])
                else:
                    raise ValueError(f"Unmapped character in text: {ch!r}")

        tag_str = match.group(0)

        if tag_str in ("\n", "\r\n", "{LINE}"):
            out.append(0x01)
        elif tag_str == "{NULL}":
            out.append(0x00)
        elif tag_str == "{PAGE}":
            out.append(0x02)
        elif tag_str in TAG_TO_MULTI_BYTE:
            out.extend(TAG_TO_MULTI_BYTE[tag_str])
        elif tag_str.startswith("{EVENT_SYNC:") or tag_str.startswith("{SOUND:"):
            hex_part = tag_str.split(":", 1)[1].rstrip("}")
            out.extend(b"\xC6\x95" + bytes.fromhex(hex_part) + b"\xC6\x96")
        elif tag_str.startswith("{TAG:"):
            hex_part = tag_str.split(":", 1)[1].rstrip("}")
            out.extend(bytes.fromhex(hex_part))
        elif tag_str.startswith("\\x"):
            hex_part = tag_str[2:]
            out.extend(bytes.fromhex(hex_part))
        else:
            raise ValueError(f"Unrecognized control tag: {tag_str}")

        pos = end

    # Process remaining characters after the last tag
    if pos < len(text):
        for ch in text[pos:]:
            if ch == "\r":
                continue
            if ch in CHAR_TO_BYTE:
                out.append(CHAR_TO_BYTE[ch])
            else:
                raise ValueError(f"Unmapped character in text: {ch!r}")

    return bytes(out)
