/**
 * Веб-приложение для сайта «Воскресный пир»: принимает список закупа и создаёт Google Doc
 * с вкладками: Сводка · Молочка · Бакалея · Овощи и фрукты · Остальное (специи и хоз. часть — внутри).
 *
 * Установка (один раз, ~3 минуты) — см. README.md в этой папке.
 * Необязательно: Свойства проекта → FOLDER_ID = id папки на Диске, куда складывать документы.
 */

const TAB_ORDER = ["Молочка", "Бакалея", "Овощи и фрукты", "Остальное"];

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    switch (data.action) {
      case "saveDish": return json_(saveDish_(data));
      case "deleteDish": return json_(deleteDish_(data));
      case "saveProduct": return json_(saveProducts_(data.products || {}));
      case "deleteProduct": return json_(deleteProduct_(data));
      default: {
        const res = createDoc_(data);
        return json_({ ok: true, url: res.url, tabs: res.tabs, tabError: res.tabError });
      }
    }
  } catch (err) {
    return json_({ ok: false, error: String(err && err.message || err) });
  }
}

// ?action=data — блюда и продукты, добавленные/изменённые на сайте (общие для всех).
// Без параметров — проверка, что скрипт работает.
function doGet(e) {
  if (e && e.parameter && e.parameter.action === "data") return json_(loadData_());
  return json_({ ok: true, message: "Воскресный пир: экспорт в Google Docs работает" });
}

/* ── Справочник, который правят на сайте: хранится в свойствах скрипта ─────────────
 * dish:<id>    — блюдо (своё или изменённая версия встроенного); {deleted:true} — скрыто
 * product:<key> — продукт/специя/хоз. позиция (новая или с изменённой ценой/названием)
 */
function loadData_() {
  const all = PropertiesService.getScriptProperties().getProperties();
  const dishes = [], products = {};
  Object.keys(all).forEach(function (k) {
    try {
      if (k.indexOf("dish:") === 0) dishes.push(JSON.parse(all[k]));
      else if (k.indexOf("product:") === 0) products[k.slice(8)] = JSON.parse(all[k]);
    } catch (err) { console.warn("битая запись " + k); }
  });
  return { ok: true, dishes: dishes, products: products };
}

function withLock_(fn) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try { return fn(); } finally { lock.releaseLock(); }
}

function clean_(s, max) { return String(s == null ? "" : s).trim().slice(0, max || 200); }

function saveProducts_(products) {
  return withLock_(function () {
    const props = PropertiesService.getScriptProperties();
    Object.keys(products).forEach(function (key) {
      if (!/^[\w-]{1,60}$/.test(key)) throw new Error("плохой ключ продукта: " + key);
      const p = products[key];
      props.setProperty("product:" + key, JSON.stringify({
        name: clean_(p.name, 120), unit: clean_(p.unit, 20), section: clean_(p.section, 40),
        price: Math.max(0, Number(p.price) || 0), price_src: clean_(p.price_src || "изменено на сайте", 40),
        per100: Number(p.per100) || 0, default: !!p.default, per_guest: Number(p.per_guest) || 0,
        updated: new Date().toISOString()
      }));
    });
    return { ok: true };
  });
}

function saveDish_(data) {
  const d = data.dish || {};
  if (!/^[\w-]{1,60}$/.test(d.id || "")) throw new Error("нет id блюда");
  if (!clean_(d.name)) throw new Error("нет названия блюда");
  if (data.products) saveProducts_(data.products);
  const num = function (m) {
    const out = {};
    Object.keys(m || {}).forEach(function (k) { const v = Number(m[k]); if (v > 0) out[k] = v; });
    return out;
  };
  const dish = {
    id: d.id, name: clean_(d.name, 120), category: clean_(d.category, 60) || "Другое",
    tags: (d.tags || []).map(function (t) { return clean_(t, 30); }).slice(0, 6),
    note: clean_(d.note, 300), source: clean_(d.source, 120) || "добавлено на сайте",
    products: num(d.products), spices: num(d.spices), custom: true, updated: new Date().toISOString()
  };
  return withLock_(function () {
    PropertiesService.getScriptProperties().setProperty("dish:" + d.id, JSON.stringify(dish));
    return { ok: true, dish: dish };
  });
}

function deleteProduct_(data) {
  if (!/^[\w-]{1,60}$/.test(data.key || "")) throw new Error("нет ключа продукта");
  return withLock_(function () {
    PropertiesService.getScriptProperties().setProperty("product:" + data.key,
      JSON.stringify({ deleted: true, updated: new Date().toISOString() }));
    return { ok: true };
  });
}

function deleteDish_(data) {
  if (!/^[\w-]{1,60}$/.test(data.id || "")) throw new Error("нет id блюда");
  return withLock_(function () {
    PropertiesService.getScriptProperties().setProperty("dish:" + data.id,
      JSON.stringify({ id: data.id, deleted: true, updated: new Date().toISOString() }));
    return { ok: true };
  });
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function money_(n) {
  return Math.round(n || 0).toLocaleString("ru-RU").replace(/,/g, " ") + " ₸";
}

function createDoc_(data) {
  const title = data.title || ("Закуп — " + Utilities.formatDate(new Date(), "Asia/Almaty", "dd.MM.yyyy"));
  const doc = DocumentApp.create(title);
  const id = doc.getId();
  doc.saveAndClose();

  // Раскладываем разделы сайта по вкладкам документа
  const tabs = {};
  TAB_ORDER.forEach(function (t) { tabs[t] = []; });
  (data.sections || []).forEach(function (s) {
    const tab = s.tab && tabs[s.tab] ? s.tab : "Остальное";
    tabs[tab].push(s);
  });

  // Создаём вкладки через Docs API; если не вышло — всё пишем в одну вкладку с разделами
  let tabIds = null, tabError = "";
  try {
    tabIds = addTabs_(id, ["Сводка"].concat(TAB_ORDER));
  } catch (err) {
    tabError = String(err && err.message || err);
    console.warn("Вкладки не созданы, пишу разделами: " + tabError);
  }

  const d = DocumentApp.openById(id);
  if (tabIds) {
    writeSummary_(d.getTab(tabIds["Сводка"]).asDocumentTab().getBody(), data, true);
    TAB_ORDER.forEach(function (t) {
      writeTab_(d.getTab(tabIds[t]).asDocumentTab().getBody(), t, tabs[t], true);
    });
  } else {
    // запасной вариант: одна вкладка, разделы с новой страницы (без очистки между разделами)
    const body = d.getBody();
    writeSummary_(body, data, true);
    TAB_ORDER.forEach(function (t) {
      body.appendPageBreak();
      writeTab_(body, t, tabs[t], false);
    });
  }
  d.saveAndClose();

  const file = DriveApp.getFileById(id);
  const folderId = PropertiesService.getScriptProperties().getProperty("FOLDER_ID");
  if (folderId) {
    try { file.moveTo(DriveApp.getFolderById(folderId)); } catch (err) { console.warn(err); }
  }
  // повар и закупщик открывают документ по ссылке
  file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.EDIT);
  return { url: "https://docs.google.com/document/d/" + id + "/edit", tabs: !!tabIds, tabError: tabError };
}

/** Первая вкладка переименовывается в «Сводка», остальные добавляются. Возвращает {название: tabId}. */
function addTabs_(docId, titles) {
  // Расширенная служба «Docs» (Google Docs API) — подключена в appsscript.json
  const docJson = Docs.Documents.get(docId, { includeTabsContent: true });
  const firstId = docJson.tabs[0].tabProperties.tabId;

  const requests = [{ updateDocumentTabProperties: { tabProperties: { tabId: firstId, title: titles[0] }, fields: "title" } }];
  titles.slice(1).forEach(function (t, i) {
    requests.push({ addDocumentTab: { tabProperties: { title: t, index: i + 1 } } });
  });
  const resp = Docs.Documents.batchUpdate({ requests: requests }, docId);

  const ids = {};
  ids[titles[0]] = firstId;
  (resp.replies || []).forEach(function (r) {
    if (r.addDocumentTab) ids[r.addDocumentTab.tabProperties.title] = r.addDocumentTab.tabProperties.tabId;
  });
  return ids;
}

function writeSummary_(body, data, clear) {
  if (clear) body.clear();
  body.appendParagraph(data.title || "Закуп").setHeading(DocumentApp.ParagraphHeading.TITLE);
  const info = [];
  if (data.date) info.push("Дата: " + data.date);
  if (data.guests) info.push("Гостей: " + data.guests);
  if (data.cook) info.push("Повар: " + data.cook);
  if (info.length) body.appendParagraph(info.join("   ·   "));
  if (data.dishes && data.dishes.length) {
    body.appendParagraph("Меню").setHeading(DocumentApp.ParagraphHeading.HEADING2);
    data.dishes.forEach(function (n) { body.appendListItem(n).setGlyphType(DocumentApp.GlyphType.BULLET); });
  }
  body.appendParagraph("Итого по разделам").setHeading(DocumentApp.ParagraphHeading.HEADING2);
  const rows = [["Раздел", "Позиций", "Сумма"]];
  (data.sections || []).forEach(function (s) {
    rows.push([s.name, String((s.rows || []).length), money_(s.total)]);
  });
  rows.push(["ИТОГО", "", money_(data.total)]);
  styleTable_(body.appendTable(rows), true);
  if (data.comment) {
    body.appendParagraph("Комментарий").setHeading(DocumentApp.ParagraphHeading.HEADING2);
    body.appendParagraph(data.comment);
  }
}

function writeTab_(body, tabName, sections, clear) {
  if (clear) body.clear();
  body.appendParagraph(tabName).setHeading(DocumentApp.ParagraphHeading.HEADING1);
  if (!sections.length) {
    body.appendParagraph("— ничего не нужно —");
    return;
  }
  let tabTotal = 0;
  sections.forEach(function (s) {
    if (sections.length > 1 || s.name !== tabName) {
      body.appendParagraph(s.name).setHeading(DocumentApp.ParagraphHeading.HEADING2);
    }
    const rows = [["✓", "Наименование", "Кол-во", "Ед.", "Цена", "Сумма"]];
    (s.rows || []).forEach(function (r) {
      rows.push(["☐", r.name, String(r.qty), r.unit || "", r.price ? money_(r.price) : "", r.sum ? money_(r.sum) : ""]);
    });
    rows.push(["", "Итого: " + s.name, "", "", "", money_(s.total)]);
    styleTable_(body.appendTable(rows), true);
    tabTotal += s.total || 0;
  });
  if (sections.length > 1) body.appendParagraph("Итого по вкладке: " + money_(tabTotal)).setBold(true);
}

function styleTable_(table, lastBold) {
  const n = table.getNumRows();
  table.getRow(0).editAsText().setBold(true);
  for (let c = 0; c < table.getRow(0).getNumCells(); c++) table.getRow(0).getCell(c).setBackgroundColor("#f3e6dc");
  if (lastBold) table.getRow(n - 1).editAsText().setBold(true);
}
