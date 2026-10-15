"""Translates all monster and bestiary related files:
- big/monster.json
- small/sfc_mon.json
- big/ex_mon.json
- big/ex_monspot.json
- big/ex_montec.json
- big/wireless_mon.json
- big/wireless_mon2.json
- big/mon_tec.json
- big/wireless_tec.json
"""

import json
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_MSG_DIR = REPO_ROOT / "ai translated text" / "msg"

MONSTER_NAMES = {
    "Nu": "Ню",
    "Reptite": "Рептит",
    "Terasaur": "Теразавр",
    "Kilwala": "Килвала",
    "Krawlie": "Краули",
    "Underling": "Прислужник",
    "Omicrone": "Омикрон",
    "Martello": "Мартелло",
    "Bellbird": "Звонарь",
    "Panel": "Панель",
    "Mammon Machine": "Машина Маммона",
    "Empty": "Пустота",
    "Blue Imp": "Синий чёрт",
    "Green Imp": "Зелёный чёрт",
    "Stone Imp": "Каменный чёрт",
    "Mud Imp": "Грязевой чёрт",
    "Roundillo": "Раундилло",
    "Fiendillo": "Фиендилло",
    "Boundillo": "Баундилло",
    "Roundillo Rider": "Всадник",
    "Blue Eaglet": "Синий орёл",
    "Golden Eaglet": "Золотой орёл",
    "Red Eaglet": "Красный орёл",
    "Gilded Bellbird": "Злат. звонарь",
    "Imp Hawk": "Чёртокрыл",
    "Bomber Bird": "Бомбардир",
    "Viper": "Гадюка",
    "Fangtooth": "Клыкач",
    "Naga": "Нага",
    "Hydraconda": "Гидраконда",
    "Ruin Stalker": "Охотник руин",
    "Cave Stalker": "Пещерн. ловец",
    "White Horror": "Белый ужас",
    "Queen Zeal": "Королева Зил",
    "Rafflesia": "Раффлезия",
    "Floral Horror": "Цвет. ужас",
    "Death Lily": "Лилия смерти",
    "Blood Yolk": "Кровав. желток",
    "Egg Ooze": "Яйцо слизи",
    "Fallen": "Падший",
    "Skeleton": "Скелет",
    "Lancer": "Копейщик",
    "Macabre": "Макабр",
    "Flesh Reaper": "Жнец плоти",
    "Royal Guard": "Страж короля",
    "Ghost Knight": "Рыцарь-призрак",
    "Freelancer": "Наёмник",
    "Outlaw": "Разбойник",
    "Giga Mutant": "Гига-мутант",
    "Tera Mutant": "Тера-мутант",
    "Juggler": "Жонглёр",
    "Melphyx": "Мелфикс",
    "Zealot Mage": "Фанатик",
    "Sentry": "Часовой",
    "Shieldsman": "Щитоносец",
    "Watcher": "Страж",
    "Nomad": "Кочевник",
    "Djinn Bottle": "Кувшин джинна",
    "Aecyto Weevil": "Долгоносик",
    "Acid": "Кислота",
    "Aecytonyx": "Аэцитоникс",
    "Aecytosaur": "Аэцитозавр",
    "Alabaster Shade": "Белая тень",
    "Alkali": "Щёлочь",
    "Amanita": "Мухомор",
    "Archaeofang": "Археоклык",
    "Arm": "Рука",
    "Atropos XR": "Атропа XR",
    "Avian Rex": "Птицезавр",
    "Ayla Statue": "Статуя Эйлы",
    "Azala": "Азала",
    "Bao Bao": "Бао-Бао",
    "Black Bat": "Чёрная мышь",
    "Black Tyranno": "Чёрн. Тиранно",
    "Bladesman": "Мечник",
    "Blubber Hulk": "Жировик",
    "Blue Gargoyle": "Синяя горгулья",
    "Blue Mudbeast": "Грязезверь",
    "Blue Scouter": "Синий скаут",
    "Bone Knight": "Костяной рыцарь",
    "Bug": "Жук",
    "Bullfrog": "Жаба-бык",
    "Byte": "Байт",
    "Cave Ape": "Пещерн. обезьяна",
    "Cave Bat": "Пещерная мышь",
    "Chaos Mage": "Маг хаоса",
    "Chrysosaur": "Хризозавр",
    "Crater": "Кратер",
    "Crested Fire": "Гребнистый",
    "Crono Statue": "Статуя Кроно",
    "Cursed Husk": "Проклятый",
    "Dalton": "Дальтон",
    "Dalton Plus": "Дальтон Плюс",
    "Deathguard": "Страж смерти",
    "Decedent": "Усопший",
    "Defunct": "Мертвец",
    "Demon Spirit": "Дух демона",
    "Departed": "Ушедший",
    "Diablos": "Диаблос",
    "Display": "Дисплей",
    "Divining Root": "Вещий корень",
    "Dragon Tank": "Дракон-танк",
    "Edger": "Острокрыл",
    "Elder": "Старейшина",
    "Elder Lavos Spawn": "Порождение",
    "Exile": "Изгнанник",
    "Flea": "Фли",
    "Flea Plus": "Фли Плюс",
    "Fossil Ape": "Ископаемое",
    "Frog Statue": "Статуя Фрога",
    "Gargoyle": "Горгулья",
    "Garuda": "Гаруда",
    "Gato": "Гато",
    "Ghost": "Призрак",
    "Gigosaur": "Гигозавр",
    "Gold-Eater": "Золотоед",
    "Golem": "Голем",
    "Golem Boss": "Босс Голем",
    "Grain Pilot": "Пилот",
    "Grimalkin": "Грималкин",
    "Guard": "Охранник",
    "Guardian": "Страж",
    "Gunret": "Турель",
    "Heckran": "Хекран",
    "Hench": "Головорез",
    "Hexapod": "Шестиног",
    "Ion": "Ион",
    "Iron Maiden": "Дева",
    "Laser Guard": "Лазер-страж",
    "Lavos": "Лавос",
    "Lavos Spawn": "Порождение",
    "Lucca Statue": "Статуя Лукки",
    "Magus": "Магус",
    "Meat Eater": "Мясоед",
    "Mega Mutant": "Мега-мутант",
    "Megasaur": "Мегазавр",
    "Mizuno": "Мидзуно",
    "Mohavor": "Мохавор",
    "Mother Brain": "Мать-Мозг",
    "Nizbel": "Низбель",
    "Nizbel II": "Низбель II",
    "Nu Master": "Мастер Ню",
    "Octoblush": "Осьминог",
    "Octopod": "Осьминог",
    "Ogan": "Оган",
    "Ozzie": "Оззи",
    "Proto 2": "Прото 2",
    "Proto 3": "Прото 3",
    "Proto 4": "Прото 4",
    "Reaper": "Жнец",
    "Red Mudbeast": "Грязезверь",
    "Red Scout": "Красный скаут",
    "R-Series": "Серия R",
    "Rust Tyranno": "Ржав. Тиранно",
    "Scouter": "Скаут",
    "Shadow": "Тень",
    "Slash": "Слэш",
    "Son of Sun": "Сын Солнца",
    "Sorcerer": "Колдун",
    "Spekkio": "Спеккио",
    "Super Slash": "Супер Слэш",
    "Synchrite": "Синхрит",
    "Turret": "Турель",
    "Volcano": "Вулкан",
    "Yakra": "Якра",
    "Yakra XIII": "Якра XIII",
    "Zombor": "Зомбор",
    "???": "???",
}

EXTRA_MONSTER_NAMES = {
    "Archaeofang (Elder)": "Археоклык (Старш.)",
    "Archaeofang (Younger)": "Археоклык (Младш.)",
    "Attack Arm": "Ударная рука",
    "Center Pod": "Центр. кокон",
    "Defense Arm": "Защитная рука",
    "Dragon Tank (Body)": "Дракон-танк (Тело)",
    "Dragon Tank (Head)": "Дракон-танк (Голова)",
    "Dragon Tank (Wheel)": "Дракон-танк (Колёса)",
    "Elder Lavos Spawn (Mouth)": "Порождение (Пасть)",
    "Elder Lavos Spawn (Shell)": "Порождение (Панцирь)",
    "Fallen + Soul": "Падший + Душа",
    "Giga Mutant (Lower Body)": "Гига-мутант (Низ)",
    "Giga Mutant (Upper Body)": "Гига-мутант (Верх)",
    "Lavos (Body)": "Лавос (Тело)",
    "Lavos (Left Hand)": "Лавос (Лев. рука)",
    "Lavos (Right Hand)": "Лавос (Прав. рука)",
    "Lavos Pod": "Кокон Лавоса",
    "Lavos Spawn (Mouth)": "Порождение (Пасть)",
    "Lavos Spawn (Shell)": "Порождение (Панцирь)",
    "Mega Mutant (Lower Body)": "Мега-мутант (Низ)",
    "Mega Mutant (Upper Body)": "Мега-мутант (Верх)",
    "Melphyx (Core)": "Мелфикс (Ядро)",
    "Melphyx (Lower Body)": "Мелфикс (Низ)",
    "Melphyx (Upper Body)": "Мелфикс (Верх)",
    "Ogan (Hammer)": "Оган (Молот)",
    "Ogan Youth (Hammer)": "Оган-юнга (Молот)",
    "Queen Zeal (Face)": "Королева Зил (Лик)",
    "Queen Zeal (Left Hand)": "Королева Зил (Лев.)",
    "Queen Zeal (Right Hand)": "Королева Зил (Прав.)",
    "Reptite (Green)": "Рептит (Зелёный)",
    "Reptite (Purple)": "Рептит (Фиолет.)",
    "Save Point": "Точка сохр.",
    "Servant (Crossbow)": "Слуга (Арбалет)",
    "Servant (Sword)": "Слуга (Меч)",
    "Slash (Sword)": "Слэш (Меч)",
    "Slash (Unarmed)": "Слэш (Без оружия)",
    "Tera Mutant (Lower Body)": "Тера-мутант (Низ)",
    "Tera Mutant (Upper Body)": "Тера-мутант (Верх)",
    "Underling (Blue)": "Прислужник (Син.)",
    "Underling (Purple)": "Прислужник (Фиол.)",
    "Zombor (Lower Body)": "Зомбор (Низ)",
    "Zombor (Upper Body)": "Зомбор (Верх)",
    "{MAGUS}": "{MAGUS}",
}

MON_TEC_COMMON = {
    "Charge": "Разгон",
    "Gore": "Бодание",
    "Strike": "Удар",
    "Scratch": "Царапание",
    "Spin Attack": "Вращение",
    "Punch": "Удар кулаком",
    "Whirling Blade": "Вихрь клинка",
    "Tackle": "Толчок",
    "Jab": "Тычок",
    "Smash": "Сокрушение",
    "Wing Flap": "Взмах крыльев",
    "Bite": "Укус",
    "Barrage": "Шквал",
    "Crushing Blow": "Дробящий удар",
    "Multi-punch": "Серия ударов",
    "Punching Glove": "Боксёрская перчатка",
    "Gato's Song of Love": "Песенка любви Гато",
    "Ding-a-ling / Confuse": "Динь-дон / Смятение",
    "Laser Spin": "Лазерный вихрь",
    "Iron Orb": "Железная сфера",
    "Delta Force": "Дельта-сила",
    "Fire Breath": "Огненное дыхание",
    "Ice Breath": "Ледяное дыхание",
    "Thunder Breath": "Дыхание грома",
    "Dark Energy": "Тёмная энергия",
    "Flame Thrower": "Огнемёт",
    "Laser": "Лазер",
    "Missile": "Ракета",
    "Needle Spin": "Вихрь игл",
    "Sand Spray": "Песчаный залп",
    "Slime": "Слизь",
    "Sonic Wave": "Звуковая волна",
    "Tail Whip": "Удар хвостом",
    "Tornado": "Торнадо",
    "Water Cannon": "Водомёт",
    "Hypno Wave": "Гипно-волна",
    "Poison Gas": "Ядовитый газ",
    "Sleep Gas": "Усыпляющий газ",
    "Chaos Gas": "Газ хаоса",
    "Stop Gas": "Паралич-газ",
    "Earthquake": "Землетрясение",
    "Blizzard": "Буран",
    "Flare": "Вспышка",
    "Dark Matter": "Тёмная материя",
    "Luminaire": "Люминар",
    "Life": "Жизнь",
    "Cure": "Лечение",
    "Heal": "Исцеление",
    "Lock": "Блок",
    "Drain": "Поглощение",
    "Absorb": "Впитывание",
    "Counter": "Контратака",
    "Terrifying Voice": "Жуткий зов",
}


def translate_monsters():
    # 1. big/monster.json
    p_mon = AI_MSG_DIR / "big/monster.json"
    with open(p_mon, "r", encoding="utf-8") as f:
        mon_data = json.load(f)

    for item in mon_data:
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        if item.get("translation", "").strip():
            continue
        if orig in MONSTER_NAMES:
            item["translation"] = MONSTER_NAMES[orig]
        elif orig in EXTRA_MONSTER_NAMES:
            item["translation"] = EXTRA_MONSTER_NAMES[orig]
        else:
            item["translation"] = orig

    with open(p_mon, "w", encoding="utf-8") as f:
        json.dump(mon_data, f, ensure_ascii=False, indent=2)
    print("Updated big/monster.json")

    # 2. small/sfc_mon.json
    p_sfc = AI_MSG_DIR / "small/sfc_mon.json"
    with open(p_sfc, "r", encoding="utf-8") as f:
        sfc_data = json.load(f)

    for i, item in enumerate(sfc_data):
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        if i == 205:
            item["translation"] = "Лавос"
        elif i < len(mon_data) and mon_data[i].get("translation"):
            item["translation"] = mon_data[i]["translation"]
        elif orig in MONSTER_NAMES:
            item["translation"] = MONSTER_NAMES[orig]
        else:
            item["translation"] = orig

    with open(p_sfc, "w", encoding="utf-8") as f:
        json.dump(sfc_data, f, ensure_ascii=False, indent=2)
    print("Updated small/sfc_mon.json")

    # 3. big/ex_mon.json
    p_ex = AI_MSG_DIR / "big/ex_mon.json"
    with open(p_ex, "r", encoding="utf-8") as f:
        ex_data = json.load(f)

    for item in ex_data:
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        if item.get("translation", "").strip():
            continue
        if orig in EXTRA_MONSTER_NAMES:
            item["translation"] = EXTRA_MONSTER_NAMES[orig]
        elif orig in MONSTER_NAMES:
            item["translation"] = MONSTER_NAMES[orig]
        else:
            item["translation"] = orig

    with open(p_ex, "w", encoding="utf-8") as f:
        json.dump(ex_data, f, ensure_ascii=False, indent=2)
    print("Updated big/ex_mon.json")

    # 4. big/wireless_mon.json & big/wireless_mon2.json
    p_w1 = AI_MSG_DIR / "big/wireless_mon.json"
    p_w2 = AI_MSG_DIR / "big/wireless_mon2.json"
    with open(p_w1, "r", encoding="utf-8") as f:
        w1_data = json.load(f)
    with open(p_w2, "r", encoding="utf-8") as f:
        w2_data = json.load(f)

    w_names = {
        "Flame Smidge": "Огненная кроха",
        "Water Smidge": "Водная кроха",
        "Light Smidge": "Светлая кроха",
        "Shadow Smidge": "Тёмная кроха",
        "Hercules Beetle": "Жук-геркулес",
        "Rhino Weevil": "Долгоносик",
        "Holy Knight": "Святой рыцарь",
        "Royal Guard": "Страж короля",
        "Naga": "Нага",
        "Bladesman": "Мечник",
    }

    for item in w1_data:
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        if orig in w_names:
            item["translation"] = w_names[orig]
        elif orig in MONSTER_NAMES:
            item["translation"] = MONSTER_NAMES[orig]
        else:
            item["translation"] = orig

    for item in w2_data:
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        cap = orig.title()
        if cap in w_names:
            item["translation"] = w_names[cap].lower()
        elif cap in MONSTER_NAMES:
            item["translation"] = MONSTER_NAMES[cap].lower()
        else:
            item["translation"] = orig.lower()

    with open(p_w1, "w", encoding="utf-8") as f:
        json.dump(w1_data, f, ensure_ascii=False, indent=2)
    with open(p_w2, "w", encoding="utf-8") as f:
        json.dump(w2_data, f, ensure_ascii=False, indent=2)
    print("Updated wireless_mon.json & wireless_mon2.json")


def translate_mon_techs():
    # 5. big/mon_tec.json & big/wireless_tec.json
    p_tec = AI_MSG_DIR / "big/mon_tec.json"
    with open(p_tec, "r", encoding="utf-8") as f:
        tec_data = json.load(f)

    tec_replacements = {
        "Head repairs damage.": "Голова устраняет повреждения.",
        "Wheels storing energy for a charge.": "Колёса копят энергию для разгона.",
        "Too far to counterattack.": "Слишком далеко для контратаки.",
        "Too close to counterattack.": "Слишком близко для контратаки.",
        "Crushing Blow": "Сокрушительный удар",
        "Needle Spin: Yakra's needle-launching attack": "Вихрь игл: игольная атака Якры",
        "Nagamour: Slow": "Чары наги: Замедление",
        "Ding-a-ling: Confuse": "Динь-дон: Смятение",
        "Grraaagh!": "Гр-р-ра-а!",
        "Attacking detected motion source.": "Атака обнаруженного движения.",
        "I'll mash you to goo!": "Размажу вас в лепёшку!",
        "Breakdown": "Поломка",
        "Amplifier": "Усилитель",
        "Ozzie's spell is broken.": "Заклятие Оззи рассеяно.",
    }

    for item in tec_data:
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        if orig in tec_replacements:
            item["translation"] = tec_replacements[orig]
        elif orig in MON_TEC_COMMON:
            item["translation"] = MON_TEC_COMMON[orig]
        else:
            item["translation"] = orig

    with open(p_tec, "w", encoding="utf-8") as f:
        json.dump(tec_data, f, ensure_ascii=False, indent=2)
    print("Updated big/mon_tec.json")

    p_wtec = AI_MSG_DIR / "big/wireless_tec.json"
    with open(p_wtec, "r", encoding="utf-8") as f:
        wtec_data = json.load(f)

    for item in wtec_data:
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        if orig in MON_TEC_COMMON:
            item["translation"] = MON_TEC_COMMON[orig]
        else:
            item["translation"] = orig

    with open(p_wtec, "w", encoding="utf-8") as f:
        json.dump(wtec_data, f, ensure_ascii=False, indent=2)
    print("Updated big/wireless_tec.json")


def translate_ex_mon_details():
    # 6. big/ex_monspot.json & big/ex_montec.json
    p_spot = AI_MSG_DIR / "big/ex_monspot.json"
    with open(p_spot, "r", encoding="utf-8") as f:
        spot_data = json.load(f)

    era_map = {
        "Present - ": "1000 г. — ",
        "Middle Ages - ": "600 г. — ",
        "Future - ": "2300 г. — ",
        "Prehistory - ": "До н. э. — ",
        "Antiquity - ": "Древн. — ",
        "Beyond Time's Eclipse": "За Затмением",
        "End of Time": "Конец Времён",
        "Black Omen": "Чёрное Знамение",
        "Dimensional Vortex": "Вихрь измерений",
        "Lost Sanctum": "Забытое Святилище",
    }

    loc_map = {
        "Leene Square": "Площадь Лины",
        "Guardia Forest": "Лес Гардии",
        "Prison Towers": "Башни тюрьмы",
        "Market": "Рынок",
        "Magus's Keep": "Замок Магуса",
        "Heckran Cave": "Пещера Хекрана",
        "Northern Ruins": "Северные руины",
        "Truce Canyon": "Каньон Трус",
        "Manolia Cathedral": "Собор Манолии",
        "Zenan Bridge": "Мост Зенан",
        "Denadoro Mountains": "Горы Денадоро",
        "Denadoro Mts.": "Горы Денадоро",
        "Magic Cave": "Магич. пещера",
        "Cursed Woods": "Проклятый лес",
        "Giant's Claw": "Клык Великана",
        "Ozzie's Fort": "Форт Оззи",
        "Sunken Desert": "Затонувш. пустыня",
        "Site 16": "Зона 16",
        "Site 32": "Зона 32",
        "Arris Dome": "Купол Аррис",
        "Abandoned Sewers": "Коллекторы",
        "Derelict Factory": "Заброш. завод",
        "Proto Dome": "Купол Прото",
        "Keeper's Dome": "Купол Хранителя",
        "Geno Dome": "Купол Гено",
        "Death Peak": "Пик Смерти",
        "Mystic Mountains": "Мистич. горы",
        "Mystic Mts.": "Мистич. горы",
        "Hunting Range": "Охотничьи угодья",
        "Forest Maze": "Лесной лабиринт",
        "Reptite Lair": "Логово рептитов",
        "Dactyl Nest": "Гнездо Дактилей",
        "Tyranno Lair": "Логово Тиранно",
        "Mudbeast Den": "Логово грязезверей",
        "Mountain of Woe": "Гора Скорби",
        "Zeal Palace": "Дворец Зил",
        "Ocean Palace": "Океанский дворец",
        "Blackbird": "«Чёрный Дрозд»",
        "North Cape": "Северный мыс",
    }

    for item in spot_data:
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        trans = orig
        for k, v in era_map.items():
            trans = trans.replace(k, v)
        for k, v in loc_map.items():
            trans = trans.replace(k, v)
        item["translation"] = trans

    with open(p_spot, "w", encoding="utf-8") as f:
        json.dump(spot_data, f, ensure_ascii=False, indent=2)
    print("Updated big/ex_monspot.json")

    p_tec = AI_MSG_DIR / "big/ex_montec.json"
    with open(p_tec, "r", encoding="utf-8") as f:
        tec_data = json.load(f)

    status_map = {
        "/ Sleep": "/ Сон",
        "/ Poison": "/ Яд",
        "/ Blind": "/ Слепота",
        "/ Confuse": "/ Смятение",
        "/ Stop": "/ Стоп",
        "/ Slow": "/ Замедление",
        "/ Chaos": "/ Хаос",
        "/ Instant KO": "/ Смерть",
        "/ Halves HP": "/ ОЗ -50%",
        "/ Absorbs HP": "/ Поглощение ОЗ",
        "/ Absorbs MP": "/ Поглощение ОМ",
        "/ Locks Techs": "/ Блок техник",
    }

    header_map = {
        "Counters:": "Контратаки:",
        "Combos:": "Комбо:",
        "Combo Counters:": "Комбо-контратаки:",
    }

    for item in tec_data:
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        lines = orig.split("\n")
        new_lines = []
        for line in lines:
            trimmed = line.strip()
            if trimmed in header_map:
                new_lines.append(header_map[trimmed])
            elif trimmed.startswith("- "):
                atk = trimmed[2:].strip()
                # Check status
                atk_trans = atk
                for sk, sv in status_map.items():
                    if sk in atk_trans:
                        atk_trans = atk_trans.replace(sk, sv)
                # Check common tec
                base_atk = atk.split(" / ")[0].strip()
                if base_atk in MON_TEC_COMMON:
                    atk_trans = atk_trans.replace(base_atk, MON_TEC_COMMON[base_atk])
                new_lines.append(" - " + atk_trans)
            else:
                new_lines.append(line)
        item["translation"] = "\n".join(new_lines)

    with open(p_tec, "w", encoding="utf-8") as f:
        json.dump(tec_data, f, ensure_ascii=False, indent=2)
    print("Updated big/ex_montec.json")


if __name__ == "__main__":
    translate_monsters()
    translate_mon_techs()
    translate_ex_mon_details()
