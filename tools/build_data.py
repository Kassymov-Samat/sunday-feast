# -*- coding: utf-8 -*-
"""Собирает данные сайта из файла ретрита и таблиц закупа:

    data/catalog.js — справочник продуктов, специй и хоз. части (раздел, единица, цена, откуда цена)
    data/dishes.js  — справочник блюд: продукты НА ОДНОГО ГОСТЯ (из «Меню на Майский ретрит»)

    python tools/build_data.py
"""
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_retreat import load, num  # noqa: E402
from price_sources import OCT, SEP  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BUTTER_PRICE = 3500  # гхи делаем сами из сливочного масла; средняя цена

# Разделы = вкладки в Google Docs
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
    "paneer": ("Панир", "кг", DAIRY, ["панир"]),
    "chechil": ("Сыр копчёный (чечил)", "кг", DAIRY, ["сыр копченный чечел"]),
    "milk_powder": ("Сухое молоко", "кг", DAIRY, ["сухое молоко"]),
    "milk_powder_gulab": ("Сухое молоко для гулабов", "кг", DAIRY, ["сухое молоко для гулабов"]),
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
    "peking": ("Капуста пекинская", "кг", VEG, ["пекинская капуста"]),
    "broccoli": ("Брокколи", "кг", VEG, ["брокколи"]),
    "zucchini": ("Кабачки", "кг", VEG, ["кабачки"]),
    "eggplant": ("Баклажаны", "кг", VEG, ["баклажаны"]),
    "pumpkin": ("Тыква", "кг", VEG, ["тыква"]),
    "radish": ("Редиска", "кг", VEG, ["редиска"]),
    "spinach": ("Шпинат", "кг", VEG, ["шпинат кг", "шпинат свежий кг"]),
    "iceberg": ("Салат айсберг", "кг", VEG, ["салат айсберг кг"]),
    "lettuce": ("Листья салата", "кг", VEG, ["листья салата кг"]),
    "dill": ("Укроп", "кг", VEG, ["укроп кг"]),
    "cilantro": ("Кинза", "кг", VEG, ["кинза свежая кг"]),
    "basil": ("Базилик", "кг", VEG, ["базилик свежий кг"]),
    "ginger": ("Имбирь свежий", "кг", VEG, ["имбирь свежий кг"]),
    "chili": ("Перец чили зелёный", "кг", VEG, ["чили зеленый свежий"]),
    "lemon": ("Лимоны", "шт", VEG, ["лимоны шт"]),
    "apple": ("Яблоки", "кг", VEG, ["яблоки"]),
    "banana": ("Бананы", "шт", VEG, ["бананы шт"]),
    "mandarin": ("Мандарины", "кг", VEG, ["мандарины"]),
    "pear": ("Груши", "кг", VEG, ["груши"]),
    "grape": ("Виноград", "кг", VEG, ["виноград"]),
    "orange": ("Апельсины", "кг", VEG, ["апельсины"]),
    "strawberry": ("Клубника", "кг", VEG, ["клубника свежая"]),
    "currant": ("Смородина чёрная замороженная", "кг", VEG, ["смородина черная замороженная"]),
    "peas_frozen": ("Горошек зелёный замороженный", "кг", VEG, ["горошек зеленый мороженный кг"]),
    "beans_green": ("Фасоль стручковая замороженная", "кг", VEG, ["фасоль стручковая мороженная кг", "стручковая фасоль (мороженная)"]),
    # ── бакалея ──
    "rice_barakat": ("Рис баракат", "кг", GROCERY, ["рис баракат"]),
    "rice_basmati": ("Рис басмати", "кг", GROCERY, ["рис басмати"]),
    "rice_alanga": ("Рис аланга (для плова)", "кг", GROCERY, ["рис аланга (для плова)"]),
    "buckwheat": ("Гречка", "кг", GROCERY, ["гречка"]),
    "millet": ("Пшено", "кг", GROCERY, ["пшенка кг"]),
    "quinoa": ("Киноа", "кг", GROCERY, ["киноа"]),
    "corn_grits": ("Крупа кукурузная", "кг", GROCERY, ["крупа кукурузная"]),
    "oats": ("Овсянка", "кг", GROCERY, ["овсянка"]),
    "five_grains": ("Каша «5 злаков»", "кг", GROCERY, ["5 злаков кг"]),
    "semolina": ("Манка", "кг", GROCERY, ["манка"]),
    "pasta": ("Рожки (макароны)", "кг", GROCERY, ["рожки кг"]),
    "flour": ("Мука 1 сорт", "кг", GROCERY, ["мука 1 сорт"]),
    "flour_rye": ("Мука ржаная", "кг", GROCERY, ["мука ржаная"]),
    "flour_whole": ("Мука цельнозерновая", "кг", GROCERY, ["мука цельнозерновая"]),
    "besan": ("Мука нутовая", "кг", GROCERY, ["нутовая мука"]),
    "starch": ("Крахмал кукурузный", "кг", GROCERY, ["крахмал кукурузный"]),
    "chickpeas": ("Нут", "кг", GROCERY, ["нут"]),
    "peas_split": ("Горох колотый", "кг", GROCERY, ["горох колотый"]),
    "lentil": ("Чечевица жёлтая", "кг", GROCERY, ["желтая чечевица"]),
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
    "dates": ("Финики", "пачка", GROCERY, ["финики пачка"]),
    "compote": ("Компотная смесь (сухофрукты)", "кг", GROCERY, ["компотная смесь"]),
    "soda": ("Сода", "пачка", GROCERY, ["сода пачка"]),
    "vanillin": ("Ванилин (банка 0,5 кг)", "банка", GROCERY, ["ванилин 0,5 кг банка"]),
    "citric": ("Лимонная кислота", "кг", GROCERY, ["лимонная кислота кг"]),
    "starter": ("Закваска (стартер)", "кг", GROCERY, ["стартер"]),
    "malt": ("Солод", "кг", GROCERY, ["солод"]),
    "lavash": ("Лаваш (пачка 100 шт)", "пачка", GROCERY, ["лаваш пачка 100 шт"]),
    "chicory": ("Цикорий", "кг", GROCERY, ["цикорий кг"]),
    "tea_herb": ("Трава для чая", "кг", GROCERY, ["трава для чая кг"]),
    "karkade": ("Каркаде", "кг", GROCERY, ["каркаде кг"]),
    "rosehip": ("Шиповник", "кг", GROCERY, ["шиповник"]),
    "thyme": ("Чебрец", "кг", GROCERY, ["чебрец кг"]),
    "colors": ("Красители пищевые", "шт", GROCERY, ["красители (карсный, синий, желтый, зеленый)"]),
    # ── остальное ──
    "mineral": ("Минеральная вода с газом", "л", OTHER, ["минеральная вода с газом литр"]),
}

# Специи: ключ: (название, единица, ставка упаковок на 100 гостей за один приём пищи — считается ниже,
#                [варианты в файле], по умолчанию в списке)
SPICES = {
    "asafoetida": ("Асафетида (100 г)", "пачка", ["асафетида 100 гр"], True),
    "cumin_seeds": ("Кумин (зира) в зёрнах, 100 г", "пачка", ["кумин в зернах 100гр"], True),
    "cumin_ground": ("Кумин молотый, 100 г", "пачка", ["кумин молотый 100гр"], True),
    "coriander": ("Кориандр молотый, 100 г", "пачка", ["кориандр молотый 100гр"], True),
    "turmeric": ("Куркума, 100 г", "пачка", ["куркума 100гр"], True),
    "garam": ("Гарам масала", "пачка", ["гарам массала"], True),
    "sambar": ("Самбар масала", "пачка", ["самбер массала"], False),
    "black_pepper": ("Перец чёрный молотый, 100 г", "пачка", ["черный перец молотый 100гр"], True),
    "salt": ("Соль (1 кг)", "пачка", ["соль 1 кг"], True),
    "bay_leaf": ("Лавровый лист (50 г)", "пачка", ["лавровый лист 50 гр"], True),
    "fennel": ("Фенхель, 100 г", "пачка", ["фенхель 100гр"], False),
    "cinnamon": ("Корица молотая, 100 г", "пачка", ["корица молотая 100гр"], False),
    "cinnamon_sticks": ("Корица палочки, 100 г", "пачка", ["корица палочки 100гр"], False),
    "cloves": ("Гвоздика", "пачка", ["гвоздика палочками"], False),
    "cardamom": ("Кардамон (не молотый)", "пачка", ["кардамон не молотый"], False),
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
    "петрушка": None, "помидоры": "tomato", "морковь": "carrot", "морковь желтая": "carrot_yellow",
    "имбирь свежий": "ginger", "лимоны": "lemon", "перец болгарский": "pepper_bell", "масло сливочное": "butter",
    "сметана": "smetana", "брынза": None, "горох колотый": "peas_split", "гречка": "buckwheat",
    "рис баракат": "rice_barakat", "горошек зеленый замороженный": "peas_frozen", "сахарная пудра": "sugar_powder",
    "сахар": "sugar", "грецкий орех чищенный": "walnut", "нутовая мука": "besan", "кокосовая стружка": "coconut",
    "рис басмати": "rice_basmati", "нут": "chickpeas", "масло подсолнечное": "oil", "сухое молоко": "milk_powder",
    "сода": "soda", "том паста": "tomato_paste", "миндаль": "almond", "кешью": "cashew", "чили зеленый": "chili",
    "капуста белокочанная": "cabbage", "шпинат свежий": "spinach", "бананы": None, "яблоки": "apple",
    "виноград": "grape", "груши": "pear", "молоко": "milk",
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


def norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower().replace("ё", "е"))


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

    # ── майские цены: лист «Продукты» (+ специи и инвентарь там же) и строки блюд ──
    may = {}
    for r in wb["Продукты"].iter_rows(values_only=True):
        name, price = norm(r[0]), num(r[2]) if len(r) > 2 else None
        if name and price:
            may[name] = price
    for r in wb["Специи"].iter_rows(values_only=True):
        name, price = norm(r[1]), num(r[3]) if len(r) > 3 else None
        if name and price:
            may[name] = price

    # ── блюда ──
    unknown = defaultdict(int)
    meal_people = {}
    for d in dishes_raw:
        if d["people"] is None and d["day"] == "9 мая":
            d["people"] = 430  # в листе не указано — как в остальные дни
        if d["meal"] in ("Завтрак", "Обед"):
            meal_people[(d["day"], d["meal"])] = d["people"]

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

    def category(name):
        n = name.lower()
        for cat, words in [("Каши", ["каша", "овсянка"]), ("Супы", ["суп", "окрошка", "самбар"]),
                           ("Салаты и нарезки", ["салат", "нарезка", "овощи в дорогу"]),
                           ("Сабджи и вторые блюда", ["сабджи", "панир", "плов", "рис", "гречка", "макарон", "паста", "фасоль", "паровые", "драники"]),
                           ("Хлеб и выпечка", ["хлеб", "булочка", "шарлотка", "манник", "кекс", "бисквит", "синабон", "пирожки", "чебуреки", "лаваш"]),
                           ("Закуски", ["пакоры", "дахивады"]), ("Соусы и подливки", ["подливка", "соус"]),
                           ("Сладости", ["халава", "помадка", "бурфи", "баларам", "чудо", "гопалы"]),
                           ("Напитки", ["напиток", "компот", "цикорий"]), ("Фрукты", ["фрукты"])]:
            if any(w in n for w in words):
                return cat
        return "Другое"

    dishes = {}
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
        key = norm(name)
        cand = {"name": name, "tags": tags, "category": category(name), "meal": d["meal"],
                "source": f"{d['day']}, {d['meal'].lower()}, на {int(d['people'])} чел.", "people": d["people"],
                "products": {k: round(v, 5) for k, v in prods.items()}, "spices": {k: round(v, 6) for k, v in spices.items()}}
        # повторы блюда: берём вариант с бо́льшим числом гостей (расчёт точнее)
        if key not in dishes or cand["people"] > dishes[key]["people"]:
            dishes[key] = cand
    dish_list = []
    for i, d in enumerate(sorted(dishes.values(), key=lambda d: (d["category"], d["name"]))):
        d["id"] = f"d{i + 1}"
        d.pop("people")
        dish_list.append(d)

    # ── цены ──
    def price_for(key, names):
        src_oct = {PRICE_ALIASES.get(k): v for k, v in OCT.items() if PRICE_ALIASES.get(k)}
        src_sep = {PRICE_ALIASES.get(k): v for k, v in SEP.items() if PRICE_ALIASES.get(k)}
        if key == "butter":
            return BUTTER_PRICE, "окт 2026"
        if key in src_oct:
            return src_oct[key][0], "окт 2026"
        if key in src_sep:
            return src_sep[key][0], "сен 2026"
        for n in names:
            if norm(n) in may:
                return round(may[norm(n)]), "май 2026"
        return None, ""

    catalog = {}
    for key, (name, unit, sect, names) in PRODUCTS.items():
        p, src = price_for(key, names)
        catalog[key] = {"name": name, "unit": unit, "section": sect, "price": p, "price_src": src}

    # специи: сколько упаковок на 100 гостей за приём пищи — по итогам закупа ретрита
    person_meals = sum(v for v in meal_people.values() if v) or 1
    spice_totals = {}
    for r in wb["Специи"].iter_rows(values_only=True):
        n, q = norm(r[1]), num(r[2]) if len(r) > 2 else None
        if n and q:
            spice_totals[n] = q
    for key, (name, unit, names, default) in SPICES.items():
        p, src = price_for(key, names)
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
        p, src = price_for(key, [])
        if p is None and key in house_names and house_may.get(norm(house_names[key])):
            p, src = round(house_may[norm(house_names[key])]), "май 2026"
        catalog[key] = {"name": name, "unit": unit, "section": HOUSE, "price": p, "price_src": src,
                        "per_guest": per_guest, "default": default}

    # ── запись ──
    (ROOT / "data").mkdir(exist_ok=True)
    head = "// Сгенерировано tools/build_data.py из «20260502_Меню на Майский ретрит.xlsx» и таблиц закупа.\n"
    (ROOT / "data" / "catalog.js").write_text(
        head + "// section — раздел (вкладка в Google Docs); price — за единицу; price_src — откуда цена.\n"
        "window.CATALOG = " + json.dumps(catalog, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    (ROOT / "data" / "dishes.js").write_text(
        head + "// Справочник блюд: products/spices — количество НА ОДНОГО ГОСТЯ (в единицах из catalog.js).\n"
        "// source — откуда взят расчёт (день и приём пищи ретрита).\n"
        "window.DISHES = " + json.dumps(dish_list, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    return dish_list, catalog, unknown, person_meals


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    dishes, catalog, unknown, pm = build()
    print("блюд:", len(dishes), "| продуктов/специй/хоз:", len(catalog), "| гостей-приёмов на ретрите:", pm)
    print("не распознаны:", dict(unknown))
    cats = defaultdict(list)
    for d in dishes:
        cats[d["category"]].append(d["name"] + (f" [{', '.join(d['tags'])}]" if d["tags"] else ""))
    for c, ns in cats.items():
        print(f"{c} ({len(ns)}): " + "; ".join(ns))
    print("\nбез цены:", [v["name"] for v in catalog.values() if not v["price"]])
    print("цены мая:", [v["name"] for v in catalog.values() if v["price_src"] == "май 2026" and v["section"] == "Овощи и фрукты"])
