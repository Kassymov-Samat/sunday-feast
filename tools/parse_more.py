# -*- coding: utf-8 -*-
"""Разбор дополнительных меню и закупов (без ручной настройки по листам):

  • C:\\projects\\sunday-feast\\пир\\готовка — копия   — меню 2025–2026 (в т.ч. «Список на готовку» с ценами);
  • C:\\projects\\блюда\\архив-drive                 — архив Google Drive 2011–2019 («список на …»).

Формат почти везде один: «№ | Наименование | количество | цена | итого», строка с номером — блюдо,
ниже продукты, пустая строка с суммой — конец блюда. В меню 2026 блюдо стоит в колонке «№ / блюдо»
(«1. Сабджи …»), продукты — в колонке «Ингредиент».

Число гостей ищется в файле: «Количество гостей», «на N чел», порции в меню («300 шт»),
одноразовая посуда / тарелки. Не нашли — блюдо берём без раскладки (только название).

Файлы, которые уже разобраны в parse_history (папка «блюда») и майский ретрит, пропускаются.
Цены берутся только из файлов 2025–2026 года (старые цены неактуальны), с датой — для сезонных цен.
"""
import re
from collections import Counter
from datetime import date
from pathlib import Path

from parse_history import NOT_FOOD, STOP, TOTAL, load_rows, num, text

DIRS = [Path(r"C:\projects\sunday-feast\пир\готовка — копия"), Path(r"C:\projects\блюда\архив-drive")]
KNOWN = Path(r"C:\projects\блюда")
SKIP_FILES = {"20260502_меню на майский ретрит.xlsx"}

HEAD_NAME = re.compile(r"^(наименование|наимнование|продукт|ингредиент|name$)", re.I)
HEAD_QTY = re.compile(r"^(кол|к-во|общий вес|quantity)", re.I)
HEAD_PRICE = re.compile(r"^(цена|price)", re.I)
HEAD_DISH = re.compile(r"^(№ ?/ ?блюдо|блюдо)", re.I)
GUESTS_RX = [re.compile(r"количество (гостей|человек|взрослых)", re.I)]
PER_RX = re.compile(r"на (\d{2,4}) ?(чел|гост|персон)", re.I)
PORTIONS = re.compile(r"^(\d{2,4}) ?(шт|порц)", re.I)
DISHES_WORDS = re.compile(r"одноразов\w* посуд|ком\.? одноразов|тарелк", re.I)


def norm_file(n):
    n = n.lower().replace("ё", "е")
    n = re.sub(r"\s*\(\d+\)", "", n)
    return re.sub(r"\s+", " ", n).strip()


def file_date(path):
    m = re.match(r"(20\d{2})(\d{2})(\d{2})", path.name)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return date(y, mo, d)
        except ValueError:
            return date(y, mo, 1)
    m = re.search(r"\b(20\d{2})\b", str(path.parent.name))
    return date(int(m.group(1)), 1, 1) if m else None


def guess_guests(sheets, fname):
    """Число гостей по всему файлу: явное → «на N чел» → порции в меню → одноразовая посуда."""
    m = PER_RX.search(fname)
    if m:
        return int(m.group(1)), "в названии файла"
    portions, plates = [], []
    for rows in sheets.values():
        for row in rows:
            cells = [text(c) for c in row[:10]]
            low = [c.lower() for c in cells]
            for i, c in enumerate(low):
                if any(r.search(c) for r in GUESTS_RX):
                    for v in row[i + 1:i + 4]:
                        if num(v) and 10 <= num(v) <= 3000:
                            return int(num(v)), "«количество гостей»"
                m = PER_RX.search(c)
                if m and 10 <= int(m.group(1)) <= 3000:
                    return int(m.group(1)), f"«{cells[i][:40]}»"
                m = PORTIONS.match(c)
                if m and i > 0 and cells[i - 1] and not num(cells[i - 1]):
                    portions.append(int(m.group(1)))
                if DISHES_WORDS.search(c):
                    for v in row[i + 1:i + 3]:
                        if num(v) and 30 <= num(v) <= 3000:
                            plates.append(int(num(v)))
                            break
    if portions:
        return Counter(portions).most_common(1)[0][0], "порции в меню"
    if plates:
        return max(plates), "одноразовая посуда"
    return None, ""


def find_cols(row):
    cells = [text(c).lower() for c in row]
    for i, c in enumerate(cells):
        if HEAD_NAME.match(c):
            q = next((j for j in range(i + 1, min(i + 5, len(cells))) if HEAD_QTY.match(cells[j])), None)
            if q is None:
                continue
            p = next((j for j in range(i + 1, min(i + 6, len(cells))) if HEAD_PRICE.match(cells[j])), None)
            u = next((j for j in range(i + 1, min(i + 6, len(cells))) if cells[j].startswith("ед")), None)
            d = i - 1 if i and (HEAD_DISH.match(cells[i - 1]) or cells[i - 1] in ("№", "#")) else None
            return i, q, p, u, d
    return None


def parse_sheet(rows, guests, fname, sheet, occ, prices, when):
    cols, cur, stopped = None, None, False
    for row in rows:
        row = list(row) + [None] * 12
        c = find_cols(row)
        if c:
            cols, cur, stopped = c, None, False
            continue
        if not cols:
            continue
        ni, qi, pi, ui, di = cols
        name = text(row[ni])
        lead = text(row[di]) if di is not None else ""
        # меню 2026: «1. Сабджи …» в колонке «№ / блюдо», колонка ингредиента пустая
        if not name and lead and not num(lead) and not any(num(v) for v in row[ni:ni + 4]):
            if STOP.match(lead.lower()) or TOTAL.match(lead.lower()):
                stopped, cur = True, None
                continue
            cur = {"name": re.sub(r"^\d+[.)]\s*", "", lead).strip(), "file": fname, "sheet": sheet,
                   "guests": guests, "items": [], "date": when}
            occ.append(cur)
            stopped = False
            continue
        if not name:
            if any(num(v) for v in row[ni + 1:ni + 5]):
                cur = None  # строка суммы — блюдо закончилось
            continue
        low = name.lower()
        if STOP.match(low):
            stopped, cur = True, None
            continue
        if TOTAL.match(low):
            cur = None
            continue
        q, p = num(row[qi]), (num(row[pi]) if pi is not None else None)
        unit = text(row[ui]).lower() if ui is not None else ""
        numbered = di is not None and num(row[di]) is not None
        if q is None and p is None and not text(row[qi]):
            # заголовок блюда: «1 | Рис» (номер слева) или первая строка после суммы
            if not stopped and (numbered or cur is None):
                cur = {"name": re.sub(r"^\d+[.)]\s*", "", name).rstrip(" +").strip(), "file": fname, "sheet": sheet,
                       "guests": guests, "items": [], "date": when}
                occ.append(cur)
            continue
        if p and p > 0 and when and when.year >= 2025:
            prices.append((fname, name, p, q, unit, when))
        if q and cur is not None and not NOT_FOOD.search(low):
            cur["items"].append((name, q, p, unit))


def load_more(verbose=False):
    known = {norm_file(f.name) for f in KNOWN.iterdir() if f.is_file()} | SKIP_FILES
    occ, prices, report = [], [], []
    files = sorted(f for d in DIRS if d.exists() for f in d.rglob("*") if f.suffix.lower() in (".xls", ".xlsx"))
    seen = set()
    for f in files:
        key = norm_file(f.name)
        if key in known or key in seen:
            continue
        seen.add(key)
        try:
            sheets = load_rows(f)
        except Exception as e:  # битый файл
            report.append((f.name, None, f"не открылся: {e}"))
            continue
        guests, how = guess_guests(sheets, f.name)
        when = file_date(f)
        n0 = len(occ)
        for sheet, rows in sheets.items():
            parse_sheet(rows, guests, f.name, sheet, occ, prices, when)
        # одно блюдо в файле встречается на нескольких листах (меню + раскладка) — оставляем вариант с составом
        best = {}
        for o in occ[n0:]:
            k = o["name"].lower()
            if k not in best or len(o["items"]) > len(best[k]["items"]):
                best[k] = o
        occ[n0:] = list(best.values())
        report.append((f.name, guests, how))
    return occ, prices, report


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    occ, prices, report = load_more()
    for fn, g, how in report:
        print(f"{fn[:60]:60} гостей: {g} ({how})")
    print()
    for o in occ:
        print(f"[{o['file'][:30]} / {o['sheet'][:14]} / {o['guests']}] {o['name']}: "
              + "; ".join(f"{n}={q:g}" for n, q, _, _ in o["items"]))
    print("\nблюд:", len(occ), "| с составом:", sum(1 for o in occ if o["items"]), "| цен 2025–26:", len(prices))
