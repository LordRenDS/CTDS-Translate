"""Fixes tag parity and missing translations in dialogue files."""

from __future__ import annotations
import json
from pathlib import Path

def apply_fixes(base_dir: Path):
    # 1. cmes0.json
    cmes0_path = base_dir / "msg/big/cmes0.json"
    if cmes0_path.exists():
        with open(cmes0_path, "r", encoding="utf-8") as f:
            d = json.load(f)

        # Missing translations
        d[22]["translation"] = "{AYLA}: ...{WAIT_KEY}\n{GLYPH:392}... ладно."
        d[29]["translation"] = "{LUCCA}: Мы бы хотели одолжить эту куклу ненадолго."
        d[53]["translation"] = "Мама: Батюшки! А ты ещё кто?"
        d[166]["translation"] = "{MARLE}: Пожалуйста, зовите меня просто {MARLE}!"

        # Tag mismatches
        d[7]["translation"] = (
            "Мама: Ах, батюшки! Я и забыла, как прекрасно\n"
            "звучит Колокол Лине!{GLYPH:405}0a{GLYPH:406}"
        )
        d[18]["translation"] = (
            "{MARLE}: Он... он замечательный.{WAIT_KEY}\n"
            "Л-лучше не бывает."
        )
        d[159]["translation"] = (
            "Как раз когда я завершал работу над Колоколом Лине,\n"
            "наш Король был ранен мистиками {MAGUS}.\n"
            "После такого опускаются руки."
        )
        d[165]["translation"] = "{LUCCA}: Что ж, Ваше Высочество, мы—"
        d[167]["translation"] = "{LUCCA}: Что ж, тогда смотри, {MARLE}..."
        d[171]["translation"] = "{LUCCA}: П-простите, мне следовало быть скромнее перед—"
        d[172]["translation"] = (
            "{MARLE}: Да хватит уже! Ну принцесса я, и что с того?\n"
            "Я ведь ничего особенного не умею.{WAIT_KEY}\n"
            "А вот ты — невероятная!\n"
            "Я бы не задумываясь променяла свой титул на твой гений!"
        )
        d[173]["translation"] = "{LUCCA}: Ну, раз ты так говоришь..."
        d[180]["translation"] = (
            "{MARLE}: Всё это звучит как-то слишком сложно.\n"
            "Может, вернёмся пока в наше время?"
        )

        with open(cmes0_path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"Updated {cmes0_path}")

    # 2. cmes3.json
    cmes3_path = base_dir / "msg/big/cmes3.json"
    if cmes3_path.exists():
        with open(cmes3_path, "r", encoding="utf-8") as f:
            d = json.load(f)
        d[182]["translation"] = (
            "Гуру Жизни доверил мне этот росток, но боюсь,\n"
            "в этом гиблом мире ему не выжить.{WAIT_KEY}"
            "Что мне делать?\n"
            "{TAG:38}{TAG:38}{GLYPH:394}Сжечь,{GLYPH:402} {GLYPH:403}из жалости.{GLYPH:395}\n"
            "{TAG:38}{TAG:38}{GLYPH:396}Посадить с надеждой.{GLYPH:397}"
        )
        with open(cmes3_path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"Updated {cmes3_path}")

    # 3. comu0.json
    comu0_path = base_dir / "msg/big/comu0.json"
    if comu0_path.exists():
        with open(comu0_path, "r", encoding="utf-8") as f:
            d = json.load(f)
        d[26]["translation"] = (
            "Распорядитель: Какую битву выберете?\n"
            "{TAG:38}{TAG:38}{GLYPH:394}Призовой бой.{GLYPH:395}\n"
            "{TAG:38}{TAG:38}{GLYPH:396}Битва эпох.{GLYPH:402} {GLYPH:403}(Связь){GLYPH:397}\n"
            "{TAG:38}{TAG:38}{GLYPH:398}Отмена.{GLYPH:399}"
        )
        with open(comu0_path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"Updated {comu0_path}")

    # 4. mest0.json
    mest0_path = base_dir / "msg/big/mest0.json"
    if mest0_path.exists():
        with open(mest0_path, "r", encoding="utf-8") as f:
            d = json.load(f)
        d[255]["translation"] = (
            "Отправиться на Арену Веков,\n"
            "за пределы потока времени?\n"
            "®®{GLYPH:394}Да.{GLYPH:395}\n"
            "®®{GLYPH:396}Нет.{GLYPH:397}"
        )
        with open(mest0_path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"Updated {mest0_path}")

    # 5. mest1.json
    mest1_path = base_dir / "msg/big/mest1.json"
    if mest1_path.exists():
        with open(mest1_path, "r", encoding="utf-8") as f:
            d = json.load(f)
        d[165]["translation"] = (
            "Спеккио: Приветик, дорогуша!{WAIT_KEY}\n"
            "Увы, ты родилась задолго до появления магии,\n"
            "так что заклинания тебе не светят. Но не грусти:\n"
            "у тебя и без магии масса достоинств. Кхм."
        )
        d[171]["translation"] = (
            "{GLYPH:384} Фирменный набор от Спеккио!{WAIT_KEY}{GLYPH:384}\n\n"
            "Получена 1 Магическая капсула и 5 Средних эфиров!"
        )
        d[172]["translation"] = (
            "{GLYPH:384} Оздоровительный набор от Спеккио!{WAIT_KEY}{GLYPH:384}\n\n"
            "Получена 1 Магическая капсула и 5 Высших эфиров!"
        )
        d[173]["translation"] = (
            "{GLYPH:384} Набор благодарности от Спеккио!{WAIT_KEY}{GLYPH:384}\n\n"
            "Получено: Капсула магии, Капсула скорости,\n"
            "Капсула силы и 10 Эликсиров!"
        )
        d[174]["translation"] = (
            "{GLYPH:384} Набор восторга и ликования от Спеккио!{WAIT_KEY}{GLYPH:384}\n\n"
            "Получено по 10 Капсул магии, скорости и силы,\n"
            "а также 10 Мегаэликсиров!{WAIT_KEY}{GLYPH:384}\n\n"
            "Похвалы от Спеккио получено столько,\n"
            "что хватит на целый год вперёд!"
        )
        with open(mest1_path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"Updated {mest1_path}")

    # 6. mest3.json
    mest3_path = base_dir / "msg/big/mest3.json"
    if mest3_path.exists():
        with open(mest3_path, "r", encoding="utf-8") as f:
            d = json.load(f)
        d[99]["translation"] = (
            "{ROBO}: Мы оставим остальные вещи позади?\n"
            "®®{GLYPH:394}Не имеет значения.{GLYPH:395}\n"
            "®®{GLYPH:396}Вернуться.{GLYPH:397}"
        )
        with open(mest3_path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"Updated {mest3_path}")

    # 7. mest4.json
    mest4_path = base_dir / "msg/big/mest4.json"
    if mest4_path.exists():
        with open(mest4_path, "r", encoding="utf-8") as f:
            d = json.load(f)
        d[36]["translation"] = (
            "Кстати говоря, вам не показалось, что\n"
            "Её Величество сама не своя?\n"
            "{TAG:38}{TAG:38}{GLYPH:394}Да.{GLYPH:395}\n"
            "{TAG:38}{TAG:38}{GLYPH:396}Нет.{GLYPH:397}"
        )
        d[110]["translation"] = (
            "{MARLE}: Ты ведь не стал бы гулять со мной\n"
            "по ярмарке, правда, {CRONO}?\n"
            "{TAG:38}{TAG:38}{GLYPH:394}Вряд ли.{GLYPH:395}\n"
            "{TAG:38}{TAG:38}{GLYPH:396}Всё равно стал бы.{GLYPH:397}"
        )
        with open(mest4_path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"Updated {mest4_path}")

def main():
    apply_fixes(Path("ai translated text"))
    apply_fixes(Path("translated text"))

if __name__ == "__main__":
    main()
