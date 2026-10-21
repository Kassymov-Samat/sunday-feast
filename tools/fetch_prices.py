# -*- coding: utf-8 -*-
"""Собирает цены продуктов с arzan.kz (Алматы) и пишет ../data/prices.js для сайта.

    python tools/fetch_prices.py

Для каждого продукта берём подходящие товары из поиска arzan.kz, считаем цену
за единицу (кг / л / шт) по самому дешёвому магазину каждого товара и берём
медиану — чтобы одна акция или премиум-бренд не исказили расчёт. Пример товара
(название, фасовка, магазин) — ближайший к медиане.
"""
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from products import COMMON_EXC, PRODUCTS  # noqa: E402

API = "https://api.arzan.kz/api/search/"
CITY_ID = 1  # Алматы
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130 Safari/537.36",
           "Origin": "https://arzan.kz", "Referer": "https://arzan.kz/ru/almaty", "Accept": "application/json"}
OUT = Path(__file__).resolve().parent.parent / "data" / "prices.js"


def per_unit(hit, unit):
    """Цена за кг / л / шт по самому дешёвому магазину товара (None — если не посчитать)."""
    price = hit.get("min_price")
    if not price:
        return None
    kind = hit.get("measure_unit_kind")
    qty = float(hit.get("measure_unit_qty") or 0) * (hit.get("pack_count") or 1)
    if hit.get("is_weighted") and unit == "кг":
        return price  # весовой товар — цена уже за кг
    if unit in ("кг", "л") and kind in ("g", "ml") and qty > 0:
        return price / qty * 1000
    if unit in ("кг", "л") and kind in ("kg", "l") and qty > 0:
        return price / qty
    if unit == "шт":
        if kind in ("piece", "pcs", "pc", "шт") and qty > 0:
            return price / qty
        if kind in (None, "", "g", "ml") and (hit.get("measure_unit") or "").startswith("шт"):
            return price / (hit.get("pack_count") or 1)
    return None


def cheapest_store(hit):
    offers = (hit.get("favorite_presentation") or {}).get("store_offers") or []
    offers = [o for o in offers if o.get("price")]
    return min(offers, key=lambda o: o["price"])["chain_name"] if offers else ""


def search(q, page):
    """Поиск arzan.kz с паузами: при «слишком много запросов» (429) ждём и повторяем."""
    for attempt in range(8):
        r = requests.get(API, params={"q": q, "city_id": CITY_ID, "page": page}, headers=HEADERS, timeout=30)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After") or 0) or 30 * (attempt + 1)
            print(f"    arzan.kz просит подождать {wait} с…", flush=True)
            time.sleep(wait)
            continue
        r.raise_for_status()
        time.sleep(4)  # arzan.kz ограничивает частоту — не чаще ~15 запросов в минуту
        return r.json().get("hits", [])
    raise RuntimeError("arzan.kz: слишком много запросов, попробуйте позже")


def fetch(key, p):
    norm = lambda ws: [w.replace("ё", "е") for w in ws]
    starts, anywhere, req = tuple(norm(p.get("starts", []))), norm(p.get("anywhere", [])), norm(p.get("req", []))
    exc = norm(p["exc"] + COMMON_EXC)

    def title_ok(t):
        if starts and not t.startswith(starts):
            return False
        if anywhere and not any(w in t for w in anywhere):
            return False
        if req and not any(w in t for w in req):
            return False
        return not any(w in t for w in exc)
    hits = search(p["q"], 0)
    good = []
    for h in hits:
        t = (h.get("title") or "").lower().replace("ё", "е")
        if not h.get("is_active", True) or not title_ok(t):
            continue
        u = per_unit(h, p["unit"])
        if u and u > 0:
            good.append((u, h))
    if not good:
        return None
    med = statistics.median(u for u, _ in good)
    # отбрасываем явные выбросы (в 3 раза дороже/дешевле медианы) и пересчитываем
    good = [(u, h) for u, h in good if med / 3 <= u <= med * 3] or good
    med = statistics.median(u for u, _ in good)
    u_ex, ex = min(good, key=lambda x: abs(x[0] - med))
    pkg = ((ex.get("favorite_presentation") or {}).get("package_labels") or {}).get("ru", "")
    return {
        "name": p["name"], "unit": p["unit"], "spice": bool(p.get("spice")),
        "price_per_unit": round(med), "min_per_unit": round(min(u for u, _ in good)),
        "pack_price": round(ex["min_price"]), "pack_label": pkg,
        "example": ex.get("title"), "store": cheapest_store(ex), "matches": len(good),
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    prices, missing = {}, []
    for key, p in PRODUCTS.items():
        try:
            res = fetch(key, p)
        except Exception as e:
            res = None
            print(f"  ! {p['name']}: {e}")
        if res:
            prices[key] = res
            print(f"{p['name']:<28} {res['price_per_unit']:>7} ₸/{p['unit']:<2}  ({res['matches']} тов.)  пример: {res['example']} — {res['pack_price']} ₸ {res['pack_label']} [{res['store']}]", flush=True)
        else:
            missing.append(p["name"])
            print(f"{p['name']:<28}  НЕ НАЙДЕНО")
    data = {"updated": datetime.now().strftime("%d.%m.%Y"), "source": "arzan.kz, Алматы", "products": prices}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("// Сгенерировано tools/fetch_prices.py — цены с arzan.kz (Алматы)\nwindow.PRICES = "
                   + json.dumps(data, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    print(f"\nСохранено: {OUT}  (найдено {len(prices)} из {len(PRODUCTS)})")
    if missing:
        print("Не найдено:", ", ".join(missing))


if __name__ == "__main__":
    main()
