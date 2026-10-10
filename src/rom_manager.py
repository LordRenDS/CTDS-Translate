"""Backward-compatible facade for src.rom."""

from src.rom import (
    build_rom,
    get_nitrofs_paths,
    unpack_rom,
    verify_rom_integrity,
)

__all__ = [
    "build_rom",
    "get_nitrofs_paths",
    "unpack_rom",
    "verify_rom_integrity",
]
