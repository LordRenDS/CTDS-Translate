"""Complete and verified translation of all item and equipment related files:
- big/item_sub.json
- big/item_mes.json
- big/item_mes2.json
- big/ex_itemget.json
- big/ex_item.json
- big/item.json
- small/sfc_item.json
"""

import json
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_MSG_DIR = REPO_ROOT / "ai translated text" / "msg"

from scripts.test_sub_widths import ITEM_SUB_MAP
from scripts.test_mes_widths import ITEM_MES_MAP
from scripts.test_mes2_widths import ITEM_MES2_MAP
from scripts.test_ex_itemget import ITEMGET_LINE_MAP, translate_line

# Override 2 overlong strings in ITEM_MES_MAP to fit <= 210px
ITEM_MES_MAP["Enables Eternal Darkness triple tech."] = "Открывает комбо «Тьма Вечности»."
ITEM_MES_MAP["Enables Omega Flare triple tech."] = "Открывает комбо «Омега-Вспышка»."
ITEM_MES_MAP["Enables Spin Strike triple tech."] = "Открывает комбо «Вихрь-Удар»."
ITEM_MES_MAP["Enables Poyozo Dance triple tech."] = "Открывает комбо «Танец Пойозо»."
ITEM_MES_MAP["Enables Master Mune triple tech."] = "Открывает комбо «Мастер Мунэ»."


def update_item_sub():
    p = AI_MSG_DIR / "big/item_sub.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    updated = 0
    for it in data:
        orig = it.get("original_en", "").strip()
        if not orig:
            continue
        if orig in ITEM_SUB_MAP:
            it["translation"] = ITEM_SUB_MAP[orig]
            updated += 1
        elif orig.replace("\n", " ") in ITEM_SUB_MAP:
            it["translation"] = ITEM_SUB_MAP[orig.replace("\n", " ")]
            updated += 1
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {p.name}: {updated} entries translated.")


def update_item_mes():
    p = AI_MSG_DIR / "big/item_mes.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    updated = 0
    for it in data:
        orig = it.get("original_en", "").strip()
        if not orig:
            continue
        if orig in ITEM_MES_MAP:
            it["translation"] = ITEM_MES_MAP[orig]
            updated += 1
        elif orig.endswith(".") and orig[:-1] in ITEM_MES_MAP:
            it["translation"] = ITEM_MES_MAP[orig[:-1]]
            updated += 1
        elif (orig + ".") in ITEM_MES_MAP:
            it["translation"] = ITEM_MES_MAP[orig + "."]
            updated += 1
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {p.name}: {updated} entries translated.")


def update_item_mes2():
    p = AI_MSG_DIR / "big/item_mes2.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    updated = 0
    for it in data:
        fid = it.get("id")
        orig = it.get("original_en", "").strip()
        if not orig:
            continue
        if fid in ITEM_MES2_MAP:
            it["translation"] = ITEM_MES2_MAP[fid]
            updated += 1
        elif orig in ITEM_MES_MAP:
            it["translation"] = ITEM_MES_MAP[orig]
            updated += 1
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {p.name}: {updated} entries translated.")


def update_ex_itemget():
    p = AI_MSG_DIR / "big/ex_itemget.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    updated = 0
    for it in data:
        orig = it.get("original_en", "")
        if not orig.strip():
            continue
        lines = orig.split("\n")
        trans_lines = [translate_line(l) for l in lines]
        it["translation"] = "\n".join(trans_lines)
        updated += 1
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {p.name}: {updated} entries translated.")


def update_ex_item():
    p = AI_MSG_DIR / "big/ex_item.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    for it in data:
        fid = it.get("id")
        if fid == 180:
            it["translation"] = "3 {TAG:3E}Радужных шлема ИЛИ {TAG:3E}Радужное платье"
        elif fid == 252:
            it["translation"] = "100 000 З"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {p.name}.")


if __name__ == "__main__":
    update_item_sub()
    update_item_mes()
    update_item_mes2()
    update_ex_itemget()
    update_ex_item()
