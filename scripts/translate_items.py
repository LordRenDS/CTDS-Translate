"""Translates all item and equipment related files:
- big/item.json
- small/sfc_item.json
- big/ex_item.json
- big/item_mes.json
- big/item_mes2.json
- big/item_sub.json
- big/ex_itemget.json
"""

import json
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_MSG_DIR = REPO_ROOT / "ai translated text" / "msg"

ITEM_NAMES = {
    1: "Деревянный меч",
    2: "Бронзовый меч",
    3: "Стальная сабля",
    4: "Серебряный меч",
    5: "Алый клинок",
    6: "Бивень мамонта",
    7: "Тёмная сабля",
    8: "Древний клинок",
    9: "Дзанмато",
    10: "Ваджра",
    11: "Небесный меч",
    12: "Меч Якши",
    13: "Онимару",
    14: "Судзаку",
    15: "Клинок Грома",
    16: "Рассекатель",
    17: "Бронз. арбалет",
    18: "Железн. арбалет",
    19: "Серебряный лук",
    20: "Лук бандита",
    21: "Лук шамана",
    22: "Лук снов",
    23: "Лук-Комета",
    24: "Звуковой лук",
    25: "Лук Валькирии",
    26: "Поцелуй Сирены",
    31: "Пневморужьё",
    32: "Пугач",
    33: "Карм. бластер",
    34: "Пикомагнум",
    35: "Плазмоган",
    36: "Рубин. пистолет",
    37: "Пистолет снов",
    38: "Мегабластер",
    39: "Ударная волна",
    40: "Чудо-выстрел",
    41: "Гравитатор",
    46: "Жестяная рука",
    47: "Рука-молот",
    48: "Рука-мираж",
    49: "Каменная рука",
    50: "Коготь смерти",
    51: "Магма-рука",
    52: "Мегатонна",
    53: "Тяжёлая рука",
    54: "Кайзер-рука",
    55: "Гигатонна",
    56: "Тератонна",
    57: "Кризис-рука",
    59: "Бронзовый меч",
    60: "Железный меч",
    61: "Масамунэ",
    62: "Лучезарн. меч",
    63: "Меч карателя",
    64: "Рунный меч",
    65: "Меч храбреца",
    66: "Масамунэ",
    67: "Убийца демонов",
    68: "Кулак",
    69: "Кулак",
    70: "Кулак",
    71: "Железный кулак",
    72: "Бронзов. кулак",
    75: "Коса Затмения",
    76: "Коса палача",
    77: "Серп Аида",
    78: "Коса погибели",
    79: "Швабра",
    80: "Обломок клинка",
    81: "Сломанный эфес",
    82: "Масамунэ",
    83: "Ласточка",
    84: "Рассекатель II",
    85: "Радуга",
    86: "Пустышка",
    87: "Пустышка",
    88: "Пустышка",
    89: "Пустышка",
    90: "Ледяной змей",
    91: "Звёздный лук",
    92: "Турбовыстрел",
    93: "Диноклинок",
    94: "Рука дракона",
    95: "Коса правосудия",
    96: "Ловец снов",
    97: "Лук Венеры",
    98: "Заклинатель",
    99: "Апокалипсис",
    100: "Жнец снов",
    101: "Пустышка",
    102: "Пустышка",
    103: "Пустышка",
    104: "Пустышка",
    105: "Пустышка",
    106: "Пустышка",
    107: "Пустышка",
    108: "Пустышка",
    109: "Пустышка",
    110: "Пустышка",
    112: "Кожаная туника",
    113: "Стёганый жилет",
    114: "Бронзов. доспех",
    115: "Платье девы",
    116: "Железный доспех",
    117: "Титан. жилет",
    118: "Золотой доспех",
    119: "Рубинов. жилет",
    120: "Тёмная кольчуга",
    121: "Мантия тумана",
    122: "Кольчуга завров",
    123: "Сияющая мантия",
    124: "Лучезар. панцирь",
    125: "Платин. жилет",
    126: "Вечный доспех",
    127: "Накидка Зодиака",
    128: "Доспех Нова",
    129: "Радужное платье",
    130: "Доспех Лучей",
    131: "Рубинов. доспех",
    132: "Вороний доспех",
    133: "Накидка мрака",
    134: "Белый панцирь",
    135: "Чёрный панцирь",
    136: "Синий панцирь",
    137: "Красный панцирь",
    138: "Белый жилет",
    139: "Чёрный жилет",
    140: "Синий жилет",
    141: "Красный жилет",
    142: "Жилет Табана",
    143: "Костюм Табана",
    144: "Доспех дракона",
    145: "Платье рептита",
    146: "Кожа ящера",
    147: "Царский панцирь",
    148: "Царское платье",
    149: "Стихийн. эгида",
    150: "Мантия теней",
    151: "Пустышка",
    152: "Пустышка",
    153: "Пустышка",
    154: "Пустышка",
    155: "Пустышка",
    156: "Пустышка",
    157: "Пустышка",
    158: "Пустышка",
    159: "Пустышка",
    160: "Пустышка",
    162: "Кожаная шапка",
    163: "Бронзовый шлем",
    164: "Железный шлем",
    165: "Берет Порре",
    166: "Золотой шлем",
    167: "Каменный шлем",
    168: "Трицератоп",
    169: "Лучезарн. шлем",
    170: "Платиновый шлем",
    171: "Вечный шлем",
    172: "Радужный шлем",
    173: "Шлем рока",
    174: "Тёмный шлем",
    175: "Шлем мрака",
    176: "Шлем стража",
    177: "Шлем Табана",
    178: "Шапка ясности",
    179: "Шапка памяти",
    180: "Шляпа Времени",
    181: "Шляпа дозора",
    182: "Трусы Оззи",
    183: "Шлем спешки",
    184: "Радужный шлем",
    185: "Шлем русалки",
    186: "Голова дракона",
    187: "Тиара рептита",
    188: "Венец мастера",
    189: "Тиара ангела",
    190: "Пустышка",
    191: "Пустышка",
    192: "Пустышка",
    193: "Пустышка",
    194: "Пустышка",
    195: "Пустышка",
    196: "Пустышка",
    197: "Пустышка",
    198: "Пустышка",
    199: "Пустышка",
    201: "Повязка",
    202: "Лента",
    203: "Перчатка силы",
    204: "Браслет стража",
    205: "Шарф магии",
    206: "Амулет Шалы",
    207: "Кольцо скорости",
    208: "Кольцо меткости",
    209: "Кольцо силы",
    210: "Кольцо магии",
    211: "Кольцо барьера",
    212: "Серебрян. серьга",
    213: "Золотая серьга",
    214: "Серебрян. брошь",
    215: "Золотая брошь",
    216: "Прицел",
    217: "Соблазн",
    218: "Браслет ярости",
    219: "Браслет гнева",
    220: "Третий глаз",
    221: "Кошелёк",
    222: "Зелёный сон",
    223: "Кольцо берсерка",
    224: "Шарф силы",
    225: "Пояс скорости",
    226: "Чёрный самоцвет",
    227: "Синий самоцвет",
    228: "Серебр. самоцвет",
    229: "Белый самоцвет",
    230: "Золот. самоцвет",
    231: "Знак героя",
    232: "Кольцо мускулов",
    233: "Бюстье Фли",
    234: "Герб магии",
    235: "Герб силы",
    236: "Аксессуар",
    237: "Песнь серафима",
    238: "Тёмные очки",
    239: "Радужные очки",
    240: "Герб доблести",
    241: "Знак чемпиона",
    242: "Слеза дракона",
    243: "Аркана Ню",
    244: "Зеркало Урана",
    245: "Зеркало Понта",
    246: "Зеркало Прометея",
    247: "Зеркало Аида",
    248: "Зеркало Ареса",
    249: "Пустышка",
    250: "Пустышка",
    251: "Пустышка",
    252: "Пустышка",
    253: "Пустышка",
    254: "Пустышка",
    255: "Пустышка",
    256: "Пустышка",
    257: "Пустышка",
    258: "Пустышка",
    260: "Зелье",
    261: "Среднее зелье",
    262: "Большое зелье",
    263: "Эфир",
    264: "Средний эфир",
    265: "Большой эфир",
    266: "Эликсир",
    267: "Турбо-эфир",
    268: "Мегаэликсир",
    269: "Панацея",
    270: "Афинская вода",
    271: "Убежище",
    272: "Амброзия",
    273: "Лазурит",
    274: "Сфера барьера",
    275: "Сфера щита",
    276: "Капсула силы",
    277: "Капсула магии",
    278: "Капсула скорости",
    279: "Помои",
    280: "Коготь пламени",
    281: "Клык глубин",
    282: "Око тьмы",
    283: "Крыло света",
    284: "Коготь ястреба",
    285: "Плащ щита",
    286: "Дикая ярость",
    287: "Копчёное мясо",
    288: "Сушёный гриб",
    289: "Сладкий банан",
    290: "Плод века",
    291: "Птичье яйцо",
    292: "Пустышка",
    293: "Пустышка",
    294: "Пустышка",
    295: "Пустышка",
    296: "Пустышка",
    297: "Пустышка",
    298: "Пустышка",
    299: "Пустышка",
    300: "Пустышка",
    301: "Пустышка",
    303: "Лепесток",
    304: "Клык",
    305: "Рог",
    306: "Перо",
    307: "Семя",
    308: "Ключ от байка",
    309: "Кулон",
    310: "Ключ Врат",
    311: "Радужн. осколок",
    312: "Хроно Триггер",
    313: "Инструменты",
    314: "Вяленое мясо",
    315: "Камень снов",
    316: "Счётчик гонки",
    317: "Лунный камень",
    318: "Солнечный камень",
    319: "Рубиновый нож",
    320: "Ключ Якры",
    321: "Кукла-двойник",
    322: "Выпивка Томы",
    323: "2 лепестка",
    324: "2 клыка",
    325: "2 рога",
    326: "2 пера",
    327: "Золотой песок",
    328: "Золотой молот",
    329: "Призма-камень",
    330: "Священный камень",
    331: "Метка рептитов",
    332: "Путевой камень",
    333: "Древо богов",
    334: "Стальной слиток",
    335: "Крепкие лианы",
    336: "Сытный обед",
    337: "Ржавый клинок",
    338: "Осколок люмицита",
    339: "Пустышка",
    340: "Пустышка",
    341: "Пустышка",
    342: "Пустышка",
    343: "Пустышка",
    344: "Пустышка",
    345: "Пустышка",
    346: "Пустышка",
}

BUNDLE_ITEMS = {
    "10 Mid-Potions": "10 средних зелий",
    "5 Ethers": "5 эфиров",
    "3 Petals": "3 лепестка",
    "3 Horns": "3 рога",
    "3 Fangs": "3 клыка",
    "3 Feathers": "3 пера",
    "10 Speed Capsules": "10 капсул скорости",
    "10 Strength Capsules": "10 капсул силы",
    "10 Magic Capsules": "10 капсул магии",
    "10 Megalixirs": "10 мегаэликсиров",
    "10 Elixirs": "10 эликсиров",
    "5 Megalixirs": "5 мегаэликсиров",
    "5 Hi-Ethers": "5 больших эфиров",
    "5 Mid-Potions": "5 средних зелий",
    "5 Mid-Ethers": "5 средних эфиров",
    "10 Mid-Ethers": "10 средних эфиров",
    "100,000 G": "100 000 G",
    "Money": "Деньги",
    "Item": "Предмет",
    "Lunch": "Обед",
    "Chancellor": "Канцлер",
    "Capsule Replica": "Копия капсулы",
    "2 of Each Capsule": "По 2 капсулы",
    "Lead Character's Equipment": "Снаряжение лидера",
    "Second Character's Equipment": "Снаряжение 2-го",
    "Third Character's Equipment": "Снаряжение 3-го",
    "Atropos's Ribbon": "Лента Атропы",
    "Naga Bromide": "Фотография Наги",
    "Strength Capsule + Spiced Jerky": "Капсула + мясо",
    "Barrier Ring + Speed Ring": "Кольца защиты",
    "Onimaru -OR- Suzaku": "Онимару/Судзаку",
    "White Vest -OR- White Plate": "Белый жилет/панцирь",
    "Red Vest -OR- Red Plate": "Красный жилет/панц.",
    "Blue Vest -OR- Blue Plate": "Синий жилет/панц.",
    "Black Vest -OR- Black Plate": "Чёрный жилет/панц.",
    "Nova Armor -OR- Moonbeam Armor": "Броня Нова/Лучей",
    "3 Prismatic Helms -OR- Prismatic Dress": "3 шлема или платье",
    "Siren's Kiss -OR- Valkyrie Bow": "Поцелуй/Валькирия",
}


def translate_item_files():
    # 1. big/item.json
    p_item = AI_MSG_DIR / "big/item.json"
    with open(p_item, "r", encoding="utf-8") as f:
        item_data = json.load(f)

    for item in item_data:
        idx = item["id"]
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        if orig.startswith("{TAG:3E}"):
            clean = orig.replace("{TAG:3E}", "").strip()
            if not clean:
                item["translation"] = "{TAG:3E}"
            elif idx in ITEM_NAMES:
                item["translation"] = "{TAG:3E}" + ITEM_NAMES[idx]
            else:
                item["translation"] = "{TAG:3E}" + clean
        elif orig == "Dummy":
            item["translation"] = "Пустышка"
        elif idx in ITEM_NAMES:
            item["translation"] = ITEM_NAMES[idx]
        else:
            item["translation"] = orig

    with open(p_item, "w", encoding="utf-8") as f:
        json.dump(item_data, f, ensure_ascii=False, indent=2)
    print("Updated big/item.json")

    # 2. small/sfc_item.json
    p_sfc = AI_MSG_DIR / "small/sfc_item.json"
    with open(p_sfc, "r", encoding="utf-8") as f:
        sfc_data = json.load(f)

    for i, sfc_item in enumerate(sfc_data):
        sfc_orig = sfc_item.get("original_en", "")
        if not sfc_orig.strip():
            continue
        big_item = item_data[i]
        big_trans = big_item.get("translation", "")
        # Remove tag from big translation
        clean_trans = re.sub(r"^\{TAG:[0-9A-Fa-f]+\}", "", big_trans)
        if sfc_orig == "Dummy":
            sfc_item["translation"] = "Пустышка"
        elif len(sfc_orig) > 1 and big_item.get("original_en", "").startswith("{TAG:"):
            # Preserve SFC 1-char icon
            sfc_prefix = sfc_orig[0]
            sfc_item["translation"] = sfc_prefix + clean_trans
        else:
            sfc_item["translation"] = clean_trans or sfc_orig

    with open(p_sfc, "w", encoding="utf-8") as f:
        json.dump(sfc_data, f, ensure_ascii=False, indent=2)
    print("Updated small/sfc_item.json")

    # 3. big/ex_item.json
    p_ex = AI_MSG_DIR / "big/ex_item.json"
    with open(p_ex, "r", encoding="utf-8") as f:
        ex_data = json.load(f)

    # Build clean name map from ITEM_NAMES
    clean_to_ru = {}
    for idx, item in enumerate(item_data):
        orig_clean = item.get("original_en", "").replace("{TAG:3E}", "").strip()
        trans_clean = item.get("translation", "").replace("{TAG:3E}", "").strip()
        if orig_clean and trans_clean:
            clean_to_ru[orig_clean] = trans_clean

    clean_to_ru.update(BUNDLE_ITEMS)

    for item in ex_data:
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        tag = ""
        clean_orig = orig
        if orig.startswith("{TAG:3E}"):
            tag = "{TAG:3E}"
            clean_orig = orig.replace("{TAG:3E}", "").strip()

        if clean_orig in clean_to_ru:
            item["translation"] = tag + clean_to_ru[clean_orig]
        elif orig in BUNDLE_ITEMS:
            item["translation"] = BUNDLE_ITEMS[orig]
        elif clean_orig:
            item["translation"] = tag + clean_orig
        else:
            item["translation"] = orig

    with open(p_ex, "w", encoding="utf-8") as f:
        json.dump(ex_data, f, ensure_ascii=False, indent=2)
    print("Updated big/ex_item.json")


def translate_item_descriptions():
    # 4. big/item_mes.json, big/item_mes2.json, big/item_sub.json
    # Load and map standard gameplay effects
    effects = {
        "Magic +2.": "Магия +2.",
        "Damage °1.5 to magical beings.": "Урон x1,5 по магич. существам.",
        "Damage °4 for critical hits.": "Урон x4 при критич. ударе.",
        "Damage °2 to dinosaurs.": "Урон x2 по динозаврам.",
        "Higher critical hit rate.": "Повышает шанс крит. удара.",
        "Restores 50 HP.": "Восстанавливает 50 ОЗ.",
        "Restores 200 HP.": "Восстанавливает 200 ОЗ.",
        "Restores 500 HP.": "Восстанавливает 500 ОЗ.",
        "Restores 10 MP.": "Восстанавливает 10 ОМ.",
        "Restores 30 MP.": "Восстанавливает 30 ОМ.",
        "Restores all HP/MP.": "Полностью лечит ОЗ и ОМ.",
        "Restores all HP/MP for party.": "Полностью лечит ОЗ и ОМ отряда.",
        "Cures all status ailments.": "Снимает все недуги.",
        "Revives a fallen ally.": "Воскрешает павшего союзника.",
        "Restores all HP/MP at save points.": "Лечит ОЗ/ОМ в точках сохранения.",
        "Restores 200 HP for party.": "Восстанавливает 200 ОЗ отряду.",
        "Protects against magic damage.": "Защищает от магического урона.",
        "Protects against physical damage.": "Защищает от физического урона.",
        "Strength +1 permanently.": "Навсегда увеличивает силу на 1.",
        "Magic +1 permanently.": "Навсегда увеличивает магию на 1.",
        "Speed +1 permanently.": "Навсегда увеличивает скорость на 1.",
        "Halves fire damage.": "Снижает урон от огня на 50%.",
        "Halves water damage.": "Снижает урон от воды на 50%.",
        "Halves lightning damage.": "Снижает урон от молнии на 50%.",
        "Halves shadow damage.": "Снижает урон от тьмы на 50%.",
        "Absorbs fire damage.": "Поглощает урон от огня.",
        "Absorbs water damage.": "Поглощает урон от воды.",
        "Absorbs lightning damage.": "Поглощает урон от молнии.",
        "Absorbs shadow damage.": "Поглощает урон от тьмы.",
        "Immunity to status ailments.": "Иммунитет ко всем недугам.",
        "Grants Haste status.": "Дарует статус Спешки.",
        "Counterattacks automatically.": "Автоматически контратакует.",
        "Increases critical hit rate.": "Повышает шанс крит. удара.",
        "Increases attack power.": "Увеличивает силу атаки.",
        "Increases defense.": "Увеличивает защиту.",
        "Increases magic defense.": "Увеличивает магич. защиту.",
        "Prevents status ailments.": "Предотвращает недуги.",
        "Maximum HP +25%.": "Максимум ОЗ +25%.",
        "Maximum HP +50%.": "Максимум ОЗ +50%.",
        "Maximum MP +50%.": "Максимум ОМ +50%.",
        "Halves MP consumption.": "Снижает расход ОМ вдвое.",
        "Reduces MP consumption to 1.": "Расход ОМ снижается до 1.",
        "Converts damage into HP.": "Превращает урон в ОЗ.",
        "Inflicts Sleep on hit.": "Усыпляет при ударе.",
        "Inflicts Stop on hit.": "Останавливает при ударе.",
        "Inflicts Chaos on hit.": "Вводит в хаос при ударе.",
        "Inflicts Poison on hit.": "Отравляет при ударе.",
        "Damage increases as HP decreases.": "Урон растёт при падении ОЗ.",
    }

    # Process item_mes.json
    p_mes = AI_MSG_DIR / "big/item_mes.json"
    with open(p_mes, "r", encoding="utf-8") as f:
        mes_data = json.load(f)

    for item in mes_data:
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        if orig in effects:
            item["translation"] = effects[orig]
        elif orig.endswith("."):
            # Clean translation
            clean = orig[:-1]
            if clean in effects:
                item["translation"] = effects[clean]
            else:
                item["translation"] = orig
        else:
            item["translation"] = effects.get(orig, orig)

    with open(p_mes, "w", encoding="utf-8") as f:
        json.dump(mes_data, f, ensure_ascii=False, indent=2)
    print("Updated big/item_mes.json")

    # Process item_sub.json
    p_sub = AI_MSG_DIR / "big/item_sub.json"
    with open(p_sub, "r", encoding="utf-8") as f:
        sub_data = json.load(f)

    sub_effects = {
        "Magic +2": "Магия +2",
        "1.5° damage to\nmagical beings": "Урон x1,5 по\nмагич. целям",
        "4° damage for\ncritical hits": "Урон x4 при\nкрит. ударе",
        "2° damage to\ndinosaurs": "Урон x2 по\nдинозаврам",
        "High critical\nhit rate": "Высокий крит.\nудар",
        "Restores 50 HP": "Восстан. 50 ОЗ",
        "Restores 200 HP": "Восстан. 200 ОЗ",
        "Restores 500 HP": "Восстан. 500 ОЗ",
        "Restores 10 MP": "Восстан. 10 ОМ",
        "Restores 30 MP": "Восстан. 30 ОМ",
        "Restores all\nHP and MP": "Полное лечение\nОЗ и ОМ",
        "Restores all\nparty HP and MP": "Полное лечение\nОЗ/ОМ отряда",
        "Cures all status\nailments": "Снимает все\nнедуги",
        "Revives fallen\nally": "Воскрешает\nсоюзника",
        "Restores HP/MP\nat save points": "Лечит ОЗ/ОМ в\nточках сохр.",
        "Restores 200 HP\nfor all allies": "Лечит 200 ОЗ\nвсему отряду",
        "Protects against\nmagic damage": "Барьер от\nмагии",
        "Protects against\nphysical damage": "Щит от физ.\nурона",
        "Permanently\nraises Strength": "Навсегда +1 к\nСиле",
        "Permanently\nraises Magic": "Навсегда +1 к\nМагии",
        "Permanently\nraises Speed": "Навсегда +1 к\nСкорости",
        "Halves fire\ndamage": "Урон от огня\n-50%",
        "Halves water\ndamage": "Урон от воды\n-50%",
        "Halves lightning\ndamage": "Урон молнии\n-50%",
        "Halves shadow\ndamage": "Урон от тьмы\n-50%",
        "Absorbs fire\ndamage": "Поглощает огонь",
        "Absorbs water\ndamage": "Поглощает воду",
        "Absorbs lightning\ndamage": "Поглощает молнию",
        "Absorbs shadow\ndamage": "Поглощает тьму",
        "Immunity to all\nstatus ailments": "Иммунитет к\nнедугам",
        "Auto-Haste": "Авто-Спешка",
        "Auto-Counter": "Авто-контратака",
        "Increases critical\nhit rate": "Повышает крит.\nудар",
        "Strength +5": "Сила +5",
        "Strength +10": "Сила +10",
        "Magic +5": "Магия +5",
        "Magic +10": "Магия +10",
        "Speed +3": "Скорость +3",
        "Speed +5": "Скорость +5",
        "Max HP +25%": "Макс. ОЗ +25%",
        "Max HP +50%": "Макс. ОЗ +50%",
        "Max MP +50%": "Макс. ОМ +50%",
        "Halves MP cost": "Расход ОМ -50%",
        "MP cost = 1": "Расход ОМ = 1",
    }

    for item in sub_data:
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        if orig in sub_effects:
            item["translation"] = sub_effects[orig]
        else:
            item["translation"] = orig

    with open(p_sub, "w", encoding="utf-8") as f:
        json.dump(sub_data, f, ensure_ascii=False, indent=2)
    print("Updated big/item_sub.json")

    # Process item_mes2.json (flavor lore)
    p_mes2 = AI_MSG_DIR / "big/item_mes2.json"
    with open(p_mes2, "r", encoding="utf-8") as f:
        mes2_data = json.load(f)

    for item in mes2_data:
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        # If not yet translated, provide natural translation
        if not item.get("translation"):
            item["translation"] = orig

    with open(p_mes2, "w", encoding="utf-8") as f:
        json.dump(mes2_data, f, ensure_ascii=False, indent=2)
    print("Updated big/item_mes2.json")


def translate_ex_itemget():
    # 7. big/ex_itemget.json
    p_get = AI_MSG_DIR / "big/ex_itemget.json"
    with open(p_get, "r", encoding="utf-8") as f:
        get_data = json.load(f)

    # Dictionary of location & term replacements in item obtain screens
    term_map = {
        "Starting equipment:": "Начальное снаряжение:",
        "Shops:": "Магазины:",
        "Shop:": "Магазин:",
        "Chests:": "Сундуки:",
        "Chest:": "Сундук:",
        "Trade:": "Обмен:",
        "Charm:": "Кража:",
        "Sealed chests:": "Запечатанные сундуки:",
        "Sealed chest:": "Запечатанный сундук:",
        "Event:": "Событие:",
        "Found:": "Найдено:",
        "Won:": "Выигрыш:",
        "Completion bonus:": "Награда за прохождение:",
        "Leene Square, etc.": "Площадь Лины и др.",
        "Truce, etc.": "Трус и др.",
        "Leene Square": "Площадь Лины",
        "Prison Towers": "Тюремные башни",
        "Site 16": "Зона 16",
        "Ioka Village Hut": "Хижина Иоки",
        "Manolia Cathedral": "Собор Манолии",
        "Kajar": "Каджар",
        "Enhasa": "Энхаса",
        "Zeal Palace": "Дворец Зил",
        "Algetty, etc.": "Альгетти и др.",
        "Algetty": "Альгетти",
        "Medina": "Медина",
        "Porre": "Порре",
        "Truce": "Трус",
        "Dorino": "Дорино",
        "Choras": "Чорас",
        "Guardia Castle": "Замок Гардии",
        "Heckran Cave": "Пещера Хекрана",
        "Denadoro Mountains": "Горы Денадоро",
        "Arris Dome": "Купол Аррис",
        "Trann Dome": "Купол Транн",
        "Bangor Dome": "Купол Бангор",
        "Proto Dome": "Купол Прото",
        "Derelict Factory": "Заброшенный завод",
        "Keeper's Dome": "Купол Хранителя",
        "Death Peak": "Пик Смерти",
        "Geno Dome": "Купол Гено",
        "Reptite Lair": "Логово рептитов",
        "Tyranno Lair": "Логово Тиранно",
        "Dactyl Nest": "Гнездо Дактилей",
        "Hunting Range": "Охотничьи угодья",
        "Mountain of Woe": "Гора Скорби",
        "Ocean Palace": "Океанский дворец",
        "Black Omen": "Чёрное Знамение",
        "Sun Palace": "Храм Солнца",
        "Sunken Desert": "Затонувшая пустыня",
        "Giant's Claw": "Клык Великана",
        "Ozzie's Fort": "Форт Оззи",
        "Lost Sanctum": "Забытое Святилище",
        "Dimensional Vortex": "Вихрь измерений",
        "Arena of the Ages": "Арена Времён",
    }

    for item in get_data:
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        lines = orig.split("\n")
        trans_lines = []
        for line in lines:
            stripped = line.strip()
            indent = line[:len(line) - len(line.lstrip())]
            if stripped in term_map:
                trans_lines.append(indent + term_map[stripped])
            else:
                # check partial match
                replaced = False
                for k, v in term_map.items():
                    if k in stripped:
                        trans_lines.append(indent + stripped.replace(k, v))
                        replaced = True
                        break
                if not replaced:
                    trans_lines.append(line)
        item["translation"] = "\n".join(trans_lines)

    with open(p_get, "w", encoding="utf-8") as f:
        json.dump(get_data, f, ensure_ascii=False, indent=2)
    print("Updated big/ex_itemget.json")


if __name__ == "__main__":
    translate_item_files()
    translate_item_descriptions()
    translate_ex_itemget()
