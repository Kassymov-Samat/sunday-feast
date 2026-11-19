# -*- coding: utf-8 -*-
"""Фотографии блюд через ChatGPT (аккаунт повара, вход в окне браузера один раз).

    python tools/gen_images.py            — все блюда без фото
    python tools/gen_images.py d12 d40    — только эти (пересоздать)

Открывает chatgpt.com в отдельном профиле браузера (папка C:\\Users\\<вы>\\.sunday-feast-chatgpt —
вход сохраняется). Для каждого блюда — новый чат, промпт с реальным составом блюда (только продукты
из раскладки, ничего не выдумываем), ждём картинку, сохраняем data/img/<id>.webp (1024 px) и
data/img/<id>-s.webp (400 px для карточек). Можно прервать и запустить снова — продолжит с места.
Журнал: tools/_images.log
"""
import io
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "data" / "img"
PROFILE = Path.home() / ".sunday-feast-chatgpt"
LOG = Path(__file__).parent / "_images.log"

STYLE = (
    "Фотореалистичная фотография блюда для меню праздничного вегетарианского пира (индийская ведическая кухня). "
    "Ракурс 45°, блюдо по центру, занимает 70% кадра. Подача: латунная или медная посуда (тали, катори, кувшин для напитков), "
    "под ней — тёмно-бордовая льняная ткань, на заднем плане размыто — тёмное дерево и пара листьев карри. "
    "Свет: тёплый мягкий боковой, как от окна, лёгкие блики, глубокие тени, тёплая цветокоррекция (золото, бордо). "
    "Строго вегетарианское: без мяса, рыбы, яиц, лука и чеснока. Без текста, надписей, логотипов, рук и людей. "
    "Квадрат 1:1."
)


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_js(name, start, end):
    t = (ROOT / "data" / name).read_text(encoding="utf-8")
    return json.loads(t[t.index(start):t.rindex(end) + 1])


def prompt_for(d, cat):
    prods = sorted(d["products"].items(), key=lambda kv: -kv[1])
    names = []
    for k, _ in prods:
        n = cat.get(k, {}).get("name", "")
        n = re.sub(r"\s*\(.*?\)|\s*\d+[,.]?\d*%", "", n).strip().lower()
        if n and n not in ("масло подсолнечное", "масло сливочное", "соль", "сахар", "вода") and n not in names:
            names.append(n)
    comp = ", ".join(names[:7]) or "по классическому рецепту"
    kind = {"Напитки": "Напиток подан в прозрачном стеклянном стакане и кувшине на латунном подносе. ",
            "Супы и далы": "Суп в глубокой латунной миске. ",
            "Сладости": "Сладости выложены на латунном блюде, несколько штук. ",
            "Хлеб и выпечка": "Выпечка на деревянной доске или латунном блюде. ",
            "Салаты и нарезки": "Салат в широкой латунной миске. "}.get(d["category"], "")
    return (f"Сгенерируй одно изображение — одно блюдо крупным планом, не коллаж и не сетка из нескольких фото; "
            f"не опирайся на прошлые изображения. Блюдо: «{d['name']}» ({d['category'].lower()}). "
            f"Состав (видно на фото только это, ничего лишнего): {comp}. {kind}{STYLE}")


def save(png_bytes, did):
    from PIL import Image
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    s = min(im.size)
    im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2))
    IMG.mkdir(parents=True, exist_ok=True)
    im.resize((1024, 1024), Image.LANCZOS).save(IMG / f"{did}.webp", "WEBP", quality=84)
    im.resize((400, 400), Image.LANCZOS).save(IMG / f"{did}-s.webp", "WEBP", quality=80)
    write_index()


def write_index():
    ids = sorted(p.stem for p in IMG.glob("*.webp") if not p.stem.endswith("-s"))
    (IMG / "index.js").write_text("// Список блюд, у которых есть фото (обновляет tools/gen_images.py)\n"
                                  "window.DISH_IMAGES = " + json.dumps(ids) + ";\n", encoding="utf-8")


class Tab:
    """Одна вкладка ChatGPT в Chrome, напрямую по протоколу отладки (остальные вкладки не трогаем)."""
    PORT = 9333

    def __init__(self):
        import urllib.request
        import websocket
        self.n = 0
        base = f"http://127.0.0.1:{self.PORT}"
        tid_file = PROFILE / "sf_tab.txt"
        tabs = json.load(urllib.request.urlopen(base + "/json/list"))
        tid = tid_file.read_text().strip() if tid_file.exists() else ""
        t = next((x for x in tabs if x["id"] == tid), None)
        if t is None:
            t = json.load(urllib.request.urlopen(urllib.request.Request(base + "/json/new?https://chatgpt.com/", method="PUT")))
            PROFILE.mkdir(exist_ok=True)
            tid_file.write_text(t["id"])
            time.sleep(8)
        self.ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=60, suppress_origin=True,
                                              max_size=None) if "max_size" in websocket.create_connection.__code__.co_varnames \
            else websocket.create_connection(t["webSocketDebuggerUrl"], timeout=60, suppress_origin=True)

    def call(self, method, params=None):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params or {}}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(m["error"].get("message"))
                return m.get("result", {})

    def js(self, expr, wait=False):
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": wait})
        return r.get("result", {}).get("value")

    def goto(self, url):
        self.call("Page.navigate", {"url": url})
        time.sleep(3)

    def key_enter(self):
        for t in ("keyDown", "keyUp"):
            self.call("Input.dispatchKeyEvent", {"type": t, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13,
                                                 **({"text": "\r"} if t == "keyDown" else {})})


def fresh_tab():
    """Вкладка зависла (бывает после многих часов) — закрываем её и открываем новую."""
    import urllib.request
    f = PROFILE / "sf_tab.txt"
    try:
        tid = f.read_text().strip()
        urllib.request.urlopen(f"http://127.0.0.1:{Tab.PORT}/json/close/{tid}", timeout=10)
    except Exception:
        pass
    f.unlink(missing_ok=True)
    time.sleep(3)
    try:
        return Tab()
    except Exception as e:
        log(f"не открылась новая вкладка: {str(e)[:120]}")
        time.sleep(30)
        return Tab()


EDITOR = "document.querySelector('#prompt-textarea, .ProseMirror[contenteditable=true]')"


def wait_login(tab):
    """До 30 минут ждём, пока повар войдёт в ChatGPT в этой вкладке."""
    for i in range(900):
        if tab.js(f"!!{EDITOR} && !document.querySelector('[data-testid=login-button]')"):
            return True
        if i % 30 == 0:
            log("жду вход в ChatGPT во вкладке Chrome…")
        time.sleep(2)
    return False


IMGS = """[...document.querySelectorAll('main img')].filter(e => e.naturalWidth >= 512 && e.complete &&
  /енерир|enerated/i.test(e.alt)).map(e => e.src)"""
FETCH = """(async (u) => { const r = await fetch(u, {credentials: 'include'}); const b = await r.blob();
  return await new Promise(res => { const f = new FileReader(); f.onload = () => res(f.result.split(',')[1]); f.readAsDataURL(b); }); })"""


def generate(tab, text, timeout_s=480):
    import base64
    tab.goto("https://chatgpt.com/")
    for _ in range(30):
        if tab.js(f"!!{EDITOR}"):
            break
        time.sleep(1)
    before = set(tab.js(IMGS) or [])
    tab.js(f"{EDITOR}.focus()")
    tab.call("Input.insertText", {"text": text})
    time.sleep(1.5)
    # отправка: кнопка «Отправить», если её нет — Enter; проверяем, что чат начался (адрес /c/…)
    SEND = "document.querySelector('[data-testid=send-button], #composer-submit-button, button[aria-label*=\"Отправить\"], button[aria-label*=\"Send\"]')"
    for _ in range(4):
        if not tab.js(f"!!{SEND} && !{SEND}.disabled && ({SEND}.click(), true)"):
            tab.js(f"{EDITOR}.focus()")
            tab.key_enter()
        for _ in range(10):
            time.sleep(1)
            if "/c/" in (tab.js("location.pathname") or ""):
                break
        else:
            continue
        break
    else:
        return None, "не отправилось"
    t0, last = time.time(), None
    while time.time() - t0 < timeout_s:
        time.sleep(5)
        new = [s for s in (tab.js(IMGS) or []) if s not in before]
        if new:
            if new[-1] == last:  # картинка дорисовалась — src больше не меняется
                b64 = tab.js(FETCH + f"({json.dumps(new[-1])})", wait=True)
                if b64:
                    return base64.b64decode(b64), "ok"
            last = new[-1]
        elif time.time() - t0 > 40:
            body = (tab.js("document.querySelector('main')?.innerText.slice(-1500) || ''") or "").lower()
            if re.search(r"лимит|limit|достигли|reached|попробуйте позже|try again later|подождите", body):
                return None, "limit"
    return None, "timeout"


def main():
    dishes = load_js("dishes.js", "[", "]")
    cat = load_js("catalog.js", "{", "}")
    only = set(sys.argv[1:])
    todo = [d for d in dishes if d["id"] in only] if only else \
           [d for d in dishes if not (IMG / f"{d['id']}.webp").exists()]
    log(f"блюд без фото: {len(todo)}")
    import urllib.request
    import subprocess
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{Tab.PORT}/json/version", timeout=2)
    except Exception:  # обычный Chrome (не «управляемый» — иначе Google не даёт войти), отдельный профиль
        chrome = next((c for c in [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                                   r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                                   str(Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe")] if Path(c).exists()))
        subprocess.Popen([chrome, f"--user-data-dir={PROFILE}", f"--remote-debugging-port={Tab.PORT}",
                          "--no-first-run", "--no-default-browser-check"])
        time.sleep(5)
    tab = Tab()
    if not wait_login(tab):
        log("не дождался входа — запустите снова")
        return
    done = 0
    for d in todo:
        for attempt in range(3):
            try:
                tab = fresh_tab()  # в новой вкладке картинка ловится сразу; в старой — через раз
                data, st = generate(tab, prompt_for(d, cat), timeout_s=240)
            except Exception as e:
                data, st = None, f"ошибка: {str(e)[:150]}"
                tab = fresh_tab()
            if data:
                save(data, d["id"])
                done += 1
                log(f"✓ {d['id']} {d['name']} ({done}/{len(todo)})")
                break
            log(f"✗ {d['id']} {d['name']}: {st}")
            if st == "limit":
                log("лимит картинок ChatGPT — пауза 30 минут")
                time.sleep(30 * 60)
            else:
                time.sleep(15)
                if st == "timeout":
                    tab = fresh_tab()  # вкладка могла зависнуть — открываем новую
        time.sleep(6)
    log(f"готово: {done}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
