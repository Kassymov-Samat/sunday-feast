# -*- coding: utf-8 -*-
"""Разбор меню и закупов за 2023–2026 из папки C:\\projects\\блюда.

Возвращает:
  occurrences — приготовления блюд: {name, file, sheet, guests, items: [(продукт, кол-во, цена, единица)]}
  prices      — цены: [(файл, продукт, цена, кол-во, единица)]

Форматы разные, поэтому для каждого листа задано: что в нём (блюда / только цены / пропустить)
и на сколько гостей готовили (из названия файла, числа тарелок или строки «количество взрослых»).
"""
import re
from pathlib import Path

import openpyxl
import xlrd

SRC = Path(r"C:\projects\блюда")


def num(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or "").replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
    try:
        return float(s)
    except ValueError:
        return None


def text(v):
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip()


def load_rows(path):
    """{лист: [[ячейки], ...]} для xls и xlsx."""
    out = {}
    if path.suffix == ".xls":
        wb = xlrd.open_workbook(str(path))
        for sh in wb.sheets():
            out[sh.name] = [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]
    else:
        wb = openpyxl.load_workbook(path, data_only=True)
        for ws in wb.worksheets:
            out[ws.title] = [list(r) for r in ws.iter_rows(values_only=True)]
    return out


# Строки-разделы: после них блюд нет (специи, хозчасть, расходы) или блюда не для гостей (обед севакам)
STOP = re.compile(r"^(специи|дополнительные расходы|доп закуп|хоз ?часть|хоз товары|прочие расходы|разное|"
                  r"обед севакам|фрукты для алтаря|абхишека|операционные расходы)", re.I)
TOTAL = re.compile(r"^итого", re.I)
SKIP_DISH = re.compile(r"^(специи)?$", re.I)
NOT_FOOD = re.compile(r"посуда|фольга|вафельн|бензин|^газ$|пакет|стакан|тарелк|ложк|контейнер|^вода", re.I)
GUESTS_LINE = re.compile(r"обед на (\d+) чел", re.I)

# (файл, лист): режим, гости. Режимы: dishes — блюда и цены, prices — только цены, skip
SHEETS = {
    "(Полный список)закуп 06 04 25.xlsx": {"Лист1": ("prices2", None)},
    "16.04.23 200 чел.xlsx": {"меню": ("dishes", 200)},
    "20241013_ВП.xlsx": {"список на готовку": ("dishes", 150)},  # одноразовых тарелок 150
    "20250202_список на Уход Карабхаджаны пр (1).xls": {"Готовка": ("dishes", 300)},  # тарелок 300
    "20250406_раманавами.xls": {"Готовка": ("dishes", 200), "Список на закуп": ("prices", None)},  # тарелок 200 в закупе 06.04.25
    "20251026_Уход Прабхупады (1).xlsx": {"Джанмаштами": ("dishes", 1000), "Прабхупада": ("dishes", 500),
                                          "Уход Прабхупады": ("dishes", 400)},  # по числу тарелок
    "20260322_Джапа ретрит (1).xlsx": {"*": ("dishes", None), "Свод меню": ("skip", None),
                                       "Продукты": ("prices", None), "Специи": ("prices", None)},
    "21.05.23. 300 чел.xlsx": {"меню": ("dishes", 300)},
    "25 января-воскреска.xlsx": {"Лист1": ("dishes", 200)},  # то же меню, что «РусЦАЯ 25 01 26 на 200 чел»
    "menu_200_final.xlsx": {"Закупка": ("dishes", 200), "Список продуктов": ("prices", None), "Свод": ("skip", None)},
    "Закуп  РусЦАЯ 25 01 26 на 200 чел.xlsx": {"*": ("prices", None)},
    "Закуп 26 01 25 на 200 чел.xlsx": {"Продукты": ("prices", None), "Меню": ("skip", None)},
    "Новый_год_итоговый_200чел (1) (1).xlsx": {"Новый год": ("dishes", 200)},
    "Нрисимха чатурдаши.xlsx": {"04,10": ("dishes", 300), "Список для закупа": ("prices", None)},  # стаканов 300
    "Пир_на_150_человек (1).xlsx": {"Лист1": ("dishes", 150), "Список продуктов": ("skip", None)},
    "Пир_на_150_человек.xlsx": {"Лист1": ("dishes", 150), "Список продуктов": ("skip", None)},
    "апрель-воскреска-2025.xls": {"Лист1": ("dishes", 200), "Лист2": ("prices_fixed", None)},  # посуды 200
    "закуп 20240915_Радхаштами.xlsx": {"Закуп Радхаштами": ("prices", None), "список на готовку": ("dishes", 400)},
    "меню 12 04 26 ГА.xlsx": {"Закуп": ("prices_ga", None), "Меню": ("ga", None)},
    "меню 5 03 26 ГА.xlsx": {"Sheet1": ("ga", None), "Лист1": ("skip", None)},
    "редакция 3 Закуп Нрисимха 26 05 24  на 500чел.xlsx": {"Лист1": ("prices", None), "Лист2": ("dishes", 500)},
}

# Блюда, записанные текстом (лист «Меню» в «Закуп 26 01 25 на 200 чел»)
MANUAL = [
    ("Закуп 26 01 25 на 200 чел.xlsx", "Рис", 200, [("рис баракат", 25)]),
    ("Закуп 26 01 25 на 200 чел.xlsx", "Дал", 200, [("горох", 4), ("морковь", 4), ("помидоры", 4), ("болгарский перец", 4)]),
    ("Закуп 26 01 25 на 200 чел.xlsx", "Сабджи с капустой", 200, [("картофель", 25), ("капуста белокочанная", 20), ("петрушка", 1)]),
    ("Закуп 26 01 25 на 200 чел.xlsx", "Банановое ласси", 200, [("кефир", 30), ("бананы кг", 20)]),
]


def find_header(row):
    """Колонки блока по строке заголовка: [(имя, кол-во, цена), ...] — блоков может быть два рядом."""
    cells = [text(c).lower() for c in row]
    blocks = []
    for i, c in enumerate(cells):
        if re.match(r"^(наименование|наимнование|продукт|ингредиент)", c):
            q = next((j for j in range(i + 1, min(i + 5, len(cells))) if re.match(r"^(кол|общий вес)", cells[j])), None)
            p = next((j for j in range(i + 1, min(i + 6, len(cells))) if cells[j].startswith("цена")), None)
            u = next((j for j in range(i + 1, min(i + 4, len(cells))) if cells[j].startswith("ед")), None)
            if q is not None:
                blocks.append((i, q, p, u))
    return blocks


def parse_block_sheet(rows, guests, fname, sheet, occ, prices, dishes=True):
    blocks, cur, meal_guests, stopped = None, {}, guests, False
    for row in rows:
        row = list(row) + [None] * 12
        first = text(row[0]).lower()
        if first.startswith("количество взрослых"):
            meal_guests = num(row[2]) or num(row[1])
            continue
        if first in ("завтрак", "обед", "ужин"):
            cur, stopped = {}, False
            continue
        head = " ".join(text(c) for c in row[:2]).strip().lower()
        m = GUESTS_LINE.search(head)
        if m:
            meal_guests, stopped, cur = int(m.group(1)), False, {}
            continue
        if blocks and STOP.match(text(row[0]).lower()) and not text(row[1]):
            stopped, cur = True, {}
            continue
        hb = find_header(row)
        if hb:
            if blocks and len(hb) < len(blocks):
                hb = [hb[0]] + blocks[1:]
            blocks = hb
            continue
        if not blocks:
            continue
        for bi, (ci, qi, pi, ui) in enumerate(blocks):
            name = text(row[ci])
            if not name:
                if any(num(c) for c in row[ci + 1:ci + 5]):
                    cur[bi] = None  # строка суммы — блюдо закончилось
                continue
            low = name.lower()
            m = GUESTS_LINE.search(low)
            if m:
                meal_guests, stopped, cur[bi] = int(m.group(1)), False, None
                continue
            if STOP.match(low):
                stopped, cur[bi] = True, None
                continue
            if TOTAL.match(low):
                cur[bi] = None
                continue
            q, p = num(row[qi]), num(row[pi]) if pi is not None else None
            if (not q and p is None) or (q is None and isinstance(row[qi], str) and row[qi].strip()):
                # заголовок блюда: «1 | Гречка», «10 | Напиток | 0», «2 | Матар панир | количество | цена»
                numbered = ci == 0 or num(row[ci - 1]) is not None
                if dishes and not stopped and (numbered or cur.get(bi) is None):
                    nm = re.sub(r"^\d+\.\s*", "", name).rstrip(" +").strip()
                    if SKIP_DISH.match(nm):
                        stopped, cur[bi] = True, None
                        continue
                    d = {"name": nm, "file": fname, "sheet": sheet, "guests": meal_guests, "items": []}
                    occ.append(d)
                    cur[bi] = d
                continue
            if q is None and p is not None and num(row[ci - 1] if ci else None) is not None and dishes and not stopped:
                # «4 | Гречка с овощами | | | 64,396» — заголовок с суммой
                continue
            unit = text(row[ui]).lower() if ui is not None else ""
            if p and p > 0:
                prices.append((fname, name, p, q, unit))
            if q and cur.get(bi) is not None and not NOT_FOOD.search(low):
                cur[bi]["items"].append((name, q, p, unit))


def parse_ga(rows, fname, sheet, occ, prices):
    """Листы «меню … ГА»: «Блюдо | кол-во | размер | Цена | Сумма | | людей | порция | сумма», ниже продукты.
    Число гостей стоит либо в строке заголовка, либо в первой строке продуктов (колонка «людей»)."""
    cur = None
    for row in rows:
        row = list(row) + [None] * 10
        a, b = text(row[0]), text(row[1]).lower()
        if not a:
            continue
        q, p, people = num(row[1]), num(row[3]), num(row[6])
        if b == "кол-во" or (q is None and people):
            cur = {"name": a, "file": fname, "sheet": sheet, "guests": people, "items": []}
            occ.append(cur)
            continue
        if a.lower().startswith("вода"):
            continue
        if q is None:
            cur = None  # «Хлеб», «макороны» — без раскладки
            continue
        if cur is not None and not cur["guests"] and people:
            cur["guests"] = people
        if p:
            prices.append((fname, a, p, q, ""))
        if cur is not None and not NOT_FOOD.search(a.lower()):
            cur["items"].append((a, q, p, ""))


def load_history():
    occ, prices = [], []
    for f in sorted(SRC.iterdir()):
        cfg = SHEETS.get(f.name)
        if cfg is None:
            print("!! нет настройки для", f.name)
            continue
        for sheet, rows in load_rows(f).items():
            mode, guests = cfg.get(sheet, cfg.get("*", ("skip", None)))
            if mode == "skip":
                continue
            if mode in ("dishes", "prices"):
                parse_block_sheet(rows, guests, f.name, sheet, occ, prices, dishes=(mode == "dishes"))
            elif mode == "prices2":  # план | факт: берём фактическую цену, если есть
                for r in rows:
                    r = list(r) + [None] * 9
                    n = text(r[0])
                    if n and not n.lower().startswith("наименование"):
                        p = num(r[6]) or num(r[2])
                        q = num(r[5]) or num(r[1])
                        if p:
                            prices.append((f.name, n, p, q, ""))
            elif mode == "prices_fixed":
                for r in rows:
                    r = list(r) + [None] * 5
                    if text(r[1]) and num(r[3]):
                        prices.append((f.name, text(r[1]), num(r[3]), num(r[2]), ""))
            elif mode == "prices_ga":
                for r in rows:
                    r = list(r) + [None] * 8
                    if text(r[0]) and num(r[6]):
                        prices.append((f.name, text(r[0]), num(r[6]), num(r[4]), text(r[5]).lower()))
            elif mode == "ga":
                parse_ga(rows, f.name, sheet, occ, prices)
    for fname, name, guests, items in MANUAL:
        occ.append({"name": name, "file": fname, "sheet": "Меню", "guests": guests, "items": [(n, q, None, "") for n, q in items]})
    occ = [o for o in occ if o["items"]]
    return occ, prices


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    occ, prices = load_history()
    for o in occ:
        print(f"[{o['file'][:28]} / {o['sheet']} / {o['guests']}] {o['name']}: " + "; ".join(f"{n}={q:g}{u and ' ' + u}" for n, q, _, u in o["items"]))
    print("\nблюд-приготовлений:", len(occ), "| цен:", len(prices))
