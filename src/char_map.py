"""Character mapping and control token engine for Chrono Trigger DS.

Maps characters to proprietary font glyph indices for both dialogue ('big') and
system/menu ('small') fonts, handles Cyrillic localization glyph codes, and provides
bidirectional tokenization for game control sequences.
"""

from typing import Dict, List, Optional

# Big font character-to-glyph table (from msg/big/msgcmn.fnt)
BIG_CHAR_TO_GLYPH: Dict[str, int] = {
    '\n': 17, ' ': 1, '!': 27, '"': 89, '#': 133, '$': 354, '%': 96, '&': 110, "'": 26,
    '(': 71, ')': 70, '*': 102, '+': 85, ',': 28, '-': 30, '.': 14, '/': 72,
    '0': 57, '1': 63, '2': 65, '3': 69, '4': 73, '5': 75, '6': 76, '7': 82, '8': 81, '9': 77,
    ':': 23, ';': 355, '<': 135, '=': 113, '>': 121, '?': 33, '@': 356,
    'A': 39, 'B': 45, 'C': 35, 'D': 42, 'E': 52, 'F': 48, 'G': 46, 'H': 51, 'I': 36,
    'J': 58, 'K': 67, 'L': 41, 'M': 37, 'N': 49, 'O': 44, 'P': 40, 'Q': 68, 'R': 47,
    'S': 31, 'T': 38, 'U': 66, 'V': 53, 'W': 54, 'X': 91, 'Y': 61, 'Z': 80,
    '[': 357, '\\': 358, ']': 359, '^': 360, '_': 90, '`': 361,
    'a': 3, 'b': 24, 'c': 16, 'd': 12, 'e': 0, 'f': 21, 'g': 19, 'h': 13, 'i': 9,
    'j': 50, 'k': 32, 'l': 11, 'm': 15, 'n': 8, 'o': 5, 'p': 18, 'q': 34, 'r': 6,
    's': 7, 't': 4, 'u': 10, 'v': 20, 'w': 29, 'x': 55, 'y': 22, 'z': 43,
    '{': 362, '|': 363, '}': 364, '~': 365,
    # Accented Latin characters
    'À': 323, 'Á': 324, 'Â': 104, 'Ä': 115, 'Ç': 105,
    'È': 325, 'É': 326, 'Ê': 98, 'Ë': 116, 'Œ': 83,
    'Ì': 327, 'Í': 328, 'Î': 103, 'Ï': 330, 'Ñ': 331,
    'Ò': 332, 'Ó': 333, 'Ô': 334, 'ß': 339,
    'Ù': 335, 'Ú': 336, 'Û': 337, 'Ü': 338,
    'à': 340, 'á': 341, 'â': 342, 'ä': 115, 'ç': 84,
    'è': 59, 'é': 25, 'ê': 64, 'ë': 116, 'œ': 94,
    'î': 78, 'ï': 108, 'ñ': 344,
    'ò': 345, 'ó': 346, 'ô': 79, 'ö': 347,
    'ù': 92, 'ú': 129, 'ü': 136,
    # Symbols & Punctuation
    '—': 86, '«': 88, '»': 93, '…': 111, '¡': 87, '¿': 109,
    '°': 114, '™': 106, '©': 107, '®': 117, '♀': 118, '♂': 119, '♪': 120
}

# Small font character-to-glyph table (from msg/small/msgcmn.fnt)
SMALL_CHAR_TO_GLYPH: Dict[str, int] = {
    '\n': 80, ' ': 4, '!': 66, '"': 98, '#': 340, '$': 341, '%': 342, '&': 91, "'": 45,
    '(': 63, ')': 64, '*': 343, '+': 90, ',': 94, '-': 44, '.': 55, '/': 71,
    '0': 48, '1': 65, '2': 58, '3': 67, '4': 75, '5': 76, '6': 73, '7': 79, '8': 87, '9': 74,
    ':': 86, ';': 344, '<': 345, '=': 346, '>': 347, '?': 68, '@': 348,
    'A': 25, 'B': 26, 'C': 28, 'D': 18, 'E': 40, 'F': 22, 'G': 33, 'H': 39, 'I': 36,
    'J': 62, 'K': 53, 'L': 35, 'M': 27, 'N': 47, 'O': 38, 'P': 29, 'Q': 78, 'R': 31,
    'S': 16, 'T': 30, 'U': 59, 'V': 43, 'W': 51, 'X': 72, 'Y': 54, 'Z': 61,
    '[': 349, '\\': 350, ']': 351, '^': 352, '_': 353, '`': 354,
    'a': 2, 'b': 20, 'c': 13, 'd': 15, 'e': 1, 'f': 37, 'g': 17, 'h': 23, 'i': 5,
    'j': 57, 'k': 34, 'l': 10, 'm': 11, 'n': 9, 'o': 6, 'p': 21, 'q': 49, 'r': 3,
    's': 14, 't': 7, 'u': 8, 'v': 32, 'w': 41, 'x': 50, 'y': 19, 'z': 46,
    '{': 355, '|': 356, '}': 357, '~': 358,
    # Accented Latin characters
    'é': 12, 'è': 24, 'à': 42, 'ê': 52, 'ç': 56, 'î': 60, 'ô': 69, 'ù': 70, 'û': 77,
    '—': 81, 'œ': 82, '«': 83, '»': 84, 'ë': 85, 'ï': 88, 'ü': 89,
    'É': 92, 'È': 93, 'À': 95, 'Ê': 96, 'Ç': 97, 'Î': 99, 'Ô': 100, 'Ù': 101, 'Û': 102,
    'Œ': 103, 'Ë': 104, 'Ï': 105, 'Ü': 106, '…': 107, '¡': 108, '¿': 109, '°': 110,
    '™': 111, '©': 112, '®': 113, '♀': 114, '♂': 115, '♪': 116, '★': 117,
    'Ñ': 331, 'ß': 323, 'ñ': 333
}

BIG_GLYPH_TO_CHAR: Dict[int, str] = {v: k for k, v in BIG_CHAR_TO_GLYPH.items()}
SMALL_GLYPH_TO_CHAR: Dict[int, str] = {v: k for k, v in SMALL_CHAR_TO_GLYPH.items()}

# Cyrillic alphabet (66 letters)
CYRILLIC_UPPER = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"  # 32 chars
CYRILLIC_LOWER = "абвгдежзийклмнопрстуфхцчшщъыьэюя"  # 32 chars
CYRILLIC_SPECIAL = [("Ё", 64), ("ё", 65)]             # 2 chars
ALL_CYRILLIC = list(CYRILLIC_UPPER) + list(CYRILLIC_LOWER) + ["Ё", "ё"]

CYRILLIC_BASE_GLYPH = 450

for idx, char in enumerate(ALL_CYRILLIC):
    glyph_idx = CYRILLIC_BASE_GLYPH + idx
    BIG_CHAR_TO_GLYPH[char] = glyph_idx
    BIG_GLYPH_TO_CHAR[glyph_idx] = char
    SMALL_CHAR_TO_GLYPH[char] = glyph_idx
    SMALL_GLYPH_TO_CHAR[glyph_idx] = char

# Special party member and dialogue control tokens
PARTY_CONTROL_TOKENS: Dict[bytes, str] = {
    b"\xC5\xB7": "{CRONO}",
    b"\xC5\xB8": "{MARLE}",
    b"\xC5\xB9": "{LUCCA}",
    b"\xC5\xBA": "{ROBO}",
    b"\xC5\xBB": "{FROG}",
    b"\xC5\xBC": "{AYLA}",
    b"\xC5\xBD": "{MAGUS}",
    b"\xC5\xBE": "{EPOCH}",
}
REV_PARTY_CONTROL_TOKENS: Dict[str, bytes] = {v: k for k, v in PARTY_CONTROL_TOKENS.items()}


def glyph_to_bytes(glyph_index: int) -> bytes:
    """Encodes a glyph index into variable-length bytes (1 or 2 bytes)."""
    if glyph_index < 128:
        return bytes([glyph_index])
    prefix = 0xC0 + (glyph_index >> 6)
    suffix = 0x80 + (glyph_index & 0x3F)
    return bytes([prefix, suffix])


def bytes_to_glyph(prefix: int, suffix: int) -> int:
    """Decodes a 2-byte sequence into its glyph index."""
    return ((prefix - 0xC0) << 6) | (suffix & 0x3F)


def tokenize_bytes(raw_bytes: bytes, font_type: str = "big") -> str:
    """Converts raw binary bytecode into a human-readable text string with control tags.

    Args:
        raw_bytes: Raw binary bytecode from a .msg file string.
        font_type: 'big' for dialogue files, 'small' for system/menu files.

    Returns:
        Human-readable text string.
    """
    raw_bytes = bytes(raw_bytes)
    g2c = BIG_GLYPH_TO_CHAR if font_type == "big" else SMALL_GLYPH_TO_CHAR
    res: List[str] = []
    i = 0

    while i < len(raw_bytes):
        b = raw_bytes[i]

        # 5-byte sequences: {EVENT_SYNC:XX} (0xC6 0x95 XX 0xC6 0x96) and {SOUND:XX} (0xC6 0x97 XX 0xC6 0x98)
        if b == 0xC6 and i + 4 < len(raw_bytes):
            b2 = raw_bytes[i + 1]
            b3 = raw_bytes[i + 2]
            b4 = raw_bytes[i + 3]
            b5 = raw_bytes[i + 4]
            if b2 == 0x95 and b4 == 0xC6 and b5 == 0x96:
                res.append(f"{{EVENT_SYNC:{b3:02X}}}")
                i += 5
                continue
            elif b2 == 0x97 and b4 == 0xC6 and b5 == 0x98:
                res.append(f"{{SOUND:{b3:02X}}}")
                i += 5
                continue

        # 2-byte sequences: party tokens, wait_key, or multi-byte glyphs
        if b >= 0xC0 and i + 1 < len(raw_bytes):
            two = raw_bytes[i : i + 2]
            if two in PARTY_CONTROL_TOKENS:
                res.append(PARTY_CONTROL_TOKENS[two])
                i += 2
                continue
            if two == b"\xC5\xBF":
                res.append("{WAIT_KEY}")
                i += 2
                continue
            b2 = raw_bytes[i + 1]
            if 0xC2 <= b <= 0xC8 and 0x80 <= b2 <= 0xBF:
                g_idx = bytes_to_glyph(b, b2)
                if g_idx in g2c:
                    res.append(g2c[g_idx])
                else:
                    res.append(f"{{GLYPH:{g_idx}}}")
                i += 2
                continue

        if b == 0:
            if font_type == "big":
                res.append("e")
            else:
                res.append("{NULL}")
            i += 1
        elif b == 2 and font_type == "big":
            res.append("{PAGE}")
            i += 1
        else:
            if b in g2c:
                res.append(g2c[b])
            else:
                res.append(f"{{TAG:{b:02X}}}")
            i += 1

    return "".join(res)


def detokenize_string(text: str, font_type: str = "big") -> bytes:
    """Converts a human-readable text string with control tags back into binary bytecode.

    Args:
        text: Human-readable text string with tags.
        font_type: 'big' for dialogue files, 'small' for system/menu files.

    Returns:
        Raw binary bytecode bytes.

    Raises:
        ValueError: If text contains unknown characters or malformed tags.
    """
    c2g = BIG_CHAR_TO_GLYPH if font_type == "big" else SMALL_CHAR_TO_GLYPH
    out = bytearray()
    i = 0

    while i < len(text):
        if text[i] == "{" and "}" in text[i:]:
            end_idx = text.find("}", i)
            tag = text[i : end_idx + 1]

            if tag in REV_PARTY_CONTROL_TOKENS:
                out.extend(REV_PARTY_CONTROL_TOKENS[tag])
                i = end_idx + 1
                continue
            elif tag == "{WAIT_KEY}":
                out.extend(b"\xC5\xBF")
                i = end_idx + 1
                continue
            elif tag.startswith("{EVENT_SYNC:") and len(tag) == 15:
                val = int(tag[12:14], 16)
                out.extend(bytes([0xC6, 0x95, val, 0xC6, 0x96]))
                i = end_idx + 1
                continue
            elif tag.startswith("{SOUND:") and len(tag) == 10:
                val = int(tag[7:9], 16)
                out.extend(bytes([0xC6, 0x97, val, 0xC6, 0x98]))
                i = end_idx + 1
                continue
            elif tag == "{PAGE}":
                out.append(2)
                i = end_idx + 1
                continue
            elif tag in ("{LINE}", "\n"):
                out.append(17 if font_type == "big" else 80)
                i = end_idx + 1
                continue
            elif tag == "{NULL}":
                out.append(0)
                i = end_idx + 1
                continue
            elif tag.startswith("{GLYPH:") and tag.endswith("}"):
                g_idx = int(tag[7:-1])
                out.extend(glyph_to_bytes(g_idx))
                i = end_idx + 1
                continue
            elif tag.startswith("{TAG:") and len(tag) == 8:
                val = int(tag[5:7], 16)
                out.append(val)
                i = end_idx + 1
                continue

        ch = text[i]
        if ch in c2g:
            g_idx = c2g[ch]
            out.extend(glyph_to_bytes(g_idx))
        else:
            raise ValueError(f"Unknown character {repr(ch)} in font '{font_type}'")
        i += 1

    return bytes(out)


def decode_char(byte_val: int, font_type: str = "big") -> str:
    """Decodes a single byte value into its character or tag representation."""
    return tokenize_bytes(bytes([byte_val]), font_type=font_type)


def encode_char(char: str, font_type: str = "big") -> bytes:
    """Encodes a single character into its byte value or sequence."""
    return detokenize_string(char, font_type=font_type)
