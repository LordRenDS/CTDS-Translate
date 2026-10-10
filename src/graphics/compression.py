"""Compression utilities for Chrono Trigger DS graphics formats.

Supports multi-layer Nintendo DS LZ10 stream compression, decompression,
and alignment padding.
"""

from __future__ import annotations

import ndspy.lz10

__all__ = [
    "compress_stream",
    "decompress_stream",
    "pad_to_alignment",
]


def decompress_stream(raw_bytes: bytes) -> tuple[bytes, int]:
    """Unwraps single- or multi-layer LZ10 compression until raw binary data is reached.

    Args:
        raw_bytes: Compressed or raw byte stream.

    Returns:
        tuple[bytes, int]: (unwrapped_bytes, layer_count)
    """
    current_data = raw_bytes
    layer_count = 0

    while len(current_data) >= 4 and current_data[0] == 0x10:
        # Check if already a valid header without decompression
        if len(current_data) >= 8 and current_data[:4] in (b"NCG\x00", b"NCL\x00", b"NSC\x00"):
            break

        try:
            decomp = ndspy.lz10.decompress(current_data)
            layer_count += 1
            current_data = decomp
        except Exception:
            # Not a valid LZ10 stream or corrupt, stop unwrapping
            break

    return current_data, layer_count


def compress_stream(data: bytes, layers: int = 1) -> bytes:
    """Applies `layers` passes of LZ10 compression to data.

    Args:
        data: Raw byte stream to compress.
        layers: Number of compression passes (defaults to 1).

    Returns:
        bytes: Compressed binary data.
    """
    result = data
    for _ in range(layers):
        result = ndspy.lz10.compress(result)
    return result


def pad_to_alignment(data: bytes, align: int = 4) -> bytes:
    """Pads byte buffer to specified alignment boundary with zeros.

    Args:
        data: Input byte buffer.
        align: Byte alignment boundary (default: 4).

    Returns:
        bytes: Padded byte buffer.
    """
    rem = len(data) % align
    if rem:
        data += b"\x00" * (align - rem)
    return data
