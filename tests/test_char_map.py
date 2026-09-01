"""Unit tests for character mapping and control code tokenization (char_map.py)."""

import unittest
from src.char_map import (
    decode_char,
    encode_char,
    tokenize_bytes,
    detokenize_string,
    BIG_CHAR_TO_GLYPH,
    SMALL_CHAR_TO_GLYPH,
    glyph_to_bytes,
    bytes_to_glyph,
)


class TestCharMap(unittest.TestCase):
    """Test suite for character encoding tables and token engine."""

    def test_encode_decode_char_big_font(self):
        """Verify individual ASCII characters encode/decode correctly for big font."""
        # 'e' -> Glyph 0 -> 0x00
        self.assertEqual(encode_char("e", font_type="big"), b"\x00")
        self.assertEqual(decode_char(0x00, font_type="big"), "e")

        # Space ' ' -> Glyph 1 -> 0x01 (in single byte context)
        self.assertEqual(encode_char(" ", font_type="big"), b"\x01")

        # 'a' -> Glyph 3 -> 0x03
        self.assertEqual(encode_char("a", font_type="big"), b"\x03")
        self.assertEqual(decode_char(0x03, font_type="big"), "a")

        # 't' -> Glyph 4 -> 0x04
        self.assertEqual(encode_char("t", font_type="big"), b"\x04")
        self.assertEqual(decode_char(0x04, font_type="big"), "t")

    def test_encode_decode_char_small_font(self):
        """Verify individual ASCII characters encode/decode correctly for small font."""
        # 'e' -> Glyph 1 -> 0x01
        self.assertEqual(encode_char("e", font_type="small"), b"\x01")

        # 'a' -> Glyph 2 -> 0x02
        self.assertEqual(encode_char("a", font_type="small"), b"\x02")

        # Space ' ' -> Glyph 4 -> 0x04
        self.assertEqual(encode_char(" ", font_type="small"), b"\x04")

    def test_char_roundtrip_ascii(self):
        """Verify pure ASCII text roundtrips losslessly in both fonts."""
        sample_text = "Chrono Trigger: Awakening!"
        for font_type in ["big", "small"]:
            encoded = detokenize_string(sample_text, font_type=font_type)
            decoded = tokenize_bytes(encoded, font_type=font_type)
            self.assertEqual(decoded, sample_text)

    def test_control_tokens_roundtrip(self):
        """Verify dialogue text with control tokens and newlines roundtrips losslessly."""
        sample_text = "{CRONO}...\n{WAIT_KEY}\nAre you sleeping?"
        encoded = detokenize_string(sample_text, font_type="big")
        decoded = tokenize_bytes(encoded, font_type="big")
        self.assertEqual(decoded, sample_text)

    def test_party_control_tokens(self):
        """Verify all party member control tokens."""
        party_tokens = [
            ("{CRONO}", b"\xC5\xB7"),
            ("{MARLE}", b"\xC5\xB8"),
            ("{LUCCA}", b"\xC5\xB9"),
            ("{ROBO}", b"\xC5\xBA"),
            ("{FROG}", b"\xC5\xBB"),
            ("{AYLA}", b"\xC5\xBC"),
            ("{MAGUS}", b"\xC5\xBD"),
            ("{EPOCH}", b"\xC5\xBE"),
            ("{WAIT_KEY}", b"\xC5\xBF"),
        ]
        for token_str, expected_bytes in party_tokens:
            encoded = detokenize_string(token_str, font_type="big")
            self.assertEqual(encoded, expected_bytes)
            decoded = tokenize_bytes(encoded, font_type="big")
            self.assertEqual(decoded, token_str)

    def test_cyrillic_roundtrip(self):
        """Verify Cyrillic dialogue text roundtrips losslessly in both fonts."""
        sample_text = "Привет, Хроно! Проснись, соня! Ёжик в тумане."
        for font_type in ["big", "small"]:
            encoded = detokenize_string(sample_text, font_type=font_type)
            decoded = tokenize_bytes(encoded, font_type=font_type)
            self.assertEqual(decoded, sample_text)

    def test_complex_control_codes(self):
        """Verify complex tags like {EVENT_SYNC:0A} and {PAGE}."""
        sample_text = "{PAGE}{EVENT_SYNC:0A}{TAG:FE}"
        encoded = detokenize_string(sample_text, font_type="big")
        self.assertEqual(encoded, b"\x02\xC6\x95\x0A\xC6\x96\xFE")
        decoded = tokenize_bytes(encoded, font_type="big")
        self.assertEqual(decoded, sample_text)

    def test_french_accents_roundtrip(self):
        """Verify French accented characters roundtrip losslessly."""
        sample_text = "Désolé de vous avoir fait attendre ! À bientôt !"
        for font_type in ["big", "small"]:
            encoded = detokenize_string(sample_text, font_type=font_type)
            decoded = tokenize_bytes(encoded, font_type=font_type)
            self.assertEqual(decoded, sample_text)

    def test_european_accents_and_symbols_roundtrip(self):
        """Verify Spanish, German, Italian accented characters and symbols roundtrip losslessly."""
        sample_big = "ÀÁÂÇÈÉÊŒÌÍÎÏÑÒÓÔßÙÚÛÜàáâäçèéêëœîïñòóôöùú—«»…¡¿°™©®♀♂♪"
        encoded_big = detokenize_string(sample_big, font_type="big")
        decoded_big = tokenize_bytes(encoded_big, font_type="big")
        self.assertEqual(decoded_big, sample_big)

        sample_small = "éèàêçîôùû—œ«»ëïüÉÈÀÊÇÎÔÙÛŒËÏÜ…¡¿°™©®♀♂♪★Ñßñ"
        encoded_small = detokenize_string(sample_small, font_type="small")
        decoded_small = tokenize_bytes(encoded_small, font_type="small")
        self.assertEqual(decoded_small, sample_small)

    def test_invalid_character_handling(self):
        """Verify unmapped characters raise appropriate exceptions during encoding."""
        with self.assertRaises(ValueError):
            encode_char("€", font_type="big")


if __name__ == "__main__":
    unittest.main()
