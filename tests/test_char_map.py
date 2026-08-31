"""Unit tests for character mapping and control code tokenization (char_map.py)."""

import unittest
from src.char_map import (
    decode_char,
    encode_char,
    tokenize_bytes,
    detokenize_string,
    CHAR_TO_BYTE,
    BYTE_TO_CHAR,
)


class TestCharMap(unittest.TestCase):
    """Test suite for character encoding tables and token engine."""

    def test_encode_decode_char_ascii(self):
        """Verify individual ASCII characters encode/decode correctly with shift."""
        # Space (0x20) -> 0x1F
        self.assertEqual(encode_char(" "), 0x1F)
        self.assertEqual(decode_char(0x1F), " ")

        # '!' (0x21) -> 0x20
        self.assertEqual(encode_char("!"), 0x20)
        self.assertEqual(decode_char(0x20), "!")

        # 'e' (0x65) -> 0x64
        self.assertEqual(encode_char("e"), 0x64)
        self.assertEqual(decode_char(0x64), "e")

        # Tab '\t' (0x09) -> 0x09
        self.assertEqual(encode_char("\t"), 0x09)
        self.assertEqual(decode_char(0x09), "\t")

    def test_encode_decode_char_cyrillic(self):
        """Verify Russian Cyrillic uppercase, lowercase, and Ё/ё mapping."""
        # Uppercase 'А' -> 0x80, 'Я' -> 0x9F
        self.assertEqual(encode_char("А"), 0x80)
        self.assertEqual(decode_char(0x80), "А")
        self.assertEqual(encode_char("Я"), 0x9F)
        self.assertEqual(decode_char(0x9F), "Я")

        # Lowercase 'а' -> 0xA0, 'я' -> 0xBF
        self.assertEqual(encode_char("а"), 0xA0)
        self.assertEqual(decode_char(0xA0), "а")
        self.assertEqual(encode_char("я"), 0xBF)
        self.assertEqual(decode_char(0xBF), "я")

        # 'Ё' -> 0xC0, 'ё' -> 0xC1
        self.assertEqual(encode_char("Ё"), 0xC0)
        self.assertEqual(decode_char(0xC0), "Ё")
        self.assertEqual(encode_char("ё"), 0xC1)
        self.assertEqual(decode_char(0xC1), "ё")

    def test_char_roundtrip_ascii(self):
        """Verify pure ASCII text roundtrips losslessly."""
        sample_text = "Chrono Trigger: Awakening!"
        encoded = detokenize_string(sample_text)
        decoded = tokenize_bytes(encoded)
        self.assertEqual(decoded, sample_text)

    def test_control_tokens_roundtrip(self):
        """Verify dialogue text with control tokens and newlines roundtrips losslessly."""
        sample_text = "{CRONO}...\n{WAIT_KEY}\nAre you sleeping?"
        encoded = detokenize_string(sample_text)
        decoded = tokenize_bytes(encoded)
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
            encoded = detokenize_string(token_str)
            self.assertEqual(encoded, expected_bytes)
            decoded = tokenize_bytes(encoded)
            self.assertEqual(decoded, token_str)

    def test_cyrillic_roundtrip(self):
        """Verify Cyrillic dialogue text roundtrips losslessly."""
        sample_text = "Привет, Хроно! Проснись, соня!"
        encoded = detokenize_string(sample_text)
        decoded = tokenize_bytes(encoded)
        self.assertEqual(decoded, sample_text)

    def test_complex_control_codes(self):
        """Verify complex tags like {EVENT_SYNC:0A} and unknown {TAG:C5}."""
        sample_text = "{PAGE}{EVENT_SYNC:0A}{TAG:C5}{NULL}"
        encoded = detokenize_string(sample_text)
        self.assertEqual(encoded, b"\x02\xC6\x95\x0A\xC6\x96\xC5\x00")
        decoded = tokenize_bytes(encoded)
        self.assertEqual(decoded, sample_text)

    def test_multibyte_event_sync(self):
        """Verify multi-byte event sync payloads roundtrip."""
        sample_text = "{EVENT_SYNC:3900}{EVENT_SYNC:3F4C}"
        encoded = detokenize_string(sample_text)
        self.assertEqual(encoded, b"\xC6\x95\x39\x00\xC6\x96\xC6\x95\x3F\x4C\xC6\x96")
        decoded = tokenize_bytes(encoded)
        self.assertEqual(decoded, sample_text)

    def test_line_tag_and_newline_compatibility(self):
        """Verify both {LINE} and \n detokenize to 0x01."""
        self.assertEqual(detokenize_string("{LINE}"), b"\x01")
        self.assertEqual(detokenize_string("\n"), b"\x01")
        self.assertEqual(detokenize_string("\r\n"), b"\x01")

    def test_invalid_character_handling(self):
        """Verify unmapped characters raise appropriate exceptions during encoding."""
        with self.assertRaises(ValueError):
            encode_char("€")

        with self.assertRaises(ValueError):
            decode_char(0xFE)


if __name__ == "__main__":
    unittest.main()
