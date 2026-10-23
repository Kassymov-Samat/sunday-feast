# -*- coding: utf-8 -*-
"""Собирает данные сайта из меню и закупов:

    data/catalog.js — справочник продуктов, специй и хоз. части (раздел, единица, цена, откуда цена)
    data/dishes.js  — справочник блюд: продукты НА ОДНОГО ГОСТЯ

Источники:
  • «20260502_Меню на Майский ретрит.xlsx» (parse_retreat.py);
  • меню и закупы за 2023–2026 из папки C:\\projects\\блюда (parse_history.py);
  • таблицы закупа за сентябрь и октябрь 2026 (price_sources.py).

Одно и то же блюдо, записанное по-разному («Дымляма»/«дамляма», «Гулабы»/«Гулабджамуны»), собирается в одно.
Раскладка на гостя: по каждому продукту — медиана по всем приготовлениям; состав — как в самом
типичном приготовлении. Цена: майский ретрит, если там её нет — среднее по всем файлам (без выбросов).

    python tools/build_data.py
"""
import json
import math
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_history import load_history  # noqa: E402
from parse_retreat import load, num  # noqa: E402
from price_sources import OCT, SEP  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
IDS_FILE = Path(__file__).parent / "dish_ids.json"
BUTTER_PRICE = 3500  # гхи делаем сами из сливочного масла; средняя цена

# Разделы = вкладки в Google Таблице
DAIRY, GROCERY, VEG, OTHER, SPICE, HOUSE = "Молочка", "Бакалея", "Овощи и фрукты", "Остальное", "Специи", "Хоз. часть"

# ключ: (название, единица, раздел, [варианты написания в файле ретрита])
PRODUCTS = {
    # ── молочка ──
    "butter": ("Масло сливочное", "кг", DAIRY, ["масло сливочное"]),
    "milk": ("Молоко", "л", DAIRY, ["молоко"]),
    "kefir": ("Кефир 2,5%", "л", DAIRY, ["кефир 2.5%"]),
    "ryazhenka": ("Ряженка", "л", DAIRY, ["ряженка"]),
    "smetana": ("Сметана", "кг", DAIRY, ["сметана"]),
    "cream": ("Сливки 20%", "л", DAIRY, ["сливки 20%"]),
    "tvorog": ("Творог", "кг", DAIRY, ["творог"]),
    "paneer": ("Панир / брынза", "кг", DAIRY, ["панир"]),
    "chechil": ("Сыр копчёный (чечил)", "кг", DAIRY, ["сыр копченный чечел"]),
    "milk_powder": ("Сухое молоко", "кг", GROCERY, ["сухое молоко"]),
    "milk_powder_gulab": ("Сухое молоко для гулабов", "кг", GROCERY, ["сухое молоко для гулабов"]),
    "condensed": ("Сгущёнка", "кг", DAIRY, ["сгущенка кг"]),
    "condensed_boiled": ("Сгущёнка варёная", "кг", DAIRY, ["варенная сгущенка кг", "сгущенка вареная кг"]),
    "whey": ("Сыворотка молочная", "л", DAIRY, ["сыворотка молочная"]),
    # ── овощи, фрукты, зелень ──
    "potato": ("Картофель", "кг", VEG, ["картофель"]),
    "carrot": ("Морковь", "кг", VEG, ["морковь"]),
    "carrot_yellow": ("Морковь жёлтая", "кг", VEG, ["морковь желтая"]),
    "tomato": ("Помидоры", "кг", VEG, ["помидоры"]),
    "cherry": ("Помидоры черри", "кг", VEG, ["помидоры черри"]),
    "cucumber": ("Огурцы", "кг", VEG, ["огурцы"]),
    "pepper_bell": ("Перец болгарский", "кг", VEG, ["болгарский перец"]),
    "cauliflower": ("Капуста цветная", "кг", VEG, ["цветная капуста"]),
    "cabbage": ("Капуста белокочанная", "кг", VEG, ["капуста"]),
    "sauerkraut": ("Капуста квашеная", "кг", VEG, []),
    "peking": ("Капуста пекинская", "кг", VEG, ["пекинская капуста"]),
    "broccoli": ("Брокколи", "кг", VEG, ["брокколи"]),
    "zucchini": ("Кабачки", "кг", VEG, ["кабачки"]),
    "eggplant": ("Баклажаны", "кг", VEG, ["баклажаны"]),
    "pumpkin": ("Тыква", "кг", VEG, ["тыква"]),
    "beet": ("Свёкла", "кг", VEG, ["свекла"]),
    "radish": ("Редиска", "кг", VEG, ["редиска"]),
    "spinach": ("Шпинат", "кг", VEG, ["шпинат кг", "шпинат свежий кг"]),
    "iceberg": ("Салат айсберг", "кг", VEG, ["салат айсберг кг"]),
    "lettuce": ("Листья салата", "кг", VEG, ["листья салата кг"]),
    "dill": ("Укроп", "кг", VEG, ["укроп кг"]),
    "parsley": ("Петрушка", "кг", VEG, []),
    "cilantro": ("Кинза", "кг", VEG, ["кинза свежая кг"]),
    "basil": ("Базилик", "кг", VEG, ["базилик свежий кг"]),
    "mint": ("Мята свежая", "кг", VEG, []),
    "ginger": ("Имбирь свежий", "кг", VEG, ["имбирь свежий кг"]),
    "chili": ("Перец чили зелёный", "кг", VEG, ["чили зеленый свежий"]),
    "lemon": ("Лимоны", "шт", VEG, ["лимоны шт"]),
    "apple": ("Яблоки", "кг", VEG, ["яблоки"]),
    "banana": ("Бананы", "шт", VEG, ["бананы шт"]),
    "mandarin": ("Мандарины", "кг", VEG, ["мандарины"]),
    "pear": ("Груши", "кг", VEG, ["груши"]),
    "grape": ("Виноград", "кг", VEG, ["виноград"]),
    "orange": ("Апельсины", "кг", VEG, ["апельсины"]),
    "plum": ("Слива", "кг", VEG, []),
    "apricot": ("Абрикосы", "кг", VEG, []),
    "nectarine": ("Нектарины / персики", "кг", VEG, []),
    "strawberry": ("Клубника (свежая или замороженная)", "кг", VEG, ["клубника свежая"]),
    "currant": ("Смородина чёрная замороженная", "кг", VEG, ["смородина черная замороженная"]),
    "currant_red": ("Смородина красная замороженная", "кг", VEG, []),
    "raspberry": ("Малина замороженная", "кг", VEG, []),
    "cherry_frozen": ("Вишня замороженная", "кг", VEG, []),
    "peas_frozen": ("Горошек зелёный замороженный", "кг", VEG, ["горошек зеленый мороженный кг"]),
    "beans_green": ("Фасоль стручковая замороженная", "кг", VEG, ["фасоль стручковая мороженная кг", "стручковая фасоль (мороженная)"]),
    # ── бакалея ──
    "rice_barakat": ("Рис круглый (баракат, краснодарский)", "кг", GROCERY, ["рис баракат"]),
    "rice_basmati": ("Рис басмати", "кг", GROCERY, ["рис басмати"]),
    "rice_alanga": ("Рис для плова (аланга, лазер)", "кг", GROCERY, ["рис аланга (для плова)"]),
    "buckwheat": ("Гречка", "кг", GROCERY, ["гречка"]),
    "millet": ("Пшено", "кг", GROCERY, ["пшенка кг"]),
    "quinoa": ("Киноа", "кг", GROCERY, ["киноа"]),
    "corn_grits": ("Крупа кукурузная", "кг", GROCERY, ["крупа кукурузная"]),
    "oats": ("Овсянка (геркулес)", "кг", GROCERY, ["овсянка"]),
    "five_grains": ("Каша «5 злаков»", "кг", GROCERY, ["5 злаков кг"]),
    "semolina": ("Манка", "кг", GROCERY, ["манка"]),
    "pasta": ("Рожки (макароны)", "кг", GROCERY, ["рожки кг"]),
    "flour": ("Мука (в/с или 1 сорт)", "кг", GROCERY, ["мука 1 сорт"]),
    "flour_rye": ("Мука ржаная", "кг", GROCERY, ["мука ржаная"]),
    "flour_whole": ("Мука цельнозерновая", "кг", GROCERY, ["мука цельнозерновая"]),
    "besan": ("Мука нутовая", "кг", GROCERY, ["нутовая мука"]),
    "starch": ("Крахмал кукурузный", "кг", GROCERY, ["крахмал кукурузный"]),
    "chickpeas": ("Нут", "кг", GROCERY, ["нут"]),
    "peas_split": ("Горох колотый", "кг", GROCERY, ["горох колотый"]),
    "lentil": ("Чечевица жёлтая", "кг", GROCERY, ["желтая чечевица"]),
    "mung": ("Маш", "кг", GROCERY, []),
    "urad": ("Урад дал", "кг", GROCERY, ["ураддал"]),
    "beans_red": ("Фасоль красная", "кг", GROCERY, ["фасоль красная кг"]),
    "soy": ("Соевый гуляш", "кг", GROCERY, ["соевый гуляш кг"]),
    "sugar": ("Сахар", "кг", GROCERY, ["сахар"]),
    "sugar_powder": ("Сахарная пудра", "кг", GROCERY, ["сахарная пудра"]),
    "honey": ("Мёд", "кг", GROCERY, ["мед кг"]),
    "oil": ("Масло подсолнечное", "л", GROCERY, ["масло подсолнечное"]),
    "oil_unref": ("Масло подсолнечное нерафинированное", "л", GROCERY, ["масло подсолнечное не рафинированное"]),
    "oil_corn": ("Масло кукурузное", "л", GROCERY, ["масло кукурузное"]),
    "tomato_paste": ("Томатная паста", "кг", GROCERY, ["том паста"]),
    "corn_can": ("Кукуруза консервированная (банка 400 г)", "шт", GROCERY, ["кукуруза банки 400 гр шт"]),
    "peas_can": ("Горошек консервированный (банка 400 г)", "шт", GROCERY, ["зел горошек (банка 400 гр шт)"]),
    "mayo": ("Майонез постный (без яиц)", "шт", GROCERY, []),
    "walnut": ("Грецкий орех чищеный", "кг", GROCERY, ["грецкий орех чищенный"]),
    "almond": ("Миндаль", "кг", GROCERY, ["миндаль"]),
    "cashew": ("Кешью", "кг", GROCERY, ["кешью"]),
    "hazelnut": ("Фундук", "кг", GROCERY, ["фундук"]),
    "peanut": ("Арахис", "кг", GROCERY, ["арахис"]),
    "sesame": ("Кунжут светлый", "кг", GROCERY, ["кунжут светлый"]),
    "sunflower_seeds": ("Семечки подсолнуха чищеные", "кг", GROCERY, ["семечки подсолнуха чищенные"]),
    "pumpkin_seeds": ("Семечки тыквенные чищеные", "кг", GROCERY, ["тыквенные семечки чищенные"]),
    "coconut": ("Кокосовая стружка", "кг", GROCERY, ["кокосовая стружка"]),
    "raisins_black": ("Изюм чёрный", "кг", GROCERY, ["изюм черный"]),
    "raisins_brown": ("Изюм коричневый", "кг", GROCERY, ["изюм коричневый"]),
    "raisins_yellow": ("Изюм жёлтый", "кг", GROCERY, ["изюм желтый"]),
    "kuraga": ("Курага", "кг", GROCERY, ["курага"]),
    "fig": ("Инжир сушёный", "кг", GROCERY, []),
    "dates": ("Финики", "пачка", GROCERY, ["финики пачка"]),
    "compote": ("Сухофрукты для компота", "кг", GROCERY, ["компотная смесь"]),
    "soda": ("Сода", "пачка", GROCERY, ["сода пачка"]),
    "yeast": ("Дрожжи (пачка)", "пачка", GROCERY, ["дрожжи пачка 400 гр"]),
    "vanillin": ("Ванилин (банка 0,5 кг)", "банка", GROCERY, ["ванилин 0,5 кг банка"]),
    "citric": ("Лимонная кислота", "кг", GROCERY, ["лимонная кислота кг"]),
    "starter": ("Закваска (стартер)", "кг", GROCERY, ["стартер"]),
    "malt": ("Солод", "кг", GROCERY, ["солод"]),
    "lavash": ("Лаваш (пачка 100 шт)", "пачка", GROCERY, ["лаваш пачка 100 шт"]),
    "nori": ("Листья нори (пачка)", "пачка", GROCERY, []),
    "chicory": ("Цикорий", "кг", GROCERY, ["цикорий кг"]),
    "tea_herb": ("Трава для чая", "кг", GROCERY, ["трава для чая кг"]),
    "ivan_tea": ("Иван-чай", "кг", GROCERY, []),
    "karkade": ("Каркаде", "кг", GROCERY, ["каркаде кг"]),
    "rosehip": ("Шиповник сушёный", "кг", GROCERY, ["шиповник"]),
    "rosehip_syrup": ("Сироп шиповника (бутылка)", "шт", GROCERY, []),
    "thyme": ("Чебрец", "кг", GROCERY, ["чебрец кг"]),
    "colors": ("Красители пищевые", "шт", GROCERY, ["красители (карсный, синий, желтый, зеленый)"]),
    # ── остальное ──
    "mineral": ("Минеральная вода с газом", "л", OTHER, ["минеральная вода с газом литр"]),
}

# Специи: ключ: (название, единица, [варианты в файле ретрита], по умолчанию в списке)
SPICES = {
    "asafoetida": ("Асафетида (100 г)", "пачка", ["асафетида 100 гр"], True),
    "cumin_seeds": ("Кумин (зира) в зёрнах, 100 г", "пачка", ["кумин в зернах 100гр"], True),
    "cumin_ground": ("Кумин молотый, 100 г", "пачка", ["кумин молотый 100гр"], True),
    "coriander": ("Кориандр молотый, 100 г", "пачка", ["кориандр молотый 100гр"], True),
    "turmeric": ("Куркума, 100 г", "пачка", ["куркума 100гр"], True),
    "garam": ("Гарам масала", "пачка", ["гарам массала"], True),
    "sambar": ("Самбар масала", "пачка", ["самбер массала"], False),
    "chana_masala": ("Чана масала", "пачка", [], False),
    "black_pepper": ("Перец чёрный молотый, 100 г", "пачка", ["черный перец молотый 100гр"], True),
    "chili_ground": ("Чили молотый, 100 г", "пачка", [], False),
    "ginger_ground": ("Имбирь молотый, 100 г", "пачка", [], False),
    "salt": ("Соль (1 кг)", "пачка", ["соль 1 кг"], True),
    "bay_leaf": ("Лавровый лист (50 г)", "пачка", ["лавровый лист 50 гр"], True),
    "fennel": ("Фенхель, 100 г", "пачка", ["фенхель 100гр"], False),
    "cinnamon": ("Корица молотая, 100 г", "пачка", ["корица молотая 100гр"], False),
    "cinnamon_sticks": ("Корица палочки, 100 г", "пачка", ["корица палочки 100гр"], False),
    "cloves": ("Гвоздика", "пачка", ["гвоздика палочками"], False),
    "cardamom": ("Кардамон (не молотый)", "пачка", ["кардамон не молотый"], False),
    "nutmeg": ("Мускатный орех, 100 г", "пачка", [], False),
    "saffron": ("Шафран (пачка 1 г)", "пачка", [], False),
    "star_anise": ("Бадьян", "кг", [], False),
    "mustard_black": ("Горчица чёрная (семена)", "пачка", ["черная горчица"], False),
    "mustard_yellow": ("Горчица жёлтая (семена)", "пачка", ["желтая горчица"], False),
    "fenugreek": ("Шамбала (семена)", "пачка", ["шамбала семена"], False),
    "kasuri_methi": ("Касури метхи (листья шамбалы)", "пачка", ["листья шамбалы (касури метхи)"], False),
    "paprika": ("Паприка красная сладкая", "кг", ["красная сладкая паприка кг"], False),
    "plov_spice": ("Специя для плова", "кг", ["специя для плова кг"], False),
    "barberry": ("Барбарис", "кг", ["барбарис"], False),
    "black_salt": ("Чёрная соль", "кг", ["черная соль кг"], False),
}

# Хоз. часть и посуда: (название, единица, на гостя? (шт на гостя) или фиксировано, по умолчанию в списке)
HOUSE_ITEMS = {
    "plates": ("Тарелки одноразовые", "шт", 1, True),
    "spoons": ("Ложки одноразовые", "шт", 1, True),
    "cups": ("Стаканы одноразовые", "шт", 1, True),
    "containers": ("Контейнеры одноразовые", "шт", 0, False),
    "containers_sweet": ("Контейнеры для сладостей 0,5 л", "шт", 0, False),
    "containers_2l": ("Контейнеры 2 л с крышкой", "шт", 0, False),
    "trash_150": ("Пакеты для мусора 150 л", "рулон", 0, True),
    "trash_240": ("Пакеты для мусора 240 л", "рулон", 0, False),
    "bags": ("Пакеты-майки", "рулон", 0, False),
    "dish_soap": ("Моющее средство для посуды", "шт", 0, True),
    "dish_soap_5l": ("Моющее средство 5 л", "шт", 0, False),
    "domestos": ("Доместос", "шт", 0, False),
    "comet": ("Комет", "шт", 0, False),
    "floor": ("Средство для пола (Мистер Пропер)", "шт", 0, False),
    "rags": ("Тряпки для стола", "пачка", 0, True),
    "sponges": ("Губки для посуды", "пачка", 0, True),
    "steel_brush": ("Железные щётки", "пачка", 0, False),
    "gloves": ("Перчатки резиновые толстые", "шт", 0, False),
    "gloves_disp": ("Перчатки одноразовые", "пачка", 0, False),
    "caps": ("Шапочки одноразовые", "пачка", 0, False),
    "napkins": ("Салфетки", "пачка", 0, False),
    "paper_towels": ("Бумажные полотенца", "шт", 0, False),
    "waffle": ("Вафельная ткань", "м", 0, False),
    "baking_paper": ("Бумага пекарская (рулон 100 м)", "рулон", 0, False),
    "film": ("Плёнка пищевая (большая)", "рулон", 0, False),
}

# Привязка названий из таблиц закупа (OCT/SEP) к ключам
PRICE_ALIASES = {
    "картофель": "potato", "цветная капуста": "cauliflower", "помидоры черри": "cherry", "кинза": "cilantro",
    "петрушка": "parsley", "помидоры": "tomato", "морковь": "carrot", "морковь желтая": "carrot_yellow",
    "имбирь свежий": "ginger", "лимоны": "lemon", "перец болгарский": "pepper_bell", "масло сливочное": "butter",
    "сметана": "smetana", "брынза": "paneer", "горох колотый": "peas_split", "гречка": "buckwheat",
    "рис баракат": "rice_barakat", "горошек зеленый замороженный": "peas_frozen", "сахарная пудра": "sugar_powder",
    "сахар": "sugar", "грецкий орех чищенный": "walnut", "нутовая мука": "besan", "кокосовая стружка": "coconut",
    "рис басмати": "rice_basmati", "нут": "chickpeas", "масло подсолнечное": "oil", "сухое молоко": "milk_powder",
    "сода": "soda", "том паста": "tomato_paste", "миндаль": "almond", "кешью": "cashew", "чили зеленый": "chili",
    "капуста белокочанная": "cabbage", "шпинат свежий": "spinach", "бананы": None, "яблоки": "apple",
    "виноград": "grape", "груши": "pear", "молоко": "milk", "мята": "mint",
    # специи
    "куркума": "turmeric", "асафетида": "asafoetida", "самбар масала": "sambar", "лавровый лист": "bay_leaf",
    "кумин в зернах": "cumin_seeds", "кориандр молотый": "coriander", "черный перец горошком": None,
    "корица молотая": None, "гарам масала": "garam", "кардамон": None, "соль": None,
    # хоз
    "тряпки для стола": "rags", "моющее средство для посуды": "dish_soap", "пакеты для мусора 150 л": "trash_150",
    "контейнеры одноразовые": "containers", "тарелки одноразовые": "plates", "ложки одноразовые": "spoons",
    "стаканы одноразовые": "cups", "пакеты для мусора 240 л": "trash_240", "пакеты майка": "bags",
    "доместос": "domestos", "бумажные полотенца": "paper_towels",
}

# Подписи мероприятий для «откуда расчёт»
EVENTS = {
    "16.04.23 200 чел.xlsx": "Гаура-пурнима 16.04.23",
    "20241013_ВП.xlsx": "Пир 13.10.24",
    "20250202_список на Уход Карабхаджаны пр (1).xls": "Уход Карабхаджаны 02.02.25",
    "20250406_раманавами.xls": "Рама-навами 06.04.25",
    "20251026_Уход Прабхупады (1).xlsx/Джанмаштами": "Джанмаштами 2025",
    "20251026_Уход Прабхупады (1).xlsx/Прабхупада": "Явление Прабхупады 2025",
    "20251026_Уход Прабхупады (1).xlsx/Уход Прабхупады": "Уход Прабхупады 26.10.25",
    "20260322_Джапа ретрит (1).xlsx": "Джапа-ретрит, {sheet}",
    "21.05.23. 300 чел.xlsx": "Пир 21.05.23",
    "25 января-воскреска.xlsx": "Воскресный пир 25.01.26",
    "menu_200_final.xlsx": "Меню на 200 чел. (июнь 2026)",
    "Закуп 26 01 25 на 200 чел.xlsx": "Пир 26.01.25",
    "Новый_год_итоговый_200чел (1) (1).xlsx": "Новый год",
    "Нрисимха чатурдаши.xlsx": "Нрисимха-чатурдаши",
    "Пир_на_150_человек (1).xlsx": "Пир на 150 чел. (вариант 1)",
    "Пир_на_150_человек.xlsx": "Пир на 150 чел.",
    "апрель-воскреска-2025.xls": "Воскресный пир 04.2025",
    "закуп 20240915_Радхаштами.xlsx": "Радхаштами 15.09.24",
    "меню 12 04 26 ГА.xlsx": "Меню 12.04.26",
    "меню 5 03 26 ГА.xlsx": "Меню 05.03.26",
    "редакция 3 Закуп Нрисимха 26 05 24  на 500чел.xlsx": "Нрисимха-чатурдаши 26.05.24",
}

# Блюда, которые уже добавили на сайте вручную: их версия главная, из файлов не дублируем
SITE_DISHES = {"Шак панир", "Чола", "Облепиховый напиток"}

DAIRY_KEYS = {k for k, v in PRODUCTS.items() if v[2] == DAIRY} | {"honey"}


def norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower().replace("ё", "е"))


# ── продукты: разные написания → ключ справочника и множитель к его единице ──
def _per_kg(n):  # «бананы кг» → штук: в кг примерно n штук
    return lambda raw, unit, price: n if ("кг" in raw or unit == "кг" or (price or 0) >= 500) else 1


def _jar(raw, unit, price):  # сметана банками по 700 г
    return 0.7 if ("700" in raw or "банка" in raw or unit == "шт") else 1


def _condensed(raw, unit, price):
    return 0.4 if "400" in raw else 0.75 if "деп" in raw else 1


def _lemon(raw, unit, price):  # лимоны в кг: ~8 шт в кг
    return 8 if unit == "кг" else 1


def _pack100(raw, unit, price):  # паприка пачками по 100 г → кг
    return 1 if "кг" in raw else 0.1


def _karkade(raw, unit, price):  # пачка каркаде ≈ 100 г
    return 0.1 if re.search(r"пач|пвч", raw) else 1


def _chili(raw, unit, price):  # перец острый стручками: ~20 г
    return 0.02 if (unit == "шт" or "стручк" in raw) else 1


def _cilantro(raw, unit, price):
    return 0.1 if "пуч" in unit else 1


ING_RULES = [
    (r"посуда|фольга|вафельн|бензин|^газ|пакет|стакан|тарелк|ложк|контейнер|^вода|соки|марля|ветошь|салфет|перчат"
     r"|отруби|карри|^гхи$|колбас|сосиск|^специи$|мусор|полотенц|тряпк|губк|моющ", None),
    (r"сухое молоко для гулаб", "milk_powder_gulab"),
    (r"сухое молоко|молоко сухое", "milk_powder"),
    (r"масло сливоч|для гхи|масло хорошее|сливочное масло", "butter"),
    (r"^масло$", lambda raw, unit, price: ("butter", 1) if (price or 0) >= 2000 else ("oil", 1)),
    (r"нерафин|не рафин|оливков", "oil_unref"),
    (r"кукурузн\w* масло|масло кукурузн", "oil_corn"),
    (r"масло|подсолне", "oil"),
    (r"сгущ\w* вар|вар\w* сгущ", "condensed_boiled"),
    (r"сгущ", ("condensed", _condensed)),
    (r"кефир", "kefir"), (r"ряженк", "ryazhenka"), (r"сливки", "cream"), (r"творог", "tvorog"),
    (r"см[яе]тана", ("smetana", _jar)), (r"брынза|панир", "paneer"), (r"сыворотк", "whey"), (r"чечел|чечил", "chechil"),
    (r"молоко", "milk"),
    (r"морковь желт", "carrot_yellow"), (r"морков|моковь", "carrot"),
    (r"картоф|картош", "potato"), (r"черри", "cherry"), (r"помидор", "tomato"), (r"огур", "cucumber"),
    (r"пекин", "peking"), (r"цвет\w* капуст|капуста цвет", "cauliflower"), (r"капуста кваш", "sauerkraut"),
    (r"капуст", "cabbage"), (r"брокколи", "broccoli"), (r"кабач", "zucchini"), (r"баклажан", "eggplant"),
    (r"тыкв(?!енн)", "pumpkin"), (r"свекл|свёкл", "beet"), (r"редис", "radish"), (r"шпинат", "spinach"),
    (r"айсберг", "iceberg"), (r"листья салата", "lettuce"), (r"укроп", "dill"), (r"петрушк", "parsley"),
    (r"кинза|^зелень", ("cilantro", _cilantro)), (r"базилик|райхон", "basil"), (r"мят", "mint"),
    (r"имбирь (молот|суш)", "ginger_ground"), (r"имбирь", "ginger"),
    (r"перец остр|острый перец|чили св|чили зел", ("chili", _chili)), (r"^чили$|чили молот", "chili_ground"),
    (r"перец черн|черный перец|чёрный перец", "black_pepper"),
    (r"перец|ласточк|светофор", "pepper_bell"),
    (r"джандо|фасоль стручк|стручковая фасоль|мфасоль", "beans_green"), (r"фасоль красн", "beans_red"),
    (r"банан", ("banana", _per_kg(5))), (r"лимон(?!н)", ("lemon", _lemon)), (r"апельсин", "orange"),
    (r"мандарин", "mandarin"), (r"груш", "pear"), (r"яблок", "apple"), (r"виноград", "grape"),
    (r"клубник", "strawberry"), (r"красн\w* смород|смород\w* красн", "currant_red"), (r"смород|сморонд", "currant"),
    (r"малин", "raspberry"), (r"вишн", "cherry_frozen"), (r"слив(?!оч|к)", "plum"), (r"нектарин|персик", "nectarine"),
    (r"облепих", "sea_buckthorn"), (r"абрикос", "apricot"), (r"инжир", "fig"), (r"курага", "kuraga"), (r"финик", "dates"),
    (r"изюм желт", "raisins_yellow"), (r"изюм черн", "raisins_black"), (r"изюм", "raisins_brown"),
    (r"компот|сухофрукт", "compote"), (r"кокос", "coconut"), (r"кешью|кещью", "cashew"),
    (r"миндал|мендаль", "almond"), (r"грецк", "walnut"), (r"фундук", "hazelnut"), (r"арахис", "peanut"),
    (r"кунжут", "sesame"), (r"семечки подсолн", "sunflower_seeds"), (r"тыквенн", "pumpkin_seeds"),
    (r"рис басмати|^басмати", "rice_basmati"), (r"рис лазер|рис аланга|для плова\)", "rice_alanga"),
    (r"^рис", "rice_barakat"), (r"гречк", "buckwheat"), (r"киноа", "quinoa"), (r"пшен", "millet"),
    (r"геркулес|овсян", "oats"), (r"5 злаков", "five_grains"), (r"манка", "semolina"), (r"рожки|макарон", "pasta"),
    (r"нутов\w* мук", "besan"), (r"мука ржан", "flour_rye"), (r"цельнозерн", "flour_whole"), (r"мука", "flour"),
    (r"горошек конс|горошек \(бан|зел горошек \(банка", "peas_can"),
    (r"горошек|горох\w* (свеж|мор|замор)|горох мор", "peas_frozen"),
    (r"горох", "peas_split"), (r"^нут$|^нут ", "chickpeas"), (r"^маш", "mung"), (r"урад", "urad"),
    (r"чечевиц", "lentil"), (r"соев", "soy"),
    (r"сахарн\w* пудр", "sugar_powder"), (r"сахар", "sugar"), (r"^м[её]д", "honey"),
    (r"томат\w* паст|том\w* паст", "tomato_paste"),
    (r"кукуруз\w* (в )?бан|кукуруза банк", "corn_can"), (r"сода", "soda"), (r"ванилин пачка 500|ванилин 0,5", "vanillin"),
    (r"дрожж", "yeast"), (r"нори", "nori"), (r"майонез", "mayo"), (r"каркад", ("karkade", _karkade)),
    (r"иван", "ivan_tea"), (r"трава для чая", "tea_herb"), (r"сироп шиповн", "rosehip_syrup"), (r"шиповник", "rosehip"),
    (r"чебрец", "thyme"), (r"цикори", "chicory"), (r"крахмал", "starch"), (r"стартер|закваск", "starter"),
    (r"солод", "malt"), (r"лаваш", "lavash"), (r"лимонная кислота", "citric"),
    # специи
    (r"бадьян", "star_anise"), (r"шафран", "saffron"), (r"мускат", "nutmeg"), (r"лавров", "bay_leaf"),
    (r"асафетид", "asafoetida"), (r"кумин молот", "cumin_ground"), (r"кумин|зира", "cumin_seeds"),
    (r"кориандр|кариандр", "coriander"), (r"куркум", "turmeric"), (r"гарам", "garam"), (r"самб[ае]р", "sambar"),
    (r"чана мас", "chana_masala"), (r"фенхел|фенхил", "fennel"), (r"корица палоч|корицы палоч|корица обяз", "cinnamon_sticks"),
    (r"корица", "cinnamon"), (r"гвоздик", "cloves"), (r"кардамон|кардомон", "cardamom"),
    (r"желтая горчица|горчица желт", "mustard_yellow"), (r"горчиц", "mustard_black"), (r"шамбал", "fenugreek"),
    (r"касури|кастори", "kasuri_methi"), (r"паприк", ("paprika", _pack100)), (r"спци|специя для плова", "plov_spice"),
    (r"барбарис", "barberry"), (r"черная соль", "black_salt"), (r"^соль", "salt"),
]
ING_RULES = [(re.compile(p), r) for p, r in ING_RULES]


def map_ing(raw, unit="", price=None):
    """(ключ, множитель к единице справочника) или None."""
    raw = re.sub(r"^\d+\.\s*", "", norm(raw))  # «1. Бананы 3-4 кг»
    for rx, rule in ING_RULES:
        if rx.search(raw):
            if rule is None:
                return None
            if callable(rule):
                return rule(raw, unit, price)
            if isinstance(rule, tuple):
                key, f = rule
                return key, (f(raw, unit, price) if callable(f) else f)
            return rule, 1
    return None


# ── блюда: разные названия одного блюда → одно название и раздел ──
def drink_name(k):
    if k <= {"sugar"}:
        return None  # «Напиток из яблок»: яблоки пожертвовали, в раскладке только сахар
    if "sea_buckthorn" in k or "облепих" in k:
        return "Облепиховый напиток"
    for need, name in [({"rosehip"}, "Напиток из шиповника"), ({"rosehip_syrup"}, "Напиток из шиповника"),
                       ({"ivan_tea"}, "Иван-чай"), ({"tea_herb"}, "Травяной чай"), ({"currant_red"}, "Смородиновый морс")]:
        if need & k:
            return name
    if "lemon" in k:
        return "Лимонно-имбирный напиток" if "ginger" in k else "Лимонный напиток с мятой" if "mint" in k else "Напиток лимонный"
    if "compote" in k:
        return "Компот"
    if "karkade" in k:
        return "Напиток из каркаде"
    return ""


def sabji_name(n, k):
    if "томат" in n or "красное" in n or {"tomato", "eggplant"} <= k:
        return "Сабджи в томатном соусе"
    if {"potato", "cauliflower"} <= k:
        return "Сабджи из картофеля и цветной капусты"
    if {"potato", "pumpkin"} <= k:
        return "Сабджи из картофеля и тыквы"
    if "cabbage" in k:
        return "Сабджи с капустой"
    if {"zucchini", "beans_green"} <= k:
        return "Сабджи из кабачков и стручковой фасоли"
    if {"zucchini", "potato"} <= k:
        return "Сабджи из кабачков и картофеля"
    return ""


def rice_name(k):
    if "rice_basmati" in k:
        return "Рис басмати с паниром и кешью" if {"paneer", "cashew"} & k else "Рис басмати"
    if {"almond", "peas_frozen", "corn_can"} & k:
        return "Пулау (рис с овощами)"
    return "Рис"


def salad_name(k):
    if {"cucumber", "tomato", "pepper_bell"} <= k:
        return "Салат из огурцов, помидоров и перца"
    if "peking" in k and "mayo" in k:
        return "Салат из пекинской капусты с кукурузой"
    if {"peking", "cucumber"} <= k:
        return "Салат из пекинской капусты с горошком"
    if {"peking", "tomato"} <= k:
        return "Салат из пекинской капусты с помидорами"
    return ""


SAL, SAB, SOUP, BREAD, SNACK, SWEET, DRINK, SAUCE, FRUIT, KASHA = (
    "Салаты и нарезки", "Сабджи и вторые блюда", "Супы и далы", "Хлеб и выпечка", "Закуски", "Сладости",
    "Напитки", "Соусы и подливки", "Фрукты", "Каши")

# (регулярное выражение по названию, новое название или функция(название, продукты), раздел или None)
DISH_RULES = [
    (r"^(напиток|лимонный напиток|компот|облепих)", lambda n, k: drink_name(k), DRINK),
    (r"^(сабджи|сабжи)( \d+)?$|^сабджи (красное|в томат|картофель и цвет|с карошкой|с капустой)|^сезонная овощная сабджи",
     sabji_name, SAB),
    (r"^дал( \+)?$", lambda n, k: "Мунг дал (из маша)" if "mung" in k else "Дал из гороха", SOUP),
    (r"^джаганн", "Джаганнатха дал", SOUP),
    (r"^рис( \+)?$|^рис баракат$|^рис басмати$", lambda n, k: rice_name(k), SAB),
    (r"^рис пушпан", "Рис пушпанна", SAB), (r"^пулау", "Пулау (рис с овощами)", SAB),
    (r"^плов$", "Плов овощной", SAB), (r"^(дымляма|дамляма)", "Дамляма", SAB),
    (r"^гречка$", "Гречка", SAB), (r"^гречка с овощ", "Гречка с овощами", SAB), (r"^киноа с овощ", "Киноа с овощами", SAB),
    (r"^матар панир", "Матар панир", SAB), (r"^картофель$", "Картофель с укропом", SAB),
    (r"^картофельное пюре", "Картофельное пюре", SAB), (r"^печеные овощи", "Печёные овощи", SAB),
    (r"^бринджал", "Бринджал (баклажаны с паниром)", SAB), (r"^махабриджал", "Махабриджал (баклажаны с нутом и шпинатом)", SAB),
    (r"^сабджи алу байган", "Алу байган (картофель с баклажанами)", SAB), (r"^милиджули", "Милиджули (овощи в сливках)", SAB),
    (r"^сабджи панир шак|^шак панир", "Шак панир", SAB), (r"^чола", "Чола", SAB),
    (r"^гауранга", "Гауранга (картофель с брынзой)", SAB), (r"^кичири|^кичри", "Кичри", SAB),
    (r"^баурсак", "Баурсаки", BREAD), (r"^пури", "Пури", BREAD), (r"^крекеры", "Крекеры", BREAD),
    (r"^выпечка$", "Выпечка с картофелем и тыквой", BREAD), (r"^пирожки со шпинат", "Пирожки со шпинатом и паниром", BREAD),
    (r"^пирог$", "Пирог с вишней", BREAD), (r"^манник", "Манник с изюмом", None), (r"^синабоны", "Синабоны", None),
    (r"^халава", "Халава", SWEET),
    (r"^(памадка|помадка)$", lambda n, k: "Молочная помадка с миндалём" if "milk_powder" in k else "Помадка", SWEET),
    (r"^помадка с кунжутом", "Кокосовое бурфи", SWEET), (r"^гулаб", "Гулабджамуны", SWEET),
    (r"^(ладду|ладу)$", "Ладду", SWEET), (r"^бунди", "Бунди ладду", SWEET), (r"^хворост", "Хворост", SWEET),
    (r"^кхир лауки", "Кхир лауки (с кабачком)", SWEET), (r"^кхир$|^сладкий рис", "Кхир (рисовый пудинг)", SWEET),
    (r"^сандеш", "Сандеш в финиках", SWEET), (r"^сухофрукты$", "Сухофрукты и орехи", SWEET),
    (r"шары", "Кокосовые шарики со сгущёнкой", SWEET), (r"^просто чудо", "Простое чудо", SWEET),
    (r"^дахивад", "Дахивады", SNACK), (r"^самосы сладк", "Самосы сладкие", SNACK), (r"^самосы", "Самосы", SNACK),
    (r"^(микс )?пакоры$", "Микс пакоры", SNACK), (r"^качори", "Качори", SNACK),
    (r"^салат$|^салат айчичук|^салат из пек капусты$", lambda n, k: salad_name(k), SAL),
    (r"^сладкий салат|^фруктовый салат", "Фруктовый салат", FRUIT), (r"^нарезка$", "Овощная нарезка", SAL),
    (r"^оливье", "Оливье вегетарианский", SAL), (r"^шуба", "Шуба вегетарианская (с нори)", SAL),
    (r"райта", "Райта огуречная", SAUCE), (r"^сливовое чатни", "Сливовое чатни", SAUCE),
    (r"^помидорное чатни", "Томатное чатни", SAUCE), (r"^сладкая подливка", "Сладкая яблочная подливка", SAUCE),
    (r"^подливка$", "Подливка", SAUCE),
    (r"^ласси$", "Ласси абрикосовое", DRINK), (r"^банановое ласси", "Банановое ласси", DRINK),
    (r"^молоко$", "Молоко тёплое", DRINK),
    (r"^каша$", lambda n, k: "Каша «5 злаков»" if "five_grains" in k else "Овсянка на молоке с изюмом", KASHA),
    (r"^фрукты$", "Фрукты", FRUIT), (r"^суп из нута", "Суп из нута", SOUP), (r"^шорпа", "Шорпа (суп из нута)", SOUP),
    (r"^суп уха", "Суп «уха» с нори и паниром", SOUP), (r"^творог$", "Творог со сметаной", "Другое"),
]
DISH_RULES = [(re.compile(p), r, c) for p, r, c in DISH_RULES]


def category(name):
    n = name.lower()
    for cat, words in [(KASHA, ["каша", "овсянка"]), (SOUP, ["суп", "окрошка", "самбар", "дал"]),
                       (SAL, ["салат", "нарезка", "овощи в дорогу"]),
                       (SAB, ["сабджи", "панир", "плов", "рис", "гречка", "макарон", "паста", "фасоль", "паровые", "драники"]),
                       (BREAD, ["хлеб", "булочка", "шарлотка", "манник", "кекс", "бисквит", "синабон", "пирожки", "чебуреки", "лаваш"]),
                       (SNACK, ["пакоры", "дахивады"]), (SAUCE, ["подливка", "соус"]),
                       (SWEET, ["халава", "помадка", "бурфи", "баларам", "чудо", "гопалы"]),
                       (DRINK, ["напиток", "компот", "цикорий"]), (FRUIT, ["фрукты"])]:
        if any(w in n for w in words):
            return cat
    return "Другое"


def canonical(name, keys):
    """(название, раздел) или None — блюдо не берём."""
    n = norm(name)
    for rx, rule, cat in DISH_RULES:
        if rx.search(n):
            new = rule(n, keys) if callable(rule) else rule
            if new is None:
                return None
            new = new or name
            return new, cat or category(new)
    return name, category(name)


# ── майский ретрит: блюда как раньше ──
def retreat_occurrences(dishes_raw, alias):
    def clean_name(n):
        tags = []
        low = n.lower()
        if "веган" in low:
            tags.append("веган")
        if "дет" in low:
            tags.append("для детей")
        if "ужин" in low:
            tags.append("на ужин")
        n = re.sub(r"\((?:[^()]*?(?:веган|дет|ужин)[^()]*?)\)", "", n, flags=re.I)
        n = re.sub(r"\s+", " ", n).strip()
        n = {"грецка": "Гречка", "памадка": "Помадка", "хлеб": "Хлеб ржаной", "каша": "Каша «5 злаков»",
             "салат": "Салат из помидоров со сметаной", "суп": "Суп овощной с паниром", "соус": "Соус из ряженки",
             "напиток": "Напиток травяной", "напиток травянной": "Напиток травяной", "напиток компот": "Компот",
             "рис": "Рис", "фасоль": "Фасоль красная с овощами",
             "салат из пек капусты": "Салат из пекинской капусты с горошком",
             "салат из пекинской капусты": "Салат из пекинской капусты со сметаной",
             "сосиска в тесте": "Картофель в лаваше", "чебурки": "Чебуреки с паниром",
             "бурфи": "Бурфи с фундуком"}.get(n.lower(), n)
        return n[:1].upper() + n[1:], tags

    occ, unknown = [], defaultdict(int)
    for d in dishes_raw:
        if d["people"] is None and d["day"] == "9 мая":
            d["people"] = 430  # в листе не указано — как в остальные дни
    for d in dishes_raw:
        if d["name"].lower().startswith(("пицца", "выпечка в дорогу")) or not d["items"] or not d["people"]:
            continue
        name, tags = clean_name(d["name"])
        prods, spices = defaultdict(float), defaultdict(float)
        for raw, q in d["items"]:
            if norm(raw).startswith("колбаса"):
                continue  # вегетарианское меню
            hit = alias.get(norm(raw))
            if not hit:
                unknown[raw] += 1
                continue
            kind, key = hit
            (spices if kind == "s" else prods)[key] += q / d["people"]
        occ.append({"name": name, "tags": tags, "meal": d["meal"], "may": True, "guests": d["people"],
                    "label": f"{d['day']}, {d['meal'].lower()}", "source": f"{d['day']}, {d['meal'].lower()}, на {int(d['people'])} чел.",
                    "products": dict(prods), "spices": dict(spices)})
    return occ, unknown


def history_occurrences():
    hist, prices = load_history()
    occ, unknown = [], defaultdict(int)
    for o in hist:
        if not o["guests"]:
            continue
        label = EVENTS.get(f"{o['file']}/{o['sheet']}") or EVENTS.get(o["file"], o["file"])
        label = label.replace("{sheet}", o["sheet"])
        prods, spices = defaultdict(float), defaultdict(float)
        for raw, q, p, unit in o["items"]:
            hit = map_ing(raw, unit, p)
            if not hit:
                if not ING_RULES[0][0].search(norm(raw)):
                    unknown[raw] += 1
                continue
            key, f = hit
            (spices if key in SPICES else prods)[key] += q * f / o["guests"]
        tags = ["веган"] if "веган" in o["name"].lower() else []
        if "ужин" in o["name"].lower():
            tags.append("на ужин")
        name = re.sub(r"\s*\((веган|на ужин)\)\s*", " ", o["name"], flags=re.I).strip()
        occ.append({"name": name[:1].upper() + name[1:], "tags": tags, "may": False, "guests": o["guests"],
                    "label": label, "source": f"{label}, на {int(o['guests'])} чел.",
                    "products": dict(prods), "spices": dict(spices)})
    return occ, prices, unknown


FATS = {"butter", "oil", "oil_corn", "oil_unref"}


def combine(group):
    """Раскладка блюда по нескольким приготовлениям.
    Состав — как в «опорном» приготовлении: для блюд майского ретрита — то, что было на сайте
    (приготовление на наибольшее число гостей), для новых — самое типичное из всех.
    Количество продукта, который есть больше чем в половине приготовлений, — медиана на гостя по ним.
    Продукты большинства, которых нет в опорном рецепте, добавляются (кроме второго вида масла).
    Если блюдо готовили только на ретрите (в разные дни), берётся опорное приготовление, как раньше."""
    if len(group) == 1:
        o = group[0]
        return dict(o["products"]), dict(o["spices"]), o
    n = len(group)
    cores = []
    for field in ("products", "spices"):
        vals = defaultdict(list)
        for o in group:
            for k, v in o[field].items():
                if v > 0:
                    vals[k].append(v)
        cores.append({k: statistics.median(v) for k, v in vals.items() if len(v) * 2 > n})
    pcore, score = cores

    def dist(o):
        d = sum(abs(math.log(o["products"][k] / m)) if o["products"].get(k) else 2.0 for k, m in pcore.items())
        return d + 0.3 * sum(1 for k in o["products"] if k not in pcore)

    may = [o for o in group if o.get("may")]
    anchor = max(may, key=lambda o: o["guests"]) if may else min(group, key=lambda o: (dist(o), -o["guests"]))
    if len(may) == n or group[0]["name"] in ("Фрукты", "Сухофрукты и орехи"):
        # повторы внутри ретрита — как раньше (приготовление на больше гостей); фрукты каждый раз разные
        return dict(anchor["products"]), dict(anchor["spices"]), anchor
    out = []
    for field, core in (("products", pcore), ("spices", score)):
        res = {k: core.get(k, v) for k, v in anchor[field].items()}
        has_fat = bool(FATS & set(res))
        for k, m in core.items():
            if k not in res and not (k in FATS and has_fat):
                res[k] = m
        out.append(res)
    return out[0], out[1], anchor


def build():
    dishes_raw, wb = load()
    alias = {}
    for key, (_, _, _, names) in PRODUCTS.items():
        for n in names:
            alias[norm(n)] = ("p", key)
    for key, (_, _, names, _) in SPICES.items():
        for n in names:
            alias[norm(n)] = ("s", key)
    alias[norm("кориандр молотый 100гр")] = ("s", "coriander")

    # ── майские цены: лист «Продукты» (+ специи и инвентарь там же) ──
    may_rows = []
    for r in wb["Продукты"].iter_rows(values_only=True):
        name, price = norm(r[0]), num(r[2]) if len(r) > 2 else None
        if name and price:
            may_rows.append((name, price))
    for r in wb["Специи"].iter_rows(values_only=True):
        name, price = norm(r[1]), num(r[3]) if len(r) > 3 else None
        if name and price:
            may_rows.append((name, price))
    may = defaultdict(list)
    for name, price in may_rows:
        hit = alias.get(name)
        key, f = (hit[1], 1) if hit else (map_ing(name, "", price) or (None, 1))
        if key:
            may[key].append(price / f)

    # ── все приготовления блюд ──
    occ, unknown = retreat_occurrences(dishes_raw, alias)
    hocc, hist_prices, hunknown = history_occurrences()
    for k, v in hunknown.items():
        unknown[k] += v
    meal_people = {}
    for d in dishes_raw:
        if d["meal"] in ("Завтрак", "Обед"):
            meal_people[(d["day"], d["meal"])] = d["people"]

    groups, cats, tags, skipped = defaultdict(list), {}, defaultdict(list), defaultdict(list)
    for o in occ + hocc:
        keys = set(o["products"]) | set(o["spices"])
        c = canonical(o["name"], keys)
        if c is None:
            continue
        name, cat = c
        if name in SITE_DISHES:
            skipped[name].append(o)
            continue
        groups[name].append(o)
        cats.setdefault(name, cat)
        for t in o["tags"]:
            if t not in tags[name]:
                tags[name].append(t)

    # ── id: прежние блюда сохраняют свои id (на них ссылаются правки на сайте и выбор у повара) ──
    ids = json.loads(IDS_FILE.read_text(encoding="utf-8")) if IDS_FILE.exists() else {}
    if not ids:
        old = (ROOT / "data" / "dishes.js").read_text(encoding="utf-8")
        for d in json.loads(old[old.index("["):old.rindex("]") + 1]):
            ids[d["name"]] = d["id"]
        for was, now in {"Напиток травяной": "Напиток из каркаде", "Сабджи": "Сабджи из картофеля и тыквы",
                         "Плов": "Плов овощной"}.items():
            ids[now] = ids.pop(was)
    nxt = max(int(v[1:]) for v in ids.values()) + 1
    for name in sorted(groups):
        if name not in ids:
            ids[name], nxt = f"d{nxt}", nxt + 1

    dish_list, report = [], []
    for name, group in groups.items():
        prods, spices, medoid = combine(group)
        if len(group) == 1 or all(o.get("may") for o in group):
            source = medoid["source"]
        else:
            source = f"среднее по {len(group)} приготовлениям: " + "; ".join(f"{o['label']} ({int(o['guests'])} чел.)" for o in group)
        meal = next((o["meal"] for o in group if o.get("meal")), "")
        dish_list.append({"name": name, "tags": tags[name], "category": cats[name], "meal": meal, "source": source,
                          "products": {k: round(v, 5) for k, v in prods.items()},
                          "spices": {k: round(v, 6) for k, v in spices.items()}, "id": ids[name]})
        report.append((name, group, prods))
    dish_list.sort(key=lambda d: (d["category"], d["name"]))
    IDS_FILE.write_text(json.dumps(ids, ensure_ascii=False, indent=1), encoding="utf-8")

    # ── цены: май → среднее по всем файлам (по каждому файлу своё среднее, выбросы отброшены) ──
    by_file = defaultdict(lambda: defaultdict(list))
    for fname, raw, p, q, unit in hist_prices:
        hit = map_ing(raw, unit, p)
        if hit and p > 0:
            key, f = hit
            if key == "karkade" and f != 1:
                continue  # пачки каркаде — цену за кг не посчитать
            by_file[key][fname].append(p / f)
    for src, table in (("Закуп 17.10.2026", OCT), ("Радхаштами 2026", SEP)):
        for k, (p, _) in table.items():
            key = PRICE_ALIASES.get(k)
            if key:
                by_file[key][src].append(p)

    def avg_price(key):
        vals = [statistics.mean(v) for v in by_file.get(key, {}).values()]
        if not vals:
            return None, 0
        m = statistics.median(vals)
        ok = [v for v in vals if m / 2 <= v <= m * 2]
        return statistics.mean(ok), len(ok)

    price_report = {}

    def price_for(key):
        avg, n = avg_price(key)
        price_report[key] = (may.get(key), avg, n)
        if key == "butter":
            return BUTTER_PRICE, "задано: 3 500"
        if may.get(key):
            return round(statistics.mean(may[key])), "май 2026"
        if avg:
            return int(round(avg, -1)), f"среднее по {n} файл." if n > 1 else "из 1 файла"
        return None, ""

    catalog = {}
    for key, (name, unit, sect, names) in PRODUCTS.items():
        p, src = price_for(key)
        catalog[key] = {"name": name, "unit": unit, "section": sect, "price": p, "price_src": src}

    # специи: сколько упаковок на 100 гостей за приём пищи — по итогам закупа ретрита
    person_meals = sum(v for v in meal_people.values() if v) or 1
    spice_totals = {}
    for r in wb["Специи"].iter_rows(values_only=True):
        n, q = norm(r[1]), num(r[2]) if len(r) > 2 else None
        if n and q:
            spice_totals[n] = q
    for key, (name, unit, names, default) in SPICES.items():
        p, src = price_for(key)
        total = sum(spice_totals.get(norm(n), 0) for n in names)
        catalog[key] = {"name": name, "unit": unit, "section": SPICE, "price": p, "price_src": src,
                        "per100": round(total / person_meals * 100, 4), "default": default}

    house_may = {norm(r[0]): num(r[2]) for r in wb["Продукты"].iter_rows(min_row=160, values_only=True) if r[0] and len(r) > 2}
    house_names = {"containers_sweet": "контейнера на сладостей 0.5 л", "containers_2l": "контейнера 2 л с крышкой",
                   "baking_paper": "бумага пекарская 100м рулон", "film": "пленка пищевая большая производственная",
                   "bags": "пакеты майчка рулон", "gloves": "резиновые перчатки толскые шт", "gloves_disp": "резиновые перчатки одноразовые пачка",
                   "sponges": "губки для посуды пачка", "steel_brush": "железные щетки пачка", "dish_soap_5l": "моющее средство 5 литров",
                   "comet": "комет", "floor": "мистер пропер для пола", "waffle": "вафельная ткань погонный метр",
                   "caps": "шапочки одноразовые", "napkins": "салфетки пачка"}
    for key, (name, unit, per_guest, default) in HOUSE_ITEMS.items():
        p, src = None, ""
        for label, table in (("окт 2026", OCT), ("сен 2026", SEP)):
            hit = next((v[0] for k, v in table.items() if PRICE_ALIASES.get(k) == key), None)
            if hit and p is None:
                p, src = hit, label
        if p is None and key in house_names and house_may.get(norm(house_names[key])):
            p, src = round(house_may[norm(house_names[key])]), "май 2026"
        catalog[key] = {"name": name, "unit": unit, "section": HOUSE, "price": p, "price_src": src,
                        "per_guest": per_guest, "default": default}

    # ── запись ──
    (ROOT / "data").mkdir(exist_ok=True)
    head = ("// Сгенерировано tools/build_data.py из «20260502_Меню на Майский ретрит.xlsx», меню и закупов 2023–2026\n"
            "// (папка «блюда») и таблиц закупа.\n")
    (ROOT / "data" / "catalog.js").write_text(
        head + "// section — раздел (вкладка в таблице); price — за единицу; price_src — откуда цена.\n"
        "window.CATALOG = " + json.dumps(catalog, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    (ROOT / "data" / "dishes.js").write_text(
        head + "// Справочник блюд: products/spices — количество НА ОДНОГО ГОСТЯ (в единицах из catalog.js).\n"
        "// source — откуда взят расчёт (мероприятие и число гостей; для нескольких — медиана).\n"
        "window.DISHES = " + json.dumps(dish_list, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    return {"dishes": dish_list, "catalog": catalog, "unknown": unknown, "report": report, "skipped": skipped,
            "prices": price_report, "by_file": by_file}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    res = build()
    dishes, catalog = res["dishes"], res["catalog"]
    print("блюд:", len(dishes), "| продуктов/специй/хоз:", len(catalog))
    print("не распознаны:", dict(res["unknown"]))
    cats = defaultdict(list)
    for d in dishes:
        cats[d["category"]].append(d["name"])
    for c, ns in cats.items():
        print(f"{c} ({len(ns)}): " + "; ".join(ns))
    print("\nбез цены:", [v["name"] for v in catalog.values() if not v["price"]])
    print("уже есть на сайте (не дублируем):", {k: len(v) for k, v in res["skipped"].items()})
