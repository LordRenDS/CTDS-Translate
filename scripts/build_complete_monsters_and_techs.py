"""Comprehensive translation and validation script for all monster and tech files.
Updates:
- big/monster.json
- small/sfc_mon.json
- big/ex_mon.json
- big/wireless_mon.json
- big/wireless_mon2.json
- big/mon_tec.json
- big/wireless_tec.json
- big/ex_montec.json
- big/ex_monspot.json
"""

import json
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_MSG_DIR = REPO_ROOT / "ai translated text" / "msg"

# 1. Base monster translations (all <= 85px)
MONSTERS_DICT = {
    # Original monster_names
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
    "Boss Goblin": "Босс гоблинов",
    "Byte": "Байт",
    "Cave Ape": "Пещерн. обезь.",
    "Cave Bat": "Пещерн. мышь",
    "Chrono Trigger": "Хроно Триггер",
    "Crono": "Хроно",
    "Crono?": "Хроно?",
    "Dalton": "Дальтон",
    "Darkshade": "Тень тьмы",
    "Debug": "Отладка",
    "Defunct Laser": "Сломан. лазер",
    "Demon Knight": "Рыцарь-демон",
    "Dragon Tank": "Дракон-танк",
    "Edgar": "Эдгар",
    "Elder Lavos Spawn": "Порождение",
    "Flea": "Фли",
    "Flea Plus": "Фли Плюс",
    "Frog Statue": "Статуя Фрога",
    "Gato": "Гато",
    "Genetic Pod": "Генетич. кокон",
    "Giga Gaia (Head)": "Гига-Гайя",
    "Giga Gaia (Left Arm)": "Левая рука",
    "Giga Gaia (Right Arm)": "Правая рука",
    "Goblin": "Гоблин",
    "Gold Eaglet": "Золотой орёл",
    "Goldrock": "Златокамень",
    "Golemette": "Големетта",
    "Great Ozzie": "Великий Оззи",
    "Gremlin": "Гремлин",
    "Grimalkin": "Грималкин",
    "Guard": "Стражник",
    "Guardia Officer": "Офицер",
    "Heckran": "Хекран",
    "Hench": "Прихвостень",
    "Highbrow": "Интеллектуал",
    "Hoplite": "Гоплит",
    "Laser Guard": "Лазерн. страж",
    "Lavos": "Лавос",
    "Lavos (Left Arm)": "Левая рука",
    "Lavos (Right Arm)": "Правая рука",
    "Lavos Spawn": "Порождение",
    "Lucca Statue": "Статуя Лукки",
    "Mad Mole": "Бешеный крот",
    "Magus": "Магус",
    "Man-eater": "Людоед",
    "Meat": "Мясо",
    "Mega Mutant": "Мега-мутант",
    "Mother Brain": "Матерь-Мозг",
    "Mud Monster": "Грязевик",
    "Nizbel": "Низбель",
    "Nizbel II": "Низбель II",
    "Octoblush": "Осьминог",
    "Ogan": "Оган",
    "Ozzie": "Оззи",
    "Peeping Doom": "Всевидящий",
    "Poly": "Поли",
    "Proto 2": "Прото 2",
    "Proto 3": "Прото 3",
    "Proto 4": "Прото 4",
    "R-Series": "Серия R",
    "R-Series 1": "R-1",
    "R-Series 2": "R-2",
    "R-Series 3": "R-3",
    "R-Series 4": "R-4",
    "R-Series 5": "R-5",
    "R-Series 6": "R-6",
    "Rainfrog": "Дождевая жаба",
    "Reptite (Blue)": "Рептит (Синий)",
    "Reptite (Red)": "Рептит (Красн.)",
    "Robo": "Робо",
    "Rust Tyranno": "Ржав. Тиранно",
    "Scouter": "Скаут",
    "Shadow": "Тень",
    "Slash": "Слэш",
    "Sorcerer": "Колдун",
    "Super Slash": "Супер-Слэш",
    "Synchrite": "Синхрит",
    "Turret": "Турель",
    "Volcano": "Вулкан",
    "Yakra": "Якра",
    "Yakra XIII": "Якра XIII",
    "Zeal": "Зил",
    "Zombor": "Зомбор",
    
    # 140 missing monsters
    "Archmage": "Архимаг",
    "Crested Sprinter": "Бегун",
    "Crimson Shade": "Алая тень",
    "Cybot": "Кибот",
    "Cyrus": "Сайрус",
    "Daltonite": "Дальтонит",
    "Deathcreeper": "Ползун",
    "Deathscythe": "Коса смерти",
    "Deep Ogan": "Оган глубин",
    "Deverminator": "Дезинсектор",
    "Deverminator EX": "Дезинсект. EX",
    "Diablo": "Диабло",
    "Dire Rat": "Лютокрыса",
    "Diva Flea": "Дива Фли",
    "Djinn": "Джинн",
    "Dokra": "Докра",
    "Dondrago": "Дондраго",
    "Dream Devourer": "Пожиратель",
    "Dummy": "Пустышка",
    "Edible Frog": "Лягушка",
    "Eggsterminator": "Яйцеборец",
    "Exterminator": "Истребитель",
    "Fangbeast": "Клыкозверь",
    "Fireball": "Огнен. шар",
    "Flame Smidge": "Огонёк",
    "Flea?": "Фли?",
    "Flyclops": "Мухоглаз",
    "Frog King": "Король-жаб",
    "Gaoler": "Тюремщик",
    "Ghaj": "Гай",
    "Ghul": "Гуль",
    "Giga Gaia": "Гига-Гайя",
    "Gigantosaur": "Гигантозавр",
    "Gokuu": "Гоку",
    "Goldhammer": "Златомолот",
    "Golem Overlord": "Владыка",
    "Gorgon": "Горгона",
    "Grimling": "Гримлинг",
    "Hercules Beetle": "Геркулес",
    "Holy Knight": "Свят. рыцарь",
    "Ice Demon": "Ледян. демон",
    "Imp Priest": "Чёрт-жрец",
    "Ion Cloud": "Ион. облако",
    "Jackpot": "Джекпот",
    "Jadewing": "Нефритокрыл",
    "King Dalton": "Дальтон",
    "Kingfrog": "Король-жаб",
    "Lavos Core": "Ядро Лавоса",
    "Left Arm": "Левая рука",
    "Left Hand": "Левая кисть",
    "Light Smidge": "Светлячок",
    "Lizardactyl": "Ящеродактиль",
    "Mad Bat": "Бешен. мышь",
    "Magus Effect": "Эффект",
    "Magus Statue": "Статуя",
    "Marle Statue": "Статуя",
    "Masa": "Маса",
    "Masa & Mune": "Маса и Мунэ",
    "Master-at-Arms": "Оружейник",
    "Medusa": "Медуза",
    "Metal Mutant": "Мутант",
    "Monk": "Монах",
    "Monster": "Монстр",
    "Mossback": "Мшистый",
    "Mudbeast": "Грязезверь",
    "Mune": "Мунэ",
    "Mutant": "Мутант",
    "Narble": "Нарбл",
    "Ninja": "Ниндзя",
    "Nu Guardian": "Страж Ню",
    "Ogan Chieftain": "Вождь оганов",
    "Ogan Youth": "Оган-юнга",
    "Once-King Dalton": "Дальтон",
    "Ouroboros": "Уроборос",
    "Ozzie the Great": "Великий Оззи",
    "Parasaur": "Паразавр",
    "Pink Imp": "Розов. чёрт",
    "Pod": "Кокон",
    "Prehistoric Frog": "Древн. жаба",
    "Prominence": "Протуберанец",
    "Prototype": "Прототип",
    "Pterranyx": "Птераникс",
    "R-70Y": "R-70Y",
    "Racer": "Гонщик",
    "Rat": "Крыса",
    "Red Ghaj": "Красный гай",
    "Red Scouter": "Красн. скаут",
    "Rhino Weevil": "Слоник",
    "Right Arm": "Правая рука",
    "Right Hand": "Правая кисть",
    "Robo Statue": "Статуя Робо",
    "Roundillo Bomber": "Бомбардир",
    "Rubble": "Булыжник",
    "Sandrago": "Сандраго",
    "Scarab": "Скарабей",
    "Schist": "Сланец",
    "Searcher": "Искатель",
    "Servant": "Слуга",
    "Shadow Smidge": "Тенёк",
    "Slate Imp": "Серый чёрт",
    "Snowbeast": "Снежн. зверь",
    "Son of the Sun": "Сын Солнца",
    "Soul": "Душа",
    "Soul Stalker": "Ловец душ",
    "Spearman": "Копейщик",
    "Spirit Gargoyle": "Дух-горгулья",
    "Steel Shade": "Стальн. тень",
    "Stone Gargoyle": "Кам. горгулья",
    "Tank Head": "Голова танка",
    "Twin Snake": "Змеи",
    "Uberhulk": "Супергромила",
    "Vampire Bat": "Вампир",
    "Version 2.0": "Версия 2.0",
    "Version 3.0": "Версия 3.0",
    "Version 4.0": "Версия 4.0",
    "Vilepillar": "Злоцвет",
    "Volcanite": "Вулканит",
    "Warrior": "Воин",
    "Water Smidge": "Капелька",
    "Wheel": "Колесо",
    "Wonder Rock": "Чудо-камень",
    "archmage": "Архимаг",
    "crested sprinter": "Бегун",
    "deathscythe": "Коса смерти",
    "deep ogan": "Оган глубин",
    "dokra": "Докра",
    "flame smidge": "Огонёк",
    "gigantosaur": "Гигантозавр",
    "gokuu": "Гоку",
    "gorgon": "Горгона",
    "hercules beetle": "Геркулес",
    "holy knight": "Свят. рыцарь",
    "ice demon": "Ледян. демон",
    "light smidge": "Светлячок",
    "medusa": "Медуза",
    "ninja": "Ниндзя",
    "ogan youth": "Оган-юнга",
    "ouroboros": "Уроборос",
    "parasaur": "Паразавр",
    "pink imp": "Розов. чёрт",
    "prototype": "Прототип",
    "racer": "Гонщик",
    "rhino weevil": "Слоник",
    "roundillo bomber": "Бомбардир",
    "shadow smidge": "Тенёк",
    "slate imp": "Серый чёрт",
    "spearman": "Копейщик",
    "spirit gargoyle": "Дух-горгулья",
    "stone gargoyle": "Кам. горгулья",
    "uberhulk": "Супергромила",
    "water smidge": "Капелька",
    "{MAGUS}": "{MAGUS}",
    
    # Extra multipart / bestiary names
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
}

# 2. Battle announcements and monster tech banners (mon_tec.json & wireless_tec.json)
from scripts.test_tec_widths import MON_TEC_MAP

# 3. Wireless tech extras (110 entries)
W_TEC_EXTRA = {
    'Abyssal Spear': 'Копьё бездны',
    'Aqua Blast': 'Водный взрыв',
    'Ardent Spear': 'Пылкое копьё',
    'Ball Lightning': 'Шаровая молния',
    'Black Chakram': 'Чёрный чакрам',
    'Blazing Charge': 'Пылающий разгон',
    'Blazing Shuriken': 'Огненный сюрикен',
    'Blazing Tackle': 'Пылающий толчок',
    'Blue Chakram': 'Синий чакрам',
    'Brine Bite': 'Едкий укус',
    'Bullet Barrage': 'Пулемётный шквал',
    'Burning Sphere': 'Горящая сфера',
    'Conflagration': 'Пожарище',
    'Cyclopean Hammer': 'Молот циклопа',
    'Dark Blast': 'Тёмный взрыв',
    'Dark Strike': 'Тёмный удар',
    'Diluvial Charge': 'Потопный разгон',
    'Diluvial Tackle': 'Потопный толчок',
    'Drenching Spear': 'Водяное копьё',
    'Electric Spines': 'Электрошипы',
    'Electrified Bite': 'Электроукус',
    'Empyrean Rain': 'Небесный дождь',
    'Fiendillo Darkness': 'Тьма фиендилло',
    'Fiendillo Fire': 'Огонь фиендилло',
    'Fiendillo Lightning': 'Гром фиендилло',
    'Fiendillo Water': 'Вода фиендилло',
    'Fire Blast': 'Огненный взрыв',
    'Fire II': 'Огонь II',
    'Fire Shot': 'Огненный выстрел',
    'Fire Strike': 'Огненный удар',
    'Firebreath': 'Огнедыхание',
    'Fist of Darkness': 'Кулак тьмы',
    'Fist of Flame': 'Кулак пламени',
    'Fist of Light': 'Кулак света',
    'Fist of Water': 'Кулак воды',
    'Flame Spines': 'Огненные шипы',
    'Frigid Rain': 'Ледяной дождь',
    'Gorgon Flame': 'Огонь горгоны',
    'Gorgon Ice': 'Лёд горгоны',
    'Gorgon Shadow': 'Тень горгоны',
    'Gorgon Thunder': 'Гром горгоны',
    'Hailstone': 'Градина',
    'Hammer': 'Молот',
    'Head-butt': 'Удар головой',
    'Heavenly Judgment': 'Небесный суд',
    'Hell Geyser': 'Адский гейзер',
    "Hell's Gate": 'Врата Ада',
    'Hellish Bite': 'Адский укус',
    'Hit': 'Удар',
    'Holy Charge': 'Святой разгон',
    'Holy Tackle': 'Святой толчок',
    'Hydrobomb': 'Гидробомба',
    'Ice Grenade': 'Ледяная граната',
    'Ice Sphere': 'Ледяная сфера',
    'Ice Spines': 'Ледяные шипы',
    'Icepick': 'Ледоруб',
    'Infernal Charge': 'Адский разгон',
    'Infernal Tackle': 'Адский толчок',
    'Jump Kick': 'Удар в прыжке',
    'Kick Combo': 'Серия пинков',
    'Lava Rain': 'Дождь из лавы',
    'Light Chakram': 'Светлый чакрам',
    'Lightning II': 'Молния II',
    'Lightning Spear': 'Копьё молнии',
    'Lightning Storm': 'Грозовой шторм',
    'Machine Gun': 'Пулемёт',
    'Mage Fire': 'Магический огонь',
    'Medusa Flame': 'Огонь медузы',
    'Medusa Ice': 'Лёд медузы',
    'Medusa Shadow': 'Тень медузы',
    'Medusa Thunder': 'Гром медузы',
    'Naga Flame': 'Огонь наги',
    'Naga Ice': 'Лёд наги',
    'Naga Shadow': 'Тень наги',
    'Naga Thunder': 'Гром наги',
    'Nether Bomb': 'Бомба преисподней',
    'Nether Shot': 'Выстрел преисподней',
    'Nether Shuriken': 'Сюрикен преисподней',
    'Purple Rain': 'Пурпурный дождь',
    'Rage': 'Ярость',
    'Red Chakram': 'Красный чакрам',
    'Riptide Shuriken': 'Водоворотный сюрикен',
    'Robo Punch': 'Удар Робо',
    'Roundillo Darkness': 'Тьма раундилло',
    'Roundillo Fire': 'Огонь раундилло',
    'Roundillo Lightning': 'Гром раундилло',
    'Roundillo Water': 'Вода раундилло',
    'Scythe': 'Коса',
    'Searing Bite': 'Обжигающий укус',
    'Shadow Spines': 'Шипы тени',
    'Slap': 'Пощёчина',
    'Sobat': 'Собат',
    'Spark Bomb': 'Искристая бомба',
    'Stygian Spines': 'Стигийские шипы',
    'Summon Eclipse': 'Призыв затмения',
    'Summon Inferno': 'Призыв инферно',
    'Summon Riptide': 'Призыв водоворота',
    'Summon Thunderbolt': 'Призыв молнии',
    'Tail Swipe': 'Удар хвостом',
    "Thor's Hammer": 'Молот Тора',
    'Thunder Blast': 'Громовой взрыв',
    'Thunder Shot': 'Громовой выстрел',
    'Thunder Shuriken': 'Громовой сюрикен',
    'Thunder Strike': 'Удар грома',
    'Umbra': 'Тень',
    'Vulcan Hammer': 'Вулканический молот',
    'Water Hammer': 'Водяной молот',
    'Water II': 'Вода II',
    'Water Shot': 'Водный выстрел',
    'Water Strike': 'Водный удар',
}

# 4. Common base techs for ex_montec.json
EX_BASE_TECHS = {
    '10,000 Hz': '10 000 Гц',
    'Absorb Core Energy': 'Энергия ядра',
    'Absorb Energy': 'Поглощ. энергии',
    'Amplifier': 'Усилитель',
    'Annihilation Ray': 'Луч погибели',
    'Annihilation Zone': 'Зона погибели',
    'Arm Attack': 'Удар рукой',
    'Arm Restoration': 'Починка руки',
    'Attack': 'Атака',
    'Attack Moving Object': 'Атака по движению',
    'Attrition': 'Истощение',
    "Azala's Wrath": 'Гнев Азалы',
    'Barrage': 'Шквал',
    'Barrier Bomb': 'Барьер-бомба',
    'Beast Toss': 'Бросок зверя',
    'Beat': 'Удар',
    'Become Golden Eaglet': 'Превращ. в зол. орла',
    'Become Red Eaglet': 'Превращ. в красн. орла',
    'Bell Strike': 'Удар колокола',
    'Bite': 'Укус',
    'Blacken': 'Почернение',
    'Blade Dance': 'Танец клинков',
    'Blanket Bomb': 'Ковровая бомба',
    'Blaring Din': 'Оглушит. шум',
    'Blast Wave': 'Взрывная волна',
    'Blaze': 'Пламя',
    'Blood Drain': 'Питьё крови',
    'Bloodfeast': 'Кровавый пир',
    'Blow Kiss': 'Поцелуй',
    'Bluuurp!': 'Бульк!',
    'Boulder': 'Валун',
    'Bubbles': 'Пузыри',
    'Burrrp!': 'Бэээ!',
    'Burst Sphere': 'Взрывная сфера',
    'Chakram': 'Чакрам',
    'Chaos Zone': 'Зона хаоса',
    'Charge': 'Разгон',
    'Chemical Reaction': 'Хим. реакция',
    'Chomp': 'Чавканье',
    'Clamp': 'Зажим',
    'Claw': 'Коготь',
    'Cleave': 'Раскол',
    'Combo Attack': 'Серия атак',
    'Cricket Chirp': 'Стрекот сверчка',
    'Crimson Rain': 'Алый дождь',
    'Cross Charge': 'Крестовый разгон',
    'Crush': 'Дробление',
    'Crushing Blow': 'Дробящий удар',
    'Cure Beam': 'Луч лечения',
    'Curse': 'Проклятие',
    'Cyclone': 'Циклон',
    'Dark Beam': 'Тёмный луч',
    'Dark Bomb': 'Тёмная бомба',
    "Dark Flame's Embrace": 'Объятия пламени',
    'Dark Flare': 'Тёмная вспышка',
    'Dark Matter': 'Тёмная материя',
    'Dark Plasma': 'Тёмная плазма',
    'Dark Ray': 'Тёмный луч',
    'Dark Will': 'Тёмная воля',
    'Death': 'Смерть',
    'Death Kiss': 'Поцелуй смерти',
    "Death's Rainbow": 'Радуга смерти',
    'Deep Freeze': 'Глубокая заморозка',
    'Delta Attack': 'Дельта-атака',
    'Delta Force': 'Дельта-сила',
    'Demon Star': 'Звезда демона',
    'Desperate Strike': 'Отчаянный удар',
    "Devil's Drop": 'Капля дьявола',
    'Devour Frog': 'Поедание лягушки',
    'Diabolic Whisper': 'Шёпот дьявола',
    'Ding-a-ling': 'Динь-дон',
    'Dive': 'Пике',
    'Doublehand Blaster': 'Двойной бластер',
    'Doublehand Chop': 'Двойной удар',
    'Doublehand Slap': 'Двойной шлепок',
    'Dragon Charge': 'Разгон дракона',
    'Dragonfire': 'Огонь дракона',
    'Drain': 'Поглощение',
    'Drain Health': 'Кража жизни',
    'Dreamreaver': 'Ловец снов',
    'Earthquake': 'Землетрясение',
    'Earthshaker': 'Сотрясатель',
    'Electric Burst': 'Электровзрыв',
    'Electric Discharge': 'Электроразряд',
    'Electric Maelstrom': 'Электровихрь',
    'Electric Shock': 'Электрошок',
    'Electrify': 'Электризация',
    'Energy Blast': 'Взрыв энергии',
    'Energy Discharge': 'Сброс энергии',
    'Energy Spheres': 'Сферы энергии',
    'Entice': 'Соблазн',
    'Escape': 'Побег',
    'Evil Emanation': 'Зловещ. сияние',
    'Evil Impulse': 'Злой импульс',
    'Evil Touch': 'Злое касание',
    'Explosion': 'Взрыв',
    'Fangs': 'Клыки',
    'Fiendillo Dance': 'Танец фиендилло',
    'Fire': 'Огонь',
    'Fire Dance': 'Танец огня',
    'Fire II': 'Огонь II',
    'Fire Whirl': 'Огненный вихрь',
    'Firebomb': 'Огненная бомба',
    'Firebreath': 'Огнедыхание',
    'First Aid': 'Первая помощь',
    'Flame': 'Пламя',
    'Flame Counterattack': 'Огненная контратака',
    'Flame Strike': 'Огненный удар',
    'Flames of War': 'Пламя войны',
    'Flamethrower': 'Огнемёт',
    'Flare': 'Вспышка',
    'Flash of Steel': 'Блеск стали',
    'Flashbomb': 'Световая бомба',
    'Fling': 'Бросок',
    'Flying Lunge': 'Выпад в полёте',
    'Flying Punch': 'Кулак в полёте',
    'Flying Spin Kick': 'Вертушка в полёте',
    'Flying Stab': 'Укол в полёте',
    'Focused Strike': 'Точный удар',
    'Fraternal Fusion': 'Братское слияние',
    'Frenzy': 'Бешенство',
    'Gaia Magnade': 'Магнад Гайи',
    'Gale Slash': 'Шквальный разрез',
    'Gash': 'Глубокая рана',
    "Gato's Song of Love": 'Песенка Гато',
    'Gears of Darkness': 'Шестерни тьмы',
    'Gnaw': 'Грызение',
    'Golden Hammer': 'Золотой молот',
    'Gore': 'Бодание',
    'Grab and Drop': 'Захват и сброс',
    'Grand Destruction': 'Великий распад',
    'Grandstone': 'Грандстоун',
    'Great Hammer': 'Великий молот',
    'Great Pyroclast': 'Великий пирокласт',
    'Grudge': 'Злоба',
    'Halation': 'Гало',
    'Hammer': 'Молот',
    'Hammer Punch': 'Удар молотом',
    'Head-butt': 'Удар головой',
    'Heal': 'Исцеление',
    'Heart Shot': 'Сердце',
    'Heartfire': 'Жар сердца',
    'Heartfire Sword': 'Меч жара сердца',
    'Heavenly Gate': 'Небесные врата',
    'Heavenly Tears': 'Слёзы небес',
    'Hell Geyser': 'Адский гейзер',
    'Hidden Needles': 'Тайные иглы',
    'Hit': 'Удар',
    'Holy Light': 'Святой свет',
    'Hurricane': 'Ураган',
    'Hurricane Spin': 'Вихрь урагана',
    'Hypnotize': 'Гипноз',
    'Ice': 'Лёд',
    'Ice II': 'Лёд II',
    'Icefall': 'Ледопад',
    'Immobilize': 'Обездвиживание',
    'Impale': 'Пронзание',
    'Ingest': 'Пожирание',
    'Ink': 'Чернила',
    'Instant KO': 'Смерть',
    'Iron Sphere': 'Железная сфера',
    'Iron Sphere Blast': 'Взрыв сферы',
    'Jump': 'Прыжок',
    'Jump Kick': 'Удар в прыжке',
    'Kick': 'Пинок',
    'Kick Combo': 'Серия пинков',
    'Lambaste': 'Взбучка',
    'Laser': 'Лазер',
    'Laser Beams': 'Лучи лазера',
    'Laser Spin': 'Лазерный вихрь',
    'Lavos Breath': 'Дыхание Лавоса',
    'Lavos Needle': 'Игла Лавоса',
    'Lavos Spawn Needle': 'Игла Порождения',
    'Lavos Spawn Needles': 'Иглы Порождения',
    'Leech': 'Пиявка',
    'Left Charge': 'Левый разгон',
    'Life Grip': 'Хватка жизни',
    'Life Shaver': 'Бритва жизни',
    'Lightning': 'Молния',
    'Lightning II': 'Молния II',
    'Lock': 'Блок',
    'Luminaire': 'Люминар',
    'Lunate Barrage': 'Лунный шквал',
    'MP Buster': 'Похититель ОМ',
    'Machine Gun': 'Пулемёт',
    'Mash': 'Раздавливание',
    'Memory Reset': 'Сброс памяти',
    'Miasma': 'Миазмы',
    'Missiles': 'Ракеты',
    'Multi-punch': 'Серия ударов',
    'Munch': 'Хруст',
    'Muscular Fusion': 'Слияние мышц',
    'Mutant Gas': 'Газ мутанта',
    'Nagamour': 'Чары наги',
    'Nasal Gas': 'Носовой газ',
    'Needle': 'Игла',
    'Needle Spin': 'Вихрь игл',
    'Needle Spin Ver. XIII': 'Вихрь игл XIII',
    'Negate': 'Отрицание',
    'Nereid Cyclone': 'Циклон нереиды',
    'Nether Blast': 'Взрыв бездны',
    'Nizbel Charge': 'Разгон Низбеля',
    'Obliterate': 'Уничтожение',
    'Omnilock': 'Полный блок',
    'Osmose': 'Осмос',
    'Overdrive': 'Перегрузка',
    'Pebble Punt': 'Бросок гальки',
    'Peck': 'Клевок',
    'Permeate': 'Просачивание',
    'Plasma': 'Плазма',
    'Point Flare': 'Точечная вспышка',
    'Poison Arrows': 'Ядовитые стрелы',
    'Poison Mist': 'Ядовитый туман',
    'Pollen': 'Пыльца',
    'Possess': 'Одержимость',
    'Proximity Bomb': 'Мина близости',
    'Psychokinesis': 'Психокинез',
    'Punch': 'Удар кулаком',
    'Punch Volcanite': 'Удар по вулканиту',
    'Punching Glove': 'Боксёрская перчатка',
    'Pyroclast': 'Пирокласт',
    'Quake Hammer': 'Молот землетрясения',
    'Rain': 'Дождь',
    'Rain Destruction': 'Дождь погибели',
    'Rainbow Beam': 'Радужный луч',
    'Rainbow Dust': 'Радужная пыль',
    'Rainbow Storm': 'Радужный шторм',
    'Rapid-fire Fist': 'Пулемётный кулак',
    'Rapid-fire Punch': 'Скоростной удар',
    'Recover': 'Лечение',
    'Recuperate': 'Восстановление',
    'Rend': 'Раздирание',
    'Repair Body': 'Починка тела',
    'Reprogram': 'Перепрошивка',
    'Restore Head': 'Починка головы',
    'Resurrect': 'Воскрешение',
    'Revive Pods': 'Возрожд. коконов',
    'Right Charge': 'Правый разгон',
    'Roar': 'Рёв',
    'Robo Cable Punch': 'Кабельный удар Робо',
    'Robo Explosion': 'Взрыв Робо',
    'Robo Laser': 'Лазер Робо',
    'Robo Pitch': 'Бросок Робо',
    'Robo Punch': 'Удар Робо',
    'Robo Tackle': 'Толчок Робо',
    'Rocket Punch': 'Ракетный кулак',
    'Rolling Attack': 'Вращат. атака',
    'Roulette Spin': 'Вращение рулетки',
    'Roundillo Shot': 'Выстрел раундилло',
    'Rush': 'Натиск',
    'Salt': 'Соль',
    'Sand Breath': 'Песч. дыхание',
    'Sand Cyclone': 'Песчаный циклон',
    'Savage Swipe': 'Дикий взмах',
    'Scalding Steam': 'Обжигающий пар',
    'Scintillation': 'Мерцание',
    'Scorch': 'Опаление',
    'Scratch': 'Царапание',
    'Screech': 'Визг',
    'Scythe': 'Коса',
    'Self-destruct': 'Самоуничтожение',
    'Shadow Fire': 'Теневой огонь',
    'Shining Sphere': 'Сияющая сфера',
    'Shuriken': 'Сюрикен',
    'Siphon': 'Высасывание',
    'Skull Drop': 'Удар черепом',
    'Skyward Flame': 'Взмывающее пламя',
    'Slap': 'Шлепок',
    'Sleep Bubble': 'Пузырь сна',
    'Slice': 'Разрез',
    'Slurp': 'Хлюпанье',
    'Smash': 'Сокрушение',
    'Smoke Bomb': 'Дымовая бомба',
    'Snowstorm': 'Метель',
    'Sobat': 'Собат',
    'Somniwave': 'Сомновална',
    'Sonic Wave': 'Звуковая волна',
    'Soul Link': 'Связь душ',
    'Spin Attack': 'Вращение',
    'Spin Jump': 'Прыжок с вращением',
    'Spinning Hammer': 'Вращающийся молот',
    'Stab': 'Укол',
    'Staff': 'Посох',
    'Stand Still': 'Оцепенение',
    'Starburst': 'Звездопад',
    'Stench': 'Вонь',
    'Stomp': 'Топот',
    'Stretch': 'Растяжка',
    'Strike': 'Удар',
    'Sumo Slap': 'Удар сумо',
    'Supersonic Wave': 'Ультразвук',
    'Suppress': 'Подавление',
    'Sword Strike': 'Удар мечом',
    'Tackle': 'Толчок',
    'Telekinesis': 'Телекинез',
    'Telepathy': 'Телепатия',
    'Teleport': 'Телепорт',
    'Temblor': 'Сотрясение',
    'Temporal Shift': 'Временной сдвиг',
    'Tentacle': 'Щупальце',
    'Tentacle Strike': 'Удар щупальцем',
    'Terrifying Voice': 'Жуткий зов',
    'The Look': 'Взгляд',
    'Thrash': 'Трепка',
    'Throw': 'Бросок',
    'Thunder': 'Гром',
    'Thunder II': 'Гром II',
    'Thunderbolt': 'Удар молнии',
    'Thunderfall': 'Громопад',
    'Time Freeze': 'Заморозка времени',
    'Time Stop': 'Остановка времени',
    'Tongue': 'Язык',
    'Torrential Blast': 'Ливневый шквал',
    'Triple Slice': 'Тройной разрез',
    'Tsubame Gaeshi': 'Цубамэ Гаэси',
    'Turn Attack into Defense': 'Атака в защиту',
    'Turn Magic into Attack': 'Магия в атаку',
    'Twin Attack': 'Двойная атака',
    'Twister': 'Твистер',
    'Typhoon': 'Тайфун',
    'Tyranno Flame': 'Пламя Тиранно',
    'Ultrasonic Wave': 'Ультразвук',
    'Umbral Embrace': 'Теневые объятия',
    'Unholy Light': 'Тёмный свет',
    'Upgrade': 'Улучшение',
    'Vacuum Wave': 'Вакуумная волна',
    'Violent Belch': 'Ярая отрыжка',
    'Volcano': 'Вулкан',
    'Water': 'Вода',
    'Water II': 'Вода II',
    'Water II!': 'Вода II!',
    'Water Surge': 'Водный всплеск',
    'Whirling Blade': 'Вихрь клинка',
    'Whirling Kick': 'Вихревой удар',
    'Whirlwind': 'Вихрь',
    'Wild Blaze': 'Дикое пламя',
    'Wind Slash': 'Ветряной разрез',
    'Wind Waltz': 'Вальс ветра',
    'Wing Blow': 'Удар крылом',
    'Wing Flap': 'Взмах крыльев',
    'X-Strike': 'Х-Удар',
    'Yah!': 'Йа-а!',
    'Yakra Rage': 'Ярость Якры',
    'Yakra Rumble': 'Грохот Якры',
    'ÊLa La LaÊ': '«Ля-ля-ля»',
}

STATUS_MAP = {
    "/ Sleep": "/ Сон",
    "/ Poison": "/ Яд",
    "/ Blind": "/ Слепота",
    "/ Confuse": "/ Смятение",
    "/ Stop": "/ Стоп",
    "/ Slow": "/ Замедление",
    "/ Chaos": "/ Хаос",
    "/ Instant KO": "/ Смерть",
    "/ Halves HP": "/ ОЗ -50%",
    "/ Absorbs HP": "/ Поглощ. ОЗ",
    "/ Absorbs MP": "/ Кража ОМ",
    "/ Locks Techs": "/ Блок техник",
    "/ Lock": "/ Блок техник",
    "/ Sets HP to 1": "/ ОЗ до 1",
    "/ 1 HP damage": "/ Урон 1 ОЗ",
    "/ Restores HP": "/ Восст. ОЗ",
    "/ Sets MP to 0": "/ ОМ до 0",
    "/ Ult. magic": "/ Высш. магия",
    "/ Ult. attack": "/ Высш. атака",
    "/ Inflicts": "/ Наложение",
    "/ Voids immunities": "/ Снятие защит",
    "/ Brings boulder": "/ Валун",
    "/ Omnilock": "/ Полный блок",
    "/ Knockback": "/ Отбрасывание",
    "/ Arm revives": "/ Рука оживает",
    "/ Revives Pods": "/ Коконы",
    "/ Revives": "/ Возрождение",
    "/ Cancels": "/ Отмена",
    "/ Raises": "/ Повышение",
    "/ Ally": "/ Союзник",
    "/ Enemy": "/ Враг",
    "/ Sets": "/ Наложение",
}

HEADER_MAP = {
    "Counters:": "Контратаки:",
    "Combos:": "Комбо:",
    "Combo Counters:": "Комбо-контратаки:",
    "None": "Нет",
}

def translate_monsters_file():
    p_mon = AI_MSG_DIR / "big/monster.json"
    with open(p_mon, "r", encoding="utf-8") as f:
        data = json.load(f)
    changed = 0
    for item in data:
        orig = item.get("original_en", "").strip()
        if not orig or orig == "???":
            continue
        if orig in MONSTERS_DICT:
            item["translation"] = MONSTERS_DICT[orig]
            changed += 1
    with open(p_mon, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Updated big/monster.json ({changed} translated)")

def translate_sfc_mon_file():
    p_sfc = AI_MSG_DIR / "small/sfc_mon.json"
    p_mon = AI_MSG_DIR / "big/monster.json"
    with open(p_sfc, "r", encoding="utf-8") as f:
        sfc_data = json.load(f)
    with open(p_mon, "r", encoding="utf-8") as f:
        mon_data = json.load(f)
    changed = 0
    for i, item in enumerate(sfc_data):
        orig = item.get("original_en", "").strip()
        if not orig or orig == "???":
            continue
        if i == 205:
            item["translation"] = "Лавос"
            changed += 1
        elif i < len(mon_data) and mon_data[i].get("translation"):
            item["translation"] = mon_data[i]["translation"]
            changed += 1
        elif orig in MONSTERS_DICT:
            item["translation"] = MONSTERS_DICT[orig]
            changed += 1
    with open(p_sfc, "w", encoding="utf-8") as f:
        json.dump(sfc_data, f, ensure_ascii=False, indent=2)
    print(f"Updated small/sfc_mon.json ({changed} translated)")

def translate_ex_mon_file():
    p_ex = AI_MSG_DIR / "big/ex_mon.json"
    with open(p_ex, "r", encoding="utf-8") as f:
        data = json.load(f)
    changed = 0
    for item in data:
        orig = item.get("original_en", "").strip()
        if not orig or orig == "???":
            continue
        if orig in MONSTERS_DICT:
            item["translation"] = MONSTERS_DICT[orig]
            changed += 1
    with open(p_ex, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Updated big/ex_mon.json ({changed} translated)")

def translate_wireless_mon_files():
    p_w1 = AI_MSG_DIR / "big/wireless_mon.json"
    p_w2 = AI_MSG_DIR / "big/wireless_mon2.json"
    with open(p_w1, "r", encoding="utf-8") as f:
        w1_data = json.load(f)
    with open(p_w2, "r", encoding="utf-8") as f:
        w2_data = json.load(f)
    for item in w1_data:
        orig = item.get("original_en", "").strip()
        if not orig:
            continue
        if orig in MONSTERS_DICT:
            item["translation"] = MONSTERS_DICT[orig]
    for item in w2_data:
        orig = item.get("original_en", "").strip()
        if not orig:
            continue
        cap = orig.title()
        if cap in MONSTERS_DICT:
            item["translation"] = MONSTERS_DICT[cap].lower()
        elif orig in MONSTERS_DICT:
            item["translation"] = MONSTERS_DICT[orig].lower()
    with open(p_w1, "w", encoding="utf-8") as f:
        json.dump(w1_data, f, ensure_ascii=False, indent=2)
    with open(p_w2, "w", encoding="utf-8") as f:
        json.dump(w2_data, f, ensure_ascii=False, indent=2)
    print("Updated wireless_mon.json & wireless_mon2.json")

def translate_mon_tec_file():
    p_tec = AI_MSG_DIR / "big/mon_tec.json"
    with open(p_tec, "r", encoding="utf-8") as f:
        data = json.load(f)
    changed = 0
    for item in data:
        orig = item.get("original_en", "").strip()
        if not orig:
            continue
        if orig in MON_TEC_MAP:
            item["translation"] = MON_TEC_MAP[orig]
            changed += 1
    with open(p_tec, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Updated big/mon_tec.json ({changed} translated)")

def translate_wireless_tec_file():
    p_wtec = AI_MSG_DIR / "big/wireless_tec.json"
    with open(p_wtec, "r", encoding="utf-8") as f:
        data = json.load(f)
    changed = 0
    for item in data:
        orig = item.get("original_en", "").strip()
        if not orig:
            continue
        if orig in MON_TEC_MAP:
            item["translation"] = MON_TEC_MAP[orig]
            changed += 1
        elif orig in W_TEC_EXTRA:
            item["translation"] = W_TEC_EXTRA[orig]
            changed += 1
        elif orig in EX_BASE_TECHS:
            item["translation"] = EX_BASE_TECHS[orig]
            changed += 1
    with open(p_wtec, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Updated big/wireless_tec.json ({changed} translated)")

def translate_ex_montec_file():
    p_tec = AI_MSG_DIR / "big/ex_montec.json"
    with open(p_tec, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    specific_multi_lines = {
        "Punch\n - Hammer Punch /\n{TAG:38}{TAG:70}Knockback\n - Rolling Attack": "Удар кулаком\n - Удар молотом /\n{TAG:38}{TAG:70}Отбрасывание\n - Вращат. атака",
        "Rolling Attack\n - Crimson Rain\n - Hammer Punch /\n{TAG:38}{TAG:70}Knockback": "Вращат. атака\n - Алый дождь\n - Удар молотом /\n{TAG:38}{TAG:70}Отбрасывание",
        "Sobat\n - Chakram\n - Combo Attack / Sets\n{TAG:38}{TAG:70}HP to 1": "Собат\n - Чакрам\n - Серия атак /\n{TAG:38}{TAG:70}ОЗ до 1",
        "Hidden Needles\n - Absorb Energy /\n{TAG:38}{TAG:70}Absorbs HP\n - Supersonic Wave / Sleep": "Тайные иглы\n - Поглощ. энергии /\n{TAG:38}{TAG:70}Поглощ. ОЗ\n - Ультразвук / Сон",
        "Needle Spin Ver. XIII\n{TAG:38}{TAG:70}Barrage": "Вихрь игл XIII\n{TAG:38}{TAG:70}Шквал",
        "Lavos Spawn Needle\n{TAG:38}{TAG:70}Barrage": "Игла Порождения\n{TAG:38}{TAG:70}Шквал",
        "Evil Emanation / Raises\n{TAG:38}{TAG:70}Attack": "Зловещ. сияние /\n{TAG:38}{TAG:70}Атака +",
        "Life Grip / Arm revives\n{TAG:38}{TAG:70}body": "Хватка жизни /\n{TAG:38}{TAG:70}Оживление тела",
        "Diabolic Whisper / Inflicts\n{TAG:38}{TAG:70}random status": "Шёпот дьявола /\n{TAG:38}{TAG:70}Случайный статус",
        "Death's Rainbow /\n{TAG:38}{TAG:70}Instant KO": "Радуга смерти /\n{TAG:38}{TAG:70}Смерть",
        "Permeate / Cancels\n{TAG:38}{TAG:70}status immunity": "Просачивание /\n{TAG:38}{TAG:70}Снятие защит",
    }
    
    glyphs = ['»', '«', 'œ', 'Œ', '©']

    for item in data:
        orig = item.get("original_en", "")
        if not orig.strip():
            continue
        
        # Replace specific multi-line blocks first if present
        text = orig
        for sk, sv in specific_multi_lines.items():
            text = text.replace(sk, sv)
        
        lines = text.split("\n")
        new_lines = []
        for line in lines:
            trimmed = line.strip()
            if trimmed in HEADER_MAP:
                new_lines.append(HEADER_MAP[trimmed])
            elif trimmed.startswith("- "):
                content = trimmed[2:].strip()
                # Check if it already got translated by specific_multi_lines
                if any(c in 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя' for c in content):
                    new_lines.append(line)
                    continue
                
                # Split status if any
                parts = content.split(" / ")
                atk_part = parts[0].strip()
                
                # Extract elemental glyph
                glyph_suffix = ""
                for g in glyphs:
                    if atk_part.endswith(g):
                        glyph_suffix = " " + g
                        atk_part = atk_part[:-1].strip()
                        break
                
                # Translate attack name
                if atk_part in EX_BASE_TECHS:
                    atk_part = EX_BASE_TECHS[atk_part]
                elif atk_part in MON_TEC_MAP:
                    atk_part = MON_TEC_MAP[atk_part]
                elif atk_part in W_TEC_EXTRA:
                    atk_part = W_TEC_EXTRA[atk_part]
                
                atk_part = atk_part + glyph_suffix
                
                if len(parts) > 1:
                    status_part = " / " + parts[1].strip()
                    for sk, sv in STATUS_MAP.items():
                        if sk in status_part:
                            status_part = status_part.replace(sk, sv)
                    new_lines.append(" - " + atk_part + status_part)
                else:
                    new_lines.append(" - " + atk_part)
            else:
                # Other non-bullet lines
                tr_line = line
                for sk, sv in specific_multi_lines.items():
                    tr_line = tr_line.replace(sk, sv)
                for sk, sv in HEADER_MAP.items():
                    tr_line = tr_line.replace(sk, sv)
                new_lines.append(tr_line)
        item["translation"] = "\n".join(new_lines)
    
    with open(p_tec, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Updated big/ex_montec.json")

def main():
    translate_monsters_file()
    translate_sfc_mon_file()
    translate_ex_mon_file()
    translate_wireless_mon_files()
    translate_mon_tec_file()
    translate_wireless_tec_file()
    translate_ex_montec_file()
    print("All monster & tech files successfully translated!")

if __name__ == "__main__":
    main()
