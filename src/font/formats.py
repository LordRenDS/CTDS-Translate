"""Binary 2bpp .fnt structures, constants, and packing/unpacking routines."""

from dataclasses import dataclass
import struct
from PIL import Image
from src.core.exceptions import FontError

FONT_MAGIC: bytes = b"FONT"
GRID_COLUMNS: int = 16

GRID_COLOR_CELL: int = 4   # (50, 80, 140) - Muted slate blue for cell boundaries
GRID_COLOR_WIDTH: int = 5  # (180, 70, 50) - Muted coral red for glyph width marker

# Standard 2bpp palette expanded with guide colors:
# 0: Transparent/Black (0,0,0)
# 1: Main font body/White (255,255,255)
# 2: Anti-aliasing/Light Gray (180,180,180)
# 3: Outline/Shadow/Dark Gray (90,90,90)
# 4: Cell border grid (50,80,140)
# 5: Glyph width boundary (180,70,50)
PALETTE_2BPP: list[int] = [
    0, 0, 0,
    255, 255, 255,
    180, 180, 180,
    90, 90, 90,
    50, 80, 140,
    180, 70, 50,
] + [0] * (256 * 3 - 18)

__all__ = [
    "FONT_MAGIC",
    "GRID_COLUMNS",
    "GRID_COLOR_CELL",
    "GRID_COLOR_WIDTH",
    "PALETTE_2BPP",
    "FntHeader",
    "find_offsets_start",
    "get_char_repr",
    "parse_fnt_header",
    "pack_fnt_binary",
    "sample_pixel_2bpp",
    "_find_offsets_start",
    "_get_char_repr",
    "_sample_pixel_2bpp",
]


@dataclass(slots=True)
class FntHeader:
    """Parsed header of a Chrono Trigger DS .fnt binary."""

    zeros: bytes
    magic: bytes
    default_width: int
    height_words: int
    glyph_count: int
    reserved: int
    cell_width: int
    cell_height: int
    char_map: list[int]
    offsets: list[int]
    offsets_start: int


def get_char_repr(char_code: int) -> str:
    """Returns a readable representation of a character bytecode index."""
    if char_code == 0x09:
        return "{TAB}"
    if 0x1F <= char_code <= 0x7D:
        return chr(char_code + 1)
    if 0x80 <= char_code <= 0x9F:
        return chr(0x0410 + (char_code - 0x80))
    if 0xA0 <= char_code <= 0xBF:
        return chr(0x0430 + (char_code - 0xA0))
    if char_code == 0xC0:
        return "Ё"
    if char_code == 0xC1:
        return "ё"
    return f"0x{char_code:02X}"


_get_char_repr = get_char_repr


def find_offsets_start(fnt_bytes: bytes, glyph_count: int) -> int:
    """Dynamically locates the start byte offset of the uint32 offset table."""
    table_size = glyph_count * 4
    for cand_start in range(14, len(fnt_bytes) - table_size + 1, 2):
        cand_offsets = struct.unpack(f"<{glyph_count}I", fnt_bytes[cand_start : cand_start + table_size])
        non_zeros = [o for o in cand_offsets if o > 0]
        if non_zeros and min(non_zeros) == cand_start + table_size:
            return cand_start
    return 0x10C


_find_offsets_start = find_offsets_start


def parse_fnt_header(fnt_bytes: bytes) -> FntHeader:
    """Parses and validates the header of a .fnt binary.

    Args:
        fnt_bytes: Raw binary content of .fnt file.

    Returns:
        FntHeader containing unpacked metadata, character map, and offsets.

    Raises:
        FontError: If binary is smaller than 14 bytes or magic is not 'FONT'.
    """
    if len(fnt_bytes) < 14:
        raise FontError("Invalid FNT binary: file size too small")

    zeros = fnt_bytes[:4]
    magic = fnt_bytes[4:8]
    if magic != FONT_MAGIC:
        raise FontError(f"Invalid FNT magic: expected {FONT_MAGIC!r}, got {magic!r}")

    def_w, height_words, glyph_count, reserved = struct.unpack("<BBHH", fnt_bytes[8:14])
    cell_h = def_w  # Glyph height equals default_width (10 for big, 8 for small)

    offsets_start = find_offsets_start(fnt_bytes, glyph_count)
    char_map_len = (offsets_start - 14) // 2
    char_map = list(struct.unpack(f"<{char_map_len}H", fnt_bytes[14 : 14 + char_map_len * 2]))
    offsets = list(struct.unpack(f"<{glyph_count}I", fnt_bytes[offsets_start : offsets_start + glyph_count * 4]))

    # Determine max bytes per row across glyphs to establish cell width
    max_bpr = max([fnt_bytes[off + 1] for off in offsets if off > 0] or [1])
    cell_w = max(def_w, max_bpr * 4)

    return FntHeader(
        zeros=zeros,
        magic=magic,
        default_width=def_w,
        height_words=height_words,
        glyph_count=glyph_count,
        reserved=reserved,
        cell_width=cell_w,
        cell_height=cell_h,
        char_map=char_map,
        offsets=offsets,
        offsets_start=offsets_start,
    )


def sample_pixel_2bpp(img: Image.Image, x: int, y: int) -> int:
    """Samples a single 2bpp pixel (0..3) from an image regardless of color mode.

    Grid guide lines (palette index >= 4 or colored RGB guide pixels) are automatically
    treated as background (0).
    """
    if x >= img.width or y >= img.height or x < 0 or y < 0:
        return 0

    mode = img.mode
    if mode == "P":
        val = img.getpixel((x, y))
        if val >= 4:
            return 0
        return val % 4
    if mode in ("RGBA", "RGB", "LA", "L"):
        px = img.getpixel((x, y))
        if mode == "RGBA":
            r, g, b, a = px
            if a < 32:
                return 0
            if max(r, g, b) - min(r, g, b) > 20:
                # Colored grid guide line (slate blue or coral red)
                return 0
            lum = int(0.299 * r + 0.587 * g + 0.114 * b)
        elif mode == "RGB":
            r, g, b = px
            if max(r, g, b) - min(r, g, b) > 20:
                # Colored grid guide line
                return 0
            lum = int(0.299 * r + 0.587 * g + 0.114 * b)
        elif mode == "LA":
            l, a = px
            if a < 32:
                return 0
            lum = l
        else:  # L
            lum = px

        if lum < 32:
            return 0
        if lum > 200:
            return 1
        if lum >= 130:
            return 2
        return 3

    return 0


_sample_pixel_2bpp = sample_pixel_2bpp


def pack_fnt_binary(
    default_width: int,
    height_words: int,
    glyph_count: int,
    char_map: list[int],
    glyphs: list[tuple[int, int, bytes] | None],
    reserved: int = 0,
    zeros: bytes = b"\x00\x00\x00\x00",
) -> bytes:
    """Packs header, character map, offset table, and glyph bitmap blocks into .fnt binary."""
    out = bytearray()
    out.extend(zeros)
    out.extend(FONT_MAGIC)
    out.extend(struct.pack("<BBHH", default_width, height_words, glyph_count, reserved))
    out.extend(struct.pack(f"<{len(char_map)}H", *char_map))

    offsets_start = len(out)
    out.extend(b"\x00" * (glyph_count * 4))

    offsets: list[int] = []
    for g_data in glyphs:
        if g_data is None:
            offsets.append(0)
        else:
            w, bpr, bm = g_data
            cur_off = len(out)
            offsets.append(cur_off)
            out.extend(struct.pack("<BB", w, bpr))
            out.extend(bm)

    out[offsets_start : offsets_start + glyph_count * 4] = struct.pack(f"<{glyph_count}I", *offsets)
    return bytes(out)
