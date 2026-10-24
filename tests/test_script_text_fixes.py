"""Tests verifying targeted script text fixes for Task 2.

Checks:
- Duplicate word removal in cmes0.json ID 137 ('день и ночь')
- Lucca female gender agreement in cmes0.json ID 42 ('Я была занята')
- Queen's handmaiden female gender agreement in mest4.json ID 20 ('Я-то ожидала')
- Natural dialogue phrasing in mest2.json ID 1 ('День... День Лавоса?!')
- Elimination of unicode ellipsis U+2026 in favor of '...' in cmes0.json
- Stat increase arrows using '↑' in item_sub.json (IDs 217, 231, 240, 241, 242)
"""

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_MSG_DIR = REPO_ROOT / "ai translated text" / "msg" / "big"


def load_json(filename: str):
    path = AI_MSG_DIR / filename
    assert path.is_file(), f"Target file not found: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_entry(data, entry_id: int):
    for item in data:
        if item.get("id") == entry_id:
            return item
    raise AssertionError(f"Entry with id {entry_id} not found")


class TestScriptTextFixes:
    """Test suite for targeted script translation corrections."""

    def test_cmes0_id_137_duplicate_removal(self):
        """Verify ID 137 in cmes0.json uses 'день и ночь' without duplicate 'день день'."""
        data = load_json("cmes0.json")
        entry = get_entry(data, 137)
        tr = entry.get("translation", "")
        assert "день и ночь" in tr, f"Expected 'день и ночь' in ID 137, got: {tr}"
        assert "день день" not in tr, f"Found duplicate 'день день' in ID 137: {tr}"

    def test_cmes0_id_42_lucca_female_gender(self):
        """Verify ID 42 in cmes0.json uses female gender agreement for Lucca."""
        data = load_json("cmes0.json")
        entry = get_entry(data, 42)
        tr = entry.get("translation", "")
        assert tr == "{LUCCA}: Я была занята своими исследованиями.", (
            f"Unexpected translation for ID 42: {tr}"
        )

    def test_cmes0_no_unicode_ellipsis(self):
        """Verify all occurrences of U+2026 ('…') in cmes0.json are replaced with '...'."""
        data = load_json("cmes0.json")
        failing_ids = [item["id"] for item in data if "…" in item.get("translation", "")]
        assert not failing_ids, f"Found unicode ellipsis (U+2026) in cmes0.json entries: {failing_ids}"

        # Explicitly verify the 6 targeted IDs
        for target_id in (26, 49, 140, 148, 177, 179):
            entry = get_entry(data, target_id)
            tr = entry.get("translation", "")
            assert "..." in tr, f"Expected '...' in ID {target_id}, got: {tr}"

    def test_mest4_id_20_handmaiden_female_gender(self):
        """Verify ID 20 in mest4.json uses female gender agreement ('Я-то ожидала')."""
        data = load_json("mest4.json")
        entry = get_entry(data, 20)
        tr = entry.get("translation", "")
        assert "Я-то ожидала" in tr, f"Expected 'Я-то ожидала' in ID 20, got: {tr}"
        assert "Я-то ожидал\n" not in tr, f"Found masculine 'Я-то ожидал' in ID 20: {tr}"

    def test_mest2_id_1_lavos_day_phrasing(self):
        """Verify ID 1 in mest2.json uses natural phrasing 'День... День Лавоса?!'."""
        data = load_json("mest2.json")
        entry = get_entry(data, 1)
        tr = entry.get("translation", "")
        assert tr == "{LUCCA}: Это же... это День... День Лавоса?!", (
            f"Unexpected translation for mest2 ID 1: {tr}"
        )

    def test_item_sub_stat_arrows(self):
        """Verify item_sub.json entries 217, 231, 240, 241, 242 use '↑' for stat increases."""
        data = load_json("item_sub.json")
        expected = {
            217: "Шанс кражи ↑",
            231: "Крит Масамунэ ↑",
            240: "Крит. удар ↑\nКонтратака: 50%",
            241: "Крит Масамунэ ↑\nРасход ОМ -50%",
            242: "Крит. удар ↑",
        }
        for item_id, expected_tr in expected.items():
            entry = get_entry(data, item_id)
            tr = entry.get("translation", "")
            assert "…" not in tr, f"Found ellipsis '…' in item_sub.json ID {item_id}: {tr}"
            assert "↑" in tr, f"Missing '↑' in item_sub.json ID {item_id}: {tr}"
            assert tr == expected_tr, (
                f"Mismatch in item_sub.json ID {item_id}: expected {repr(expected_tr)}, got {repr(tr)}"
            )

    def test_kmes0_id_44_dragon_tank_memo_layout(self):
        """Verify Dragon Tank memo in kmes0.json ID 44 has correct page structure."""
        data = load_json("kmes0.json")
        entry = get_entry(data, 44)
        tr = entry.get("translation", "")
        # Page 1 has blank line between header and addressee
        assert "{TAG:38}{TAG:38}{TAG:38}{TAG:38} Чертежи Дракона-танка\n\n{TAG:38}{TAG:7F}Начальнику тюрьмы замка Гардия" in tr
        # Signature is on its own page/line and does not overflow
        assert "Королевский арсенал Гардии" in tr

    def test_mesk1_id_76_button_mimic_table(self):
        """Verify dance button mimic table in mesk1.json ID 76 has 3 lines and proper layout."""
        data = load_json("mesk1.json")
        entry = get_entry(data, 76)
        tr = entry.get("translation", "")
        expected = (
            "Повторяйте движения!\n"
            "Кнопка L: Левая рука{TAG:38}{TAG:38}®Кнопка R: Правая рука\n"
            "Кнопка Y: Смех{TAG:38}{TAG:38}{TAG:38}{TAG:38}Кнопка A: Испуг"
        )
        assert tr == expected, f"Mismatch in mesk1 ID 76: expected {repr(expected)}, got {repr(tr)}"

    def test_cmes0_id_174_gates_terminology(self):
        """Verify Lucca's line in cmes0.json ID 174 uses «Вратами» instead of transliterated Гейтс."""
        data = load_json("cmes0.json")
        entry = get_entry(data, 174)
        tr = entry.get("translation", "")
        assert "«Вратами»" in tr, f"Expected «Вратами» in cmes0 ID 174, got: {tr}"
        assert "Гейтс" not in tr, f"Found banned transliteration 'Гейтс' in cmes0 ID 174: {tr}"

    def test_mest4_id_199_no_hanging_punctuation(self):
        """Verify mest4.json ID 199 has no hanging punctuation '?!' at start of line."""
        data = load_json("mest4.json")
        entry = get_entry(data, 199)
        tr = entry.get("translation", "")
        assert "\n?!" not in tr, f"Found hanging punctuation '\n?!' in mest4 ID 199: {tr}"
        assert "Кто бы мог подумать, что собор служил\nим логовом?! Какое святотатство!" == tr

    def test_mest0_id_63_69_no_broken_carry(self):
        """Verify mest0.json IDs 63 and 69 have clean wrap without broken hyphenated punctuation."""
        data = load_json("mest0.json")
        e63 = get_entry(data, 63)
        tr63 = e63.get("translation", "")
        assert "Лавоса-\n»" not in tr63
        assert tr63 == "{LUCCA}: 1999 год н. э.?\nВидеозапись «Дня Лавоса»..."

        e69 = get_entry(data, 69)
        tr69 = e69.get("translation", "")
        assert "погибнуть-\n?.." not in tr69
        assert tr69 == "{MARLE}: Неужели этому миру суждено\nтак погибнуть?..."

    def test_msg01_cmes5_v_etom_zale(self):
        """Verify 'В этом зале' is used instead of feminine 'В этой зале' in msg01 ID 22 and cmes5 ID 20."""
        data_msg01 = load_json("msg01.json")
        tr_frog = get_entry(data_msg01, 22).get("translation", "")
        assert "В этом зале" in tr_frog
        assert "В этой зале" not in tr_frog

        data_cmes5 = load_json("cmes5.json")
        tr_queen = get_entry(data_cmes5, 20).get("translation", "")
        assert "В этом зале" in tr_queen
        assert "В этой зале" not in tr_queen

    def test_mest4_id_117_king_guardia_rephrase(self):
        """Verify King Guardia in mest4 ID 117 uses 'Впрочем, не будем об этом' and polite plural address."""
        data = load_json("mest4.json")
        tr = get_entry(data, 117).get("translation", "")
        assert "Впрочем, не будем об этом." in tr
        assert "Вы оказали мне" in tr
        assert "Впрочем, пустое" not in tr
        assert "Ты оказала мне" not in tr

    def test_mest4_id_187_lucca_female_agreement(self):
        """Verify Lucca in mest4 ID 187 uses female past tense 'как я и думала'."""
        data = load_json("mest4.json")
        tr = get_entry(data, 187).get("translation", "")
        assert "как я и думала" in tr
        assert "как я и думал." not in tr

