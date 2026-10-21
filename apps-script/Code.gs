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
    const url = createDoc_(data);
    return json_({ ok: true, url: url });
  } catch (err) {
    return json_({ ok: false, error: String(err && err.message || err) });
  }
}

// Проверка в браузере: открыть URL веб-приложения — должно ответить «работает».
function doGet() {
  return json_({ ok: true, message: "Воскресный пир: экспорт в Google Docs работает" });
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
  let tabIds = null;
  try {
    tabIds = addTabs_(id, ["Сводка"].concat(TAB_ORDER));
  } catch (err) {
    console.warn("Вкладки не созданы, пишу разделами: " + err);
  }

  const d = DocumentApp.openById(id);
  if (tabIds) {
    writeSummary_(d.getTab(tabIds["Сводка"]).asDocumentTab().getBody(), data);
    TAB_ORDER.forEach(function (t) {
      writeTab_(d.getTab(tabIds[t]).asDocumentTab().getBody(), t, tabs[t]);
    });
  } else {
    const body = d.getBody();
    writeSummary_(body, data);
    TAB_ORDER.forEach(function (t) {
      body.appendPageBreak();
      writeTab_(body, t, tabs[t]);
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
  return "https://docs.google.com/document/d/" + id + "/edit";
}

/** Первая вкладка переименовывается в «Сводка», остальные добавляются. Возвращает {название: tabId}. */
function addTabs_(docId, titles) {
  const api = "https://docs.googleapis.com/v1/documents/" + docId;
  const headers = { Authorization: "Bearer " + ScriptApp.getOAuthToken() };
  const docJson = JSON.parse(UrlFetchApp.fetch(api + "?includeTabsContent=true", { headers: headers }).getContentText());
  const firstId = docJson.tabs[0].tabProperties.tabId;

  const requests = [{ updateDocumentTabProperties: { tabProperties: { tabId: firstId, title: titles[0] }, fields: "title" } }];
  titles.slice(1).forEach(function (t, i) {
    requests.push({ addDocumentTab: { tabProperties: { title: t, index: i + 1 } } });
  });
  const resp = UrlFetchApp.fetch(api + ":batchUpdate", {
    method: "post", contentType: "application/json", headers: headers,
    payload: JSON.stringify({ requests: requests }), muteHttpExceptions: true
  });
  if (resp.getResponseCode() !== 200) throw new Error(resp.getContentText().slice(0, 300));

  const ids = {};
  ids[titles[0]] = firstId;
  JSON.parse(resp.getContentText()).replies.forEach(function (r) {
    if (r.addDocumentTab) ids[r.addDocumentTab.tabProperties.title] = r.addDocumentTab.tabProperties.tabId;
  });
  return ids;
}

function writeSummary_(body, data) {
  body.clear();
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

function writeTab_(body, tabName, sections) {
  if (body.clear) body.clear();
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
