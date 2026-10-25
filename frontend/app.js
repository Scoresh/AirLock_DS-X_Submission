/* StrangerThesis workspace.
   API (local FastAPI server):
     GET  /status                                    -> { model: { configured, model, endpoint } }
     GET  /sample                                    -> the test thesis PDF
     POST /parse            (multipart: file)        -> { doc_id, pages[] }
     POST /scrub/{doc_id}                            -> { scrubbed_pages[], direct_identifiers[], participants[] }
     POST /score            { doc_id, accepted[] }   -> { participants[], gate_open }   (accepted fixes accumulate)
     POST /review           { doc_id }               -> { findings[], model_review, model }
     GET  /llm-view/{doc_id}                         -> { pages[{ page, original, sent_to_llm }] }
   PDF.js draws pages in the browser; the file itself is only sent to the local server. */

"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const PDFJS = "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.0.379/build";
const TOKEN = /\[[A-Z_]+_\d+\]/g;
const DIFF_LIMIT = 4_000_000;  // word pairs; longer pages skip the word diff

// Column names of the organizers' NSSE synthetic data (see backend/app/risk.py).
const FIELD_LABEL = {
  Class: "Class year", affiliation: "Affiliation", MAJfirst: "Major", MAJfirstfield: "Major field",
  MAJsecond: "Second major", MAJsecondfield: "Second major field", MAJnum: "Majors", begincol: "Started college",
};
const LOSS = {
  MAJfirst: "major → its field",
  MAJfirstfield: "major field → omitted",
  MAJsecond: "second major → its field",
  MAJsecondfield: "second major → “another field”",
  affiliation: "affiliation → omitted",
  begincol: "transfer history → omitted",
};
const ID_LABEL = { PERSON: "name", EMAIL: "email", PHONE: "phone number", STUDENT_ID: "student ID", SECTION: "course section", OTHER: "identifier" };
const RISK_TEXT = { high: "High risk", medium: "Medium risk", low: "Low risk" };
const RISK_ORDER = { high: 0, medium: 1, low: 2 };

const state = {
  populationSource: "local",
  model: null,          // { configured, model, endpoint }
  file: null, isSample: false,
  parsed: null, scrubbed: null, scored: null, view: null, review: null,
  rubric: null,         // [{ parameter_title, description, points? }] loaded from rubric JSON
  rubricCheck: null,    // { results[], model_review, model } from /rubric-check
  rubricError: null,    // string: problem loading/parsing the rubric JSON
  rubricSource: null,   // file name of the loaded rubric JSON
  pdfDoc: null, pageGeom: {}, textItems: {},
  formatCheckedFor: null,  // doc_id whose local format findings are already loaded
  page: 1, tab: "privacy", compare: false, focus: null, busy: false,
};

/* ---------- helpers ---------- */
async function request(path, { method = "GET", body, form } = {}) {
  const opts = { method };
  if (form) opts.body = form;
  else if (body !== undefined) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, opts);
  } catch {
    throw Object.assign(new Error("We couldn’t reach the document checker. Please try again in a moment."), { status: 0 });
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* not JSON */ }
    if (state.scored && (path === "/score" || ((path === "/review" || path.startsWith("/rubric-check/")) && [403, 404, 503].includes(res.status)))) {
      state.scored = { ...state.scored, gate_open: false, check_error: detail };
      state.review = null;
      state.rubricCheck = null;
    }
    throw Object.assign(new Error(detail), { status: res.status });
  }
  return res.json();
}

const participantName = (id) => `Participant ${Number(String(id).replace(/\D/g, ""))}`;
const fileSize = (n) => n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(1)} MB`;
const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const fieldValue = (field, v) => v;

function joinNames(names) {
  if (names.length < 2) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

function scoredById() {
  return Object.fromEntries((state.scored?.participants || []).map((p) => [p.id, p]));
}

function concernsOnPage(n) {
  const scored = scoredById();
  return (state.scrubbed?.participants || [])
    .filter((p) => p.pages.includes(n) && scored[p.id] && scored[p.id].risk !== "low");
}

function idsOnPage(n) {
  return new Set((state.scrubbed?.direct_identifiers || []).filter((d) => d.page === n).map((d) => d.token)).size;
}

// What the page index and the page edge show, most urgent first.
function pageStatus(n) {
  if (concernsOnPage(n).length) return "risk";
  if (idsOnPage(n)) return "replaced";
  if (findingsOnPage(n).length) return "format";
  return "";
}

function findingsOnPage(n, source) {
  return (state.review?.findings || []).filter((f) => f.page === n && (!source || f.source === source));
}

function modelSentLabel() {
  return state.review?.model_review === "sent" ? `Sent to model · ${state.review.model}` : "Prepared for review";
}

/* ---------- masthead status ---------- */
function setLocalStatus(text) { $("status-local").textContent = text; }

function renderModelStatus() {
  const m = state.model;
  let text;
  if (!m) text = "Currently unavailable";
  else if (state.review?.model_review === "sent") text = `Prepared text sent to ${state.review.model}`;
  else if (state.review?.model_review === "not_implemented") text = `${m.model} configured · model review not implemented, nothing sent`;
  else if (state.review?.model_review === "failed") text = `${m.model} configured · review request failed`;
  // A review may have run earlier with no model. Don't leave the line stuck on
  // "Not configured" after the user swaps one in — reflect the current config.
  else if (m.configured) text = `${m.model}${m.endpoint ? ` (${m.endpoint})` : ""}`;
  else if (state.review) text = "Off · nothing sent to AI";
  else text = "Off · add a reviewer in Settings";
  $("status-model").textContent = text;
}

/* ---------- intake ---------- */
function showIntakeError(message, details = "") {
  $("intake-error").innerHTML = `${esc(message)}${details
    ? `<details class="explain"><summary>Technical details</summary><p>${esc(details)}</p></details>` : ""}`;
  $("intake-error").hidden = false;
}

function chooseFile(file) {
  if (state.setupBlocked) return;  // keep the setup warning visible
  $("intake-error").hidden = true;
  if (!file) return;
  const isPdf = file.type === "application/pdf" || /\.pdf$/i.test(file.name);
  if (!isPdf) {
    state.file = null;
    $("start").disabled = true;
    $("file-name").textContent = "";
    showIntakeError(`“${file.name}” isn't a PDF. Choose a PDF, or open the sample document.`);
    return;
  }
  state.file = file;
  state.isSample = false;
  $("file-name").innerHTML = `Selected: <strong>${esc(file.name)}</strong> <span class="num">· ${fileSize(file.size)}</span>`;
  $("start").disabled = false;
}

$("pdf").addEventListener("change", () => chooseFile($("pdf").files[0]));

const drop = $("dropzone");
["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, (e) => {
  e.preventDefault(); drop.classList.add("is-dragover");
}));
["dragleave", "drop"].forEach((t) => drop.addEventListener(t, (e) => {
  e.preventDefault(); drop.classList.remove("is-dragover");
}));
drop.addEventListener("drop", (e) => chooseFile(e.dataTransfer.files[0]));

$("upload-form").addEventListener("submit", (e) => {
  e.preventDefault();
  if (state.file) startCheck(state.file);
});

$("open-sample").addEventListener("click", async () => {
  $("intake-error").hidden = true;
  setIntakeBusy(true, "Loading sample document");
  try {
    const res = await fetch(`/sample?source=${state.populationSource}`);
    if (!res.ok) throw new Error("The sample document isn't available on the local server.");
    const blob = await res.blob();
    const file = new File([blob], "demo-thesis.pdf", { type: "application/pdf" });
    state.isSample = true;
    await startCheck(file, true);
  } catch (err) {
    setIntakeBusy(false);
    showIntakeError(err.message);
  }
});

function setIntakeBusy(busy, step = "") {
  $("progress").textContent = busy ? step : "";
  $("start").disabled = busy || !state.file;
  $("open-sample").disabled = busy;
  $("population-source").disabled = busy;
  if (busy) setLocalStatus(step);
}

async function startCheck(file, isSample = false) {
  state.file = file;
  state.isSample = isSample;
  $("intake-error").hidden = true;
  try {
    setIntakeBusy(true, "Reading your PDF");
    const form = new FormData();
    form.append("file", file, file.name);
    const [parsed, pdfDoc] = await Promise.all([request("/parse", { method: "POST", form }), openPdf(file)]);
    state.parsed = parsed;
    state.pdfDoc = pdfDoc;

    setIntakeBusy(true, "Finding personal details");
    setLocalStatus("Finding personal details");
    state.scrubbed = await request(`/scrub/${parsed.doc_id}?source=${state.populationSource}`, { method: "POST" });

    setIntakeBusy(true, state.populationSource === "jiff" ? "Comparing details privately · this can take a moment" : "Checking participant descriptions");
    state.scored = await request("/score", { method: "POST", body: { doc_id: parsed.doc_id, accepted: [] } });

    setIntakeBusy(true, "Preparing comparison");
    state.view = await request(`/llm-view/${parsed.doc_id}`);
    state.review = null;
    state.formatCheckedFor = null;
    state.rubricCheck = null;  // rubric itself (state.rubric) stays loaded across documents

    setIntakeBusy(false);
    await enterWorkspace();
  } catch (err) {
    setIntakeBusy(false);
    setLocalStatus("Waiting for a document");
    const hint = err.status === 400
      ? " Choose another PDF, or open the sample document."
      : err.status === 0 ? "" : " Try again, or open the sample document.";
    showIntakeError(`Couldn't check this document: ${err.message}.${hint}`);
  }
}

/* ---------- CSV mode ---------- */
$("csv-file").addEventListener("change", () => {
  $("csv-error").hidden = true;
  const f = $("csv-file").files[0];
  $("csv-start").disabled = !f;
});

$("csv-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = $("csv-file").files[0];
  if (!f) return;
  $("csv-error").hidden = true;
  $("csv-result").hidden = true;
  $("csv-start").disabled = true;
  $("csv-progress").textContent = "Checking your table’s privacy";
  try {
    const form = new FormData();
    form.append("file", f, f.name);
    renderCsvReport(await request("/csv/scrub", { method: "POST", form }), f.name);
  } catch (err) {
    $("csv-error").textContent = `Couldn't scrub this table: ${err.message}. Check that it is a comma-separated file with a header row.`;
    $("csv-error").hidden = false;
  } finally {
    $("csv-progress").textContent = "";
    $("csv-start").disabled = false;
  }
});

function renderCsvReport(r, name) {
  const byRole = {};
  r.columns.forEach((c) => (byRole[c.role] ||= []).push(c.rule ? `${c.name} (${c.rule.replaceAll("_", " ")})` : c.name));
  const pct = (v) => `${((v / r.rows) * 100).toFixed(1)}%`;
  const bins = Object.keys(r.k_before.bins);
  const roleLine = (role, label) => byRole[role] ? `<p><strong>${esc(label)}:</strong> ${esc(byRole[role].join(", "))}</p>` : "";
  $("csv-result").innerHTML = `<div class="csvreport">
      <p class="label">${esc(name)} · <span class="num">${r.rows.toLocaleString()}</span> rows</p>
      <div class="csvreport__roles">
        ${roleLine("direct identifier", "Replaced with tokens")}
        ${roleLine("quasi-identifier", "Generalized")}
        <p><strong>Kept as is:</strong> ${(byRole["kept"] || []).length + (byRole["quasi-identifier (kept)"] || []).length} columns</p>
      </div>
      <table aria-label="Re-identification risk before and after">
        <thead><tr><th>Estimated k</th><th>Before</th><th>After</th></tr></thead>
        <tbody>${bins.map((b) => `<tr><td>${esc(b)}</td><td>${pct(r.k_before.bins[b])}</td><td>${pct(r.k_after.bins[b])}</td></tr>`).join("")}</tbody>
      </table>
      <p class="csvreport__roles">k is computed on ${esc(r.k_after.columns.join(", ") || "no recognised columns")}. The token key stays on this machine.</p>
      <a class="btn btn--primary" href="${esc(r.download)}" download>Download scrubbed CSV</a>
    </div>`;
  $("csv-result").hidden = false;
}

/* ---------- PDF.js ---------- */
async function openPdf(file) {
  try {
    const pdfjsLib = await import(`${PDFJS}/pdf.min.mjs`);
    pdfjsLib.GlobalWorkerOptions.workerSrc = `${PDFJS}/pdf.worker.min.mjs`;
    return await pdfjsLib.getDocument({ data: await file.arrayBuffer() }).promise;
  } catch (e) {
    console.warn("PDF.js unavailable; showing extracted text instead.", e);
    return null;
  }
}

/* ---------- workspace ---------- */
async function enterWorkspace() {
  $("intake").hidden = true;
  $("workspace").hidden = false;
  $("workspace").dataset.pane = "reader";
  state.compare = false;
  state.textItems = {};
  state.pageGeom = {};

  const n = state.parsed.pages.length;
  $("file-title").textContent = state.isSample ? "Sample document" : state.file.name;
  $("file-meta").textContent = `${state.file.name} · ${plural(n, "page")} · ${fileSize(state.file.size)}`;
  setLocalStatus(`Privacy check complete · ${plural(n, "page")}`);

  const scored = state.scored.participants;
  const firstConcern = state.scrubbed.participants.find((p) => scoredById()[p.id]?.risk === "high");
  state.page = firstConcern ? firstConcern.pages[0] : 1;

  // Navigation and findings first. Page images draw in the background and never
  // disable controls: the privacy check does not depend on them.
  $("doc-view").innerHTML = "";
  renderAll();
  selectTab("privacy");
  maybeAutoFormatCheck();
  const page = state.page;
  renderDocument().then((finished) => {
    if (!finished) return;  // a newer document replaced this one
    renderOverlays();
    if (state.page === page) selectPage(page, { scroll: true });
  });
}

function renderAll() {
  renderModelStatus();
  // The workspace renderers below read state.parsed / state.scored. Before a
  // document is loaded (e.g. saving settings from the intake screen) there is
  // nothing to render, so stop after the model status.
  if (!state.parsed || !state.scored) return;
  renderSidebar();
  renderOverlays();
  renderCompare();
  renderPrivacyPanel();
  renderRubricPanel();
  $("doc-view").hidden = state.compare;
  $("compare-view").hidden = !state.compare;
}

function setBusy(text) {
  state.busy = Boolean(text);
  $("busy").textContent = text || "";
  document.querySelectorAll("#inspector button").forEach((b) => { b.disabled = state.busy || b.dataset.disabled === "1"; });
}

function showWorkError(err, retry) {
  const lost = err.status === 404;
  const message = lost
    ? "This document is no longer on the local server (it may have restarted). Start again with the same file."
    : `${err.message}. Your previous results are unchanged.`;
  $("work-error").innerHTML = `${esc(message)}<div class="notice__actions">
      ${lost ? `<button type="button" class="btn btn--secondary btn--small" id="err-restart">Start again</button>`
             : retry ? `<button type="button" class="btn btn--secondary btn--small" id="err-retry">Try again</button>` : ""}
      <button type="button" class="btn btn--quiet btn--small" id="err-dismiss">Dismiss</button></div>`;
  $("work-error").hidden = false;
  $("err-dismiss").onclick = () => { $("work-error").hidden = true; };
  if (lost) $("err-restart").onclick = () => { resetToIntake(); startCheck(state.file, state.isSample); };
  else if (retry) $("err-retry").onclick = () => { $("work-error").hidden = true; retry(); };
}

function resetToIntake() {
  state.drawId = (state.drawId || 0) + 1;  // stop any page drawing still in progress
  setReaderNote("");
  Object.assign(state, { parsed: null, scrubbed: null, scored: null, view: null, review: null, pdfDoc: null });
  $("workspace").hidden = true;
  $("intake").hidden = false;
  $("work-error").hidden = true;
  $("doc-view").innerHTML = "";
  $("compare-view").innerHTML = "";
  $("pdf").value = "";
  $("file-name").textContent = "";
  state.file = null;
  $("start").disabled = true;
  setLocalStatus("Waiting for a document");
  renderModelStatus();
}

$("new-doc").addEventListener("click", resetToIntake);

/* tabs */
const TABS = ["privacy", "compare", "rubric"];
// Tabs that take over the whole workspace (sidebar + reader/inspector hidden) so
// their content has the full width. Rubric fills the inspector; Compare fills the
// reader (see data-view below). Both get the whole workspace.
const FULL_WIDTH_TABS = ["rubric", "compare"];
// Tabs that have no inspector panel and instead drive the left reader column.
const READER_TABS = ["compare"];
function selectTab(name, { focus = false } = {}) {
  state.tab = name;
  TABS.forEach((t) => {
    const tab = $(`tab-${t}`);
    const on = t === name;
    tab.setAttribute("aria-selected", String(on));
    tab.tabIndex = on ? 0 : -1;
    const panel = $(`panel-${t}`);        // reader tabs (compare) have no inspector panel
    if (panel) panel.hidden = !on;
    if (on && focus) tab.focus();
  });
  // Compare is a reader view; everything else shows the inspector panels.
  state.compare = READER_TABS.includes(name);
  renderCompare();
  $("doc-view").hidden = state.compare;
  $("compare-view").hidden = !state.compare;
  const grid = $("workspace").querySelector(".workspace__grid");
  grid.dataset.full = FULL_WIDTH_TABS.includes(name) ? "1" : "";
  // data-view tells the CSS which column a full-width tab should fill.
  grid.dataset.view = READER_TABS.includes(name) ? "reader" : "inspector";
}
TABS.forEach((t) => $(`tab-${t}`).addEventListener("click", () => {
  selectTab(t);
  if (READER_TABS.includes(t)) {
    showPane("reader");
    selectPage(state.page, { scroll: true });
  } else {
    showPane("inspector");
  }
}));
$("workspace").querySelector(".viewtabs").addEventListener("keydown", (e) => {
  const i = TABS.indexOf(state.tab);
  const n = TABS.length;
  const next = { ArrowRight: (i + 1) % n, ArrowLeft: (i + n - 1) % n, Home: 0, End: n - 1 }[e.key];
  if (next === undefined) return;
  e.preventDefault();
  selectTab(TABS[next], { focus: true });
});

/* narrow screens: document or findings */
function showPane(pane) {
  if (!window.matchMedia("(max-width: 960px)").matches) return;
  $("workspace").dataset.pane = pane;
  $("show-reader").setAttribute("aria-pressed", String(pane === "reader"));
  $("show-inspector").setAttribute("aria-pressed", String(pane === "inspector"));
}
$("show-reader").addEventListener("click", () => showPane("reader"));
$("show-inspector").addEventListener("click", () => showPane("inspector"));

/* ---------- sidebar: page index as heatmap ---------- */
function renderSidebar() {
  const pages = state.parsed.pages;
  $("page-list").innerHTML = pages.map(({ page: n }) => {
    const p = concernsOnPage(n).length;
    const i = idsOnPage(n);
    const f = findingsOnPage(n, "rule").length;
    const m = findingsOnPage(n, "llm").length;
    const parts = [
      p && `${plural(p, "privacy risk")}`, i && `${plural(i, "identifier")} replaced`,
      f && `${plural(f, "format finding")}`, m && `${plural(m, "model finding")}`,
    ].filter(Boolean);
    const status = pageStatus(n);
    return `<li><button type="button" data-page="${n}" aria-current="${n === state.page}"
        aria-label="Page ${n}${parts.length ? `: ${parts.join(", ")}` : ": no findings"}">
      ${status ? `<span class="pagelist__bar pagelist__bar--${status}" aria-hidden="true"></span>` : ""}
      <span class="pagelist__num">p. ${n}</span>
      <span class="pagelist__marks" aria-hidden="true">
        ${p ? `<b class="mk mk--privacy">P${p > 1 ? p : ""}</b>` : ""}
        ${i ? `<b class="mk mk--replaced">I${i > 1 ? i : ""}</b>` : ""}
        ${f ? `<b class="mk mk--format">F${f > 1 ? f : ""}</b>` : ""}
        ${m ? `<b class="mk mk--model">M${m > 1 ? m : ""}</b>` : ""}
      </span></button></li>`;
  }).join("");

  const high = state.scored.participants.filter((p) => p.risk === "high");
  $("gate-chip").innerHTML = state.scored.checking
    ? `<span class="risk risk--high">Checking · review blocked</span>`
    : state.scored.check_error
    ? `<span class="risk risk--high">Incomplete · review blocked</span>`
    : state.scored.gate_open
    ? `<span class="risk risk--ready">Ready for review</span>`
    : `<span class="risk risk--high">Blocked · ${plural(high.length, "high-risk participant")}</span>`;

  const unresolved = state.scored.participants.filter((p) => p.risk !== "low").length;
  $("count-privacy").textContent = unresolved ? `(${unresolved})` : "";
  $("count-rubric").textContent = state.rubric?.length ? `(${state.rubric.length})` : "";
}

$("page-list").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-page]");
  if (!b) return;
  const n = Number(b.dataset.page);
  selectPage(n, { scroll: true });
  // Stay in the current check and bring that page's items into view.
  if (state.tab === "privacy") {
    const p = state.scrubbed.participants.find((x) => x.pages.includes(n));
    if (p) $(`concern-${p.id}`)?.scrollIntoView({ block: "start" });
    else document.querySelector(`#panel-privacy .annot[data-page="${n}"]`)?.scrollIntoView({ block: "nearest" });
  }
  showPane("reader");
});

function selectPage(n, { scroll = false, highlight = null } = {}) {
  state.page = n;
  document.querySelectorAll("#page-list button").forEach((b) =>
    b.setAttribute("aria-current", String(Number(b.dataset.page) === n)));
  document.querySelectorAll(".sheet").forEach((s) => s.classList.toggle("is-current", Number(s.dataset.page) === n));
  document.querySelectorAll(".hl.is-active, .annot.is-active").forEach((el) => el.classList.remove("is-active"));
  if (highlight) document.querySelectorAll(`[data-key="${highlight}"]`).forEach((el) => el.classList.add("is-active"));
  if (scroll) {
    const target = state.compare ? $(`cmp-${n}`) : $(`sheet-${n}`);
    target?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  }
}

/* ---------- reader: PDF pages ---------- */
const PAGE_DRAW_TIMEOUT_MS = 8000;  // a stalled page switches the rest to extracted text

function withTimeout(promise, ms) {
  let timer;
  return Promise.race([promise, new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error("timeout")), ms);
  })]).finally(() => clearTimeout(timer));
}

function setReaderNote(text) {
  $("reader-note").hidden = !text;
  $("reader-note").textContent = text || "";
}

/* Returns true when every page is placed, false if a newer document took over. */
async function renderDocument() {
  const drawId = (state.drawId = (state.drawId || 0) + 1);
  const pdfDoc = state.pdfDoc;
  const total = state.parsed.pages.length;
  const view = $("doc-view");
  view.innerHTML = "";
  let useImages = Boolean(pdfDoc);
  setReaderNote(useImages ? `Drawing page images · 0 of ${total}` :
    "Page images couldn't be drawn because PDF.js didn't load. Showing the text extracted on this machine instead.");

  for (const { page: n, text, layout } of state.parsed.pages) {
    if (drawId !== state.drawId) return false;
    const sheet = document.createElement("figure");
    sheet.className = "sheet";
    sheet.id = `sheet-${n}`;
    sheet.dataset.page = n;
    sheet.innerHTML = `<figcaption class="sheet__caption"><span>Page ${n} of ${state.parsed.pages.length}</span>
        <span>${layout.page_label ? `printed “${esc(layout.page_label)}”` : "no printed page number"}</span></figcaption>
      <div class="sheet__page"><div class="sheet__edge" hidden></div></div>`;
    view.appendChild(sheet);
    const pageEl = sheet.querySelector(".sheet__page");

    if (useImages && n <= pdfDoc.numPages) {
      try {
        await withTimeout(drawPage(pdfDoc, n, pageEl), PAGE_DRAW_TIMEOUT_MS);
        if (drawId !== state.drawId) return false;
        setReaderNote(n < total ? `Drawing page images · ${n} of ${total}` : "");
        renderOverlays();
        continue;
      } catch {
        if (drawId !== state.drawId) return false;
        useImages = false;  // slow or failed: show text for this and the remaining pages
        pageEl.querySelector(".sheet__canvas")?.remove();
        setReaderNote("Page images were taking too long, so the remaining pages show the text extracted on this machine.");
      }
    }
    pageEl.insertAdjacentHTML("beforeend", `<div class="sheet__text">${esc(text)}</div>`);
    state.pageGeom[n] = { w: layout.width_in * 72, h: layout.height_in * 72 };
  }
  if (useImages) setReaderNote("");
  return drawId === state.drawId;
}

async function drawPage(pdfDoc, n, pageEl) {
  const page = await pdfDoc.getPage(n);
  const base = page.getViewport({ scale: 1 });
  const scale = (720 * Math.min(window.devicePixelRatio || 1, 2)) / base.width;
  const viewport = page.getViewport({ scale });
  const canvas = document.createElement("canvas");
  canvas.className = "sheet__canvas";
  canvas.width = Math.floor(viewport.width);
  canvas.height = Math.floor(viewport.height);
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", `Page ${n} of the uploaded document`);
  pageEl.appendChild(canvas);
  await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
  state.pageGeom[n] = { w: base.width, h: base.height };
  state.textItems[n] = (await page.getTextContent()).items.map((it) => {
    const h = it.height || Math.hypot(it.transform[2], it.transform[3]);
    const [x0, y0] = base.convertToViewportPoint(it.transform[4], it.transform[5] + h);
    const [x1, y1] = base.convertToViewportPoint(it.transform[4] + it.width, it.transform[5] - h * 0.22);
    return { str: it.str, x0, y0, x1, y1 };
  });
}

/* Find a phrase in the PDF's text items and return boxes in page points. Approximate within a line. */
function phraseBoxes(n, phrase) {
  const items = state.textItems[n];
  const target = phrase.trim();
  if (!items || target.length < 2) return [];
  const boxes = [];
  for (const it of items) {
    let i = it.str.indexOf(target);
    if (i < 0) i = it.str.toLowerCase().indexOf(target.toLowerCase());
    if (i < 0) continue;
    const w = it.x1 - it.x0;
    const len = Math.max(it.str.length, 1);
    boxes.push({ x0: it.x0 + w * (i / len), x1: it.x0 + w * ((i + target.length) / len), y0: it.y0, y1: it.y1 });
  }
  return boxes;
}

function placeBox(pageEl, n, box, cls, key, title) {
  const g = state.pageGeom[n];
  if (!g) return;
  const el = document.createElement("span");
  el.className = `hl ${cls}`;
  el.dataset.key = key;
  el.title = title;
  el.style.left = `${(box.x0 / g.w) * 100}%`;
  el.style.top = `${(box.y0 / g.h) * 100}%`;
  el.style.width = `${((box.x1 - box.x0) / g.w) * 100}%`;
  el.style.height = `${((box.y1 - box.y0) / g.h) * 100}%`;
  pageEl.appendChild(el);
}

function renderOverlays() {
  const scored = scoredById();
  const diffs = pageDiffs();
  document.querySelectorAll(".sheet").forEach((sheet) => {
    const n = Number(sheet.dataset.page);
    const pageEl = sheet.querySelector(".sheet__page");
    pageEl.querySelectorAll(".hl").forEach((el) => el.remove());

    // Words changed in the prepared text (tokens and accepted rewrites).
    for (const run of diffs[n]?.removedRuns || []) {
      for (const b of phraseBoxes(n, run)) placeBox(pageEl, n, b, "hl--replaced", `replaced-${n}`, "Replaced in the prepared text");
    }
    // Details that still single out a participant.
    for (const p of state.scrubbed.participants) {
      const s = scored[p.id];
      if (!s || s.risk === "low" || !p.pages.includes(n)) continue;
      for (const [field, words] of Object.entries(p.mentions || {})) {
        if (!(field in s.attributes)) continue;  // already generalized
        for (const b of phraseBoxes(n, words)) {
          placeBox(pageEl, n, b, "hl--privacy", `p-${p.id}`, `${participantName(p.id)}: ${FIELD_LABEL[field] || field}`);
        }
      }
    }
    // Findings with regions.
    (state.review?.findings || []).forEach((f, i) => {
      if (f.page !== n) return;
      for (const b of f.bbox || []) {
        placeBox(pageEl, n, b, f.source === "llm" ? "hl--model" : "hl--format", `f-${i}`, f.issue);
      }
    });

    const edge = pageEl.querySelector(".sheet__edge");
    const status = pageStatus(n);
    edge.hidden = !status;
    edge.className = `sheet__edge sheet__edge--${status}`;
  });
}

$("doc-view").addEventListener("click", (e) => {
  const hl = e.target.closest(".hl");
  if (!hl) return;
  const key = hl.dataset.key;
  const n = Number(hl.closest(".sheet").dataset.page);
  if (key.startsWith("p-")) {
    focusParticipant(key.slice(2));
  } else if (key.startsWith("f-")) {
    selectTab("privacy");
    selectPage(n, { highlight: key });
    document.querySelector(`#panel-privacy .annot[data-key="${key}"]`)?.scrollIntoView({ block: "nearest" });
  } else {
    selectPage(n);
  }
});

/* ---------- word diff (original vs prepared) ---------- */
function splitWords(text) {
  const parts = String(text).split(/(\s+)/);
  const words = [];
  for (let i = 0; i < parts.length; i += 2) {
    if (parts[i] === "" && i === 0) { words.push({ w: "", sep: parts[i + 1] || "" }); continue; }
    if (parts[i] !== "") words.push({ w: parts[i], sep: parts[i + 1] || "" });
  }
  return words.filter((x) => x.w !== "" || x.sep !== "");
}

function lcsKeep(a, b) {
  const n = a.length, m = b.length;
  const keepA = new Uint8Array(n), keepB = new Uint8Array(m);
  if (n * m > DIFF_LIMIT) return null;
  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { keepA[i++] = 1; keepB[j++] = 1; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) i++;
    else j++;
  }
  return { keepA, keepB };
}

let diffCache = { key: null, value: null };
function pageDiffs() {
  if (!state.view) return {};
  const key = JSON.stringify(state.view.pages.map((p) => p.sent_to_llm));
  if (diffCache.key === key) return diffCache.value;
  const out = {};
  for (const p of state.view.pages) {
    const a = splitWords(p.original), b = splitWords(p.sent_to_llm);
    const keep = lcsKeep(a.map((x) => x.w), b.map((x) => x.w));
    const removedRuns = [];
    if (keep) {
      let run = [];
      a.forEach((x, i) => {
        if (!keep.keepA[i] && x.w) {
          run.push(x.w);
          if (x.sep.includes("\n")) { removedRuns.push(run.join(" ")); run = []; }
        } else if (run.length) { removedRuns.push(run.join(" ")); run = []; }
      });
      if (run.length) removedRuns.push(run.join(" "));
    }
    out[p.page] = { a, b, keep, removedRuns: removedRuns.map((r) => r.replace(/^[(“"']+|[),.;:”"']+$/g, "")) };
  }
  diffCache = { key, value: out };
  return out;
}

function markRuns(words, keepMask, renderWord, cls, joinLines = false) {
  let html = "", open = false;
  words.forEach((x, i) => {
    const changed = keepMask ? !keepMask[i] && x.w : false;
    if (changed && !open) { html += `<mark class="${cls}">`; open = true; }
    if (!changed && open) { html += "</mark>"; open = false; }
    html += renderWord(x.w);
    const next = words[i + 1];
    const nextChanged = next && keepMask ? !keepMask[i + 1] && next.w : false;
    if (open && !nextChanged) { html += "</mark>"; open = false; }
    // PDF text breaks lines mid-sentence; show single breaks as spaces, keep paragraph breaks.
    html += esc(joinLines && x.sep === "\n" ? " " : x.sep);
  });
  if (open) html += "</mark>";
  return html;
}

function renderPreparedWord(w) {
  return esc(w).replace(/\[[A-Z_]+_\d+\]/g, (t) => `<span class="tok">${t}</span>`);
}

/* ---------- compare view ---------- */
function renderCompare() {
  if (!state.view) return;
  const diffs = pageDiffs();
  const sentLabel = modelSentLabel();
  $("compare-view").innerHTML = `
    <div class="compare__head">
      <div><span class="label">Original · stays local</span><p>Text extracted on this machine. Never sent.</p></div>
      <div><span class="label">${esc(sentLabel)}</span>
        <p>${state.review?.model_review === "sent" ? "Exactly what the model received." : "What a review model would receive. Nothing has been sent."}</p></div>
    </div>
    ${state.view.pages.map((p) => {
      const d = diffs[p.page];
      const original = markRuns(d.a, d.keep?.keepA, esc, "d-old", true);
      const prepared = markRuns(d.b, d.keep?.keepB, renderPreparedWord, "d-new");
      return `<section class="compare__page" id="cmp-${p.page}" aria-label="Page ${p.page}">
        <p class="compare__pageno">Page ${p.page}</p>
        <div class="compare__cols">
          <div class="compare__col compare__col--original" data-label="Original · stays local">${original}</div>
          <div class="compare__col compare__col--prepared" data-label="${esc(sentLabel)}">${prepared}</div>
        </div></section>`;
    }).join("")}`;
}

/* ---------- inspector: privacy check ---------- */
function gateHtml() {
  const s = state.scored;
  if (s.checking) return `<div class="gate gate--blocked"><p class="gate__title">Privacy check in progress</p><p>The previous count no longer authorizes review. Waiting for the updated population check.</p></div>`;
  if (s.check_error) return `<div class="gate gate--blocked"><p class="gate__title">Privacy check incomplete · review blocked</p><p>${esc(s.check_error)}</p><button class="btn btn--secondary" data-action="retry-population">Retry population check</button></div>`;
  const high = s.participants.filter((p) => p.risk === "high");
  const medium = s.participants.filter((p) => p.risk === "medium");
  if (!s.gate_open) {
    return `<div class="gate gate--blocked">
      <p class="gate__title">Review is blocked</p>
      <p class="gate__body">${esc(joinNames(high.map((p) => participantName(p.id))))} can still be singled out
        (estimated k of 4 or fewer). Apply suggested rewrites to make ${high.length === 1 ? "that description" : "those descriptions"} less specific.</p>
      <div class="panel__actions"><button type="button" class="btn btn--secondary btn--small" data-focus="${esc(high[0].id)}">Show ${esc(participantName(high[0].id))}</button></div>
    </div>`;
  }
  const m = state.model;
  return `<div class="gate gate--ready">
    <p class="gate__title">Ready for review</p>
    ${medium.length ? `<p class="gate__body">${esc(joinNames(medium.map((p) => participantName(p.id))))}
      ${medium.length === 1 ? "is" : "are"} still in a narrow group (k between 5 and 19). You can continue, or apply the remaining suggestions first.</p>` : ""}
    <p class="gate__body">${m?.configured
      ? `Local format checks run automatically. Sending for model review shares the prepared text with <strong>${esc(m.model)}</strong>${m.endpoint ? ` at ${esc(m.endpoint)}` : ""}; the original text and the token key stay on this machine.`
      : "Local format checks run automatically and stay on this machine. No review model is configured, so nothing is sent to one."}</p>
    ${m?.configured ? `<div class="panel__actions"><button type="button" class="btn btn--primary" data-action="review">${state.review?.model_review === "sent" ? "Send for model review again" : "Send prepared text for model review"}</button></div>` : ""}
    <p class="gate__fine">“Ready” means no participant is above the high-risk threshold in this estimate. It does not guarantee anonymity.</p>
  </div>`;
}

function renderPrivacyPanel() {
  const scored = scoredById();
  const ids = state.scrubbed.direct_identifiers;
  const counts = {};
  new Map(ids.map((d) => [d.token, d])).forEach((d) => { counts[d.type] = (counts[d.type] || 0) + 1; });
  const idText = Object.entries(counts).map(([t, c]) => plural(c, ID_LABEL[t] || "identifier")).join(", ");

  const people = [...state.scrubbed.participants]
    .sort((a, b) => (RISK_ORDER[scored[a.id]?.risk] ?? 3) - (RISK_ORDER[scored[b.id]?.risk] ?? 3));
  const anySuggestions = state.scored.participants.some((p) => p.suggestions.length);
  // Image-only (likely scanned) pages carry content the local scrubber can't read.
  const scanPages = state.parsed.image_only_pages || [];

  $("panel-privacy").innerHTML = `
    <h2 class="panel__title">Privacy check</h2>
    <p class="panel__intro">${state.scored.population_source === "jiff"
      ? "Private comparison (JIFF demo). Estimates use fictional data."
      : "Standard comparison. Estimates use sample data."}
      <strong>k</strong> is the estimated number of people who fit the same description: the smaller it is, the easier that person is to single out.</p>
    <details class="explain"><summary>How to read k</summary>
      <p>k of 1–4: high risk, blocks review. k of 5–19: medium, a narrow group. k of 20 or more: low.
      These are estimates from synthetic data, not counts of real students, and a low k is a reason to rewrite rather than proof of identification.
      The data is fictional by design: its majors are invented and lemur species stand in for an identity group.</p></details>

    ${scanPages.length ? `<p class="notice notice--warning">
      ${plural(scanPages.length, "page")} (${scanPages.map((n) => `p. ${n}`).join(", ")})
      ${scanPages.length === 1 ? "is" : "are"} an image (likely a scan) with little or no selectable text, so the
      local privacy check can't read ${scanPages.length === 1 ? "its" : "their"} contents. Any names or details inside
      the image are <strong>not</strong> scrubbed. Replace with text-based pages before sending.</p>` : ""}

    <section class="panel__section">
      <span class="label">Direct identifiers</span>
      <p class="idsummary">${ids.length ? `<strong>${idText}</strong> replaced with placeholders. The key for restoring them is not sent to an AI reviewer.`
        : "No names, emails, phone numbers or student IDs were found."}</p>
    </section>

    <section class="panel__section">
      <span class="label">Described participants</span>
      ${people.length ? people.map((p) => concernHtml(p, scored[p.id])).join("")
        : `<p class="panel__empty">No participant descriptions were recognised. Descriptions are found when they name a participant, for example “Participant 3, a senior majoring in Clockmaking: Technology who identifies as Aye-aye…”.</p>`}
      ${anySuggestions ? `<div class="panel__actions"><button type="button" class="btn btn--secondary" data-action="apply-all">Apply all suggestions</button></div>` : ""}
    </section>
    ${gateHtml()}
    ${reviewFindingsHtml()}`;
}

function concernHtml(p, s) {
  if (!s) return "";
  const quote = p.evidence[0]?.quote || "";
  const mentions = Object.values(p.mentions || {}).filter(Boolean).sort((a, b) => b.length - a.length);
  let passage = esc(quote);
  for (const m of mentions) passage = passage.split(esc(m)).join(`<mark>${esc(m)}</mark>`);
  passage = passage.replace(TOKEN, (t) => `<span class="tok">${t}</span>`);
  const attrs = Object.entries(s.attributes).map(([f, v]) =>
    `<dt>${esc(FIELD_LABEL[f] || f)}</dt><dd>${esc(fieldValue(f, v))}</dd>`).join("");
  return `<article class="concern${state.focus === p.id ? " is-focused" : ""}" id="concern-${esc(p.id)}" tabindex="-1">
    <div class="concern__head">
      <h3 class="concern__who">${esc(participantName(p.id))}</h3>
      <button type="button" class="btn btn--quiet btn--small concern__where" data-page="${p.pages[0]}">p. ${p.pages.join(", ")}</button>
    </div>
    <p class="concern__k"><span class="risk risk--${s.risk}">${RISK_TEXT[s.risk]}</span> ·
      <strong>k ≈ ${s.k}</strong> ${s.k === 1 ? "person matches" : "people match"} this combination (estimate)</p>
    ${quote ? `<blockquote class="passage">${passage}</blockquote>` : ""}
    <dl class="attrs">${attrs}</dl>
    ${s.suggestions.length ? `<div class="rewrites" aria-label="Suggested rewrites">${s.suggestions.map((g) => `
      <div class="rewrite">
        <span class="rewrite__change">${esc(FIELD_LABEL[g.field] || g.field)}:
          <span class="rewrite__from">${esc(g.from)}</span><span class="rewrite__arrow" aria-label="becomes">→</span><span class="rewrite__to">${esc(g.to)}</span></span>
        <span class="rewrite__meta">${esc(LOSS[g.field] || "less specific")} · k ≈ ${s.k} → ${g.new_k}</span>
        <button type="button" class="btn btn--secondary btn--small" data-apply="${esc(p.id)}|${esc(g.field)}"
          aria-label="Apply: ${esc(FIELD_LABEL[g.field] || g.field)} ${esc(g.from)} becomes ${esc(g.to)}">Apply</button>
      </div>`).join("")}</div>`
      : `<p class="concern__ok">${s.risk === "low" ? "No rewrite needed at this level." : "No further generalization is available for these details."}</p>`}
  </article>`;
}

function focusParticipant(id) {
  state.focus = id;
  selectTab("privacy");
  showPane("inspector");
  renderPrivacyPanel();
  const p = state.scrubbed.participants.find((x) => x.id === id);
  if (p) selectPage(p.pages[0], { scroll: true, highlight: `p-${id}` });
  const el = $(`concern-${id}`);
  el?.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  el?.focus({ preventScroll: true });
}

async function applyFixes(fixes) {
  if (state.busy) return;
  $("work-error").hidden = true;
  state.scored = {...state.scored, gate_open:false, checking:true, check_error:null};
  state.review = null;
  state.rubricCheck = null;
  renderAll();
  setBusy(state.scored?.population_source === "jiff" ? "Comparing details privately · this can take a moment" : "Checking participant descriptions");
  try {
    state.scored = await request("/score", { method: "POST", body: { doc_id: state.parsed.doc_id, accepted: fixes } });
    setBusy("Preparing comparison");
    state.view = await request(`/llm-view/${state.parsed.doc_id}`);
    setBusy("");
    // Fixes can change pages/margins, so refresh the local format findings.
    state.formatCheckedFor = null;
    renderAll();
    if (state.focus) $(`concern-${state.focus}`)?.scrollIntoView({ block: "nearest" });
    maybeAutoFormatCheck();
  } catch (err) {
    setBusy("");
    if (state.scored) {
      state.scored = {...state.scored, gate_open:false, checking:false, check_error:err.message};
      renderAll();
    }
    showWorkError(err, () => applyFixes(fixes));
  }
}

$("inspector").addEventListener("click", (e) => {
  const t = e.target.closest("button");
  if (!t || t.disabled) return;
  if (t.dataset.action === "retry-population") {
    applyFixes([]);
  } else if (t.dataset.apply) {
    const [participant_id, field] = t.dataset.apply.split("|");
    state.focus = participant_id;
    applyFixes([{ participant_id, field }]);
  } else if (t.dataset.key && t.classList.contains("annot")) {
    openFinding(t.dataset.key);
  } else if (t.dataset.action === "apply-all") {
    applyFixes(state.scored.participants.flatMap((p) => p.suggestions.map((g) => ({ participant_id: p.id, field: g.field }))));
  } else if (t.dataset.action === "review") {
    runReview();
  } else if (t.dataset.focus) {
    focusParticipant(t.dataset.focus);
  } else if (t.dataset.page && t.closest("#panel-privacy")) {
    selectPage(Number(t.dataset.page), { scroll: true });
    showPane("reader");
  }
});

/* ---------- inspector: review ---------- */
function annotationHtml(f, i) {
  const kind = f.source === "llm" ? "model" : "format";
  return `<button type="button" class="annot annot--${kind}" data-key="f-${i}" data-page="${f.page}">
    <span class="annot__meta"><span class="num">p. ${f.page}</span>
      <span class="annot__src">${kind === "model" ? "Model review" : "Local rule"}</span>
      <span>${f.severity === "error" ? "Error" : "Warning"}</span></span>
    <span class="annot__issue" style="display:block">${esc(f.issue)}</span>
    ${f.quote ? `<span class="annot__passage" style="display:block">${esc(f.quote)}</span>` : ""}
    <span class="annot__criterion" style="display:block">Criterion: <q>${esc(f.criterion)}</q></span>
    ${f.bbox?.length ? "" : `<span class="annot__scope" style="display:block">Applies to the whole page</span>`}
  </button>`;
}

function modelNote() {
  const r = state.review;
  if (r.model_review === "sent") return `Reviewed by <strong>${esc(r.model)}</strong>. Findings marked “Model review” came from it; tokens were restored on this machine.`;
  if (r.model_review === "failed") return `The request to ${esc(r.model)} failed (${esc(r.model_error || "no detail")}). The prepared text may have reached the endpoint, but no findings came back. Only local rules are shown.`;
  if (r.model_review === "not_implemented") return `A model (${esc(r.model)}) is configured, but model review isn't implemented in this build yet. Nothing was sent; only local rules ran.`;
  return "";
}

// Review findings, embedded in the Privacy check panel (there is no separate
// Review tab). Returns "" before a review has run; the gate button that starts
// a review lives in gateHtml().
function reviewFindingsHtml() {
  const r = state.review;
  if (!r) return "";
  const rules = r.findings.filter((f) => f.source === "rule").length;
  const model = r.findings.filter((f) => f.source === "llm").length;
  return `<section class="panel__section review-findings">
    <span class="label">Review findings</span>
    <p class="review-summary">${plural(rules, "local rule finding")}${r.model_review === "sent" ? ` · ${plural(model, "model finding")}` : ""}</p>
    ${r.findings.length ? r.findings.map((f, i) => annotationHtml(f, i)).join("")
      : `<p class="panel__empty">No findings. The checks that ran found nothing to flag.</p>`}
  </section>`;
}

function openFinding(key) {
  const i = Number(key.slice(2));
  const f = state.review.findings[i];
  if (state.tab !== "privacy") selectTab("privacy");
  selectPage(f.page, { scroll: true, highlight: key });
  showPane("reader");
}

/* ---------- inspector: rubric check ---------- */
// Loads the JSON produced by the `rubric_parsing` package
// ({"rubric": [{parameter_title, description, points?}, ...]}),
// renders it as a table, then (via /rubric-check) asks the configured model
// whether the prepared document fulfils each criterion and fills in the result.

function normalizeRubric(raw) {
  // Accept either {"rubric": [...]} (the package output) or a bare array.
  const rows = Array.isArray(raw) ? raw : Array.isArray(raw?.rubric) ? raw.rubric : null;
  if (!rows) throw new Error('Expected a JSON object with a "rubric" array.');
  const out = rows.map((r, i) => {
    if (!r || typeof r !== "object") throw new Error(`Criterion ${i + 1} is not an object.`);
    const title = r.parameter_title;
    const description = r.description;
    if (typeof title !== "string" || !title.trim()) throw new Error(`Criterion ${i + 1} has no "parameter_title".`);
    const out = { parameter_title: title.trim(), description: typeof description === "string" ? description.trim() : "" };
    if (r.points !== undefined && r.points !== null && r.points !== "") {
      const pts = Number(r.points);
      if (!Number.isNaN(pts)) out.points = pts;
    }
    return out;
  });
  if (!out.length) throw new Error("The rubric has no criteria.");
  return out;
}

function loadRubricFromText(text, sourceName) {
  state.rubricError = null;
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    state.rubric = null;
    state.rubricCheck = null;
    state.rubricError = "That file is not valid JSON. Export the rubric with the rubric_parsing tool and load its .json output.";
    renderAll();
    return;
  }
  try {
    state.rubric = normalizeRubric(parsed);
    state.rubricCheck = null;
    state.rubricSource = sourceName || "rubric.json";
  } catch (err) {
    state.rubric = null;
    state.rubricCheck = null;
    state.rubricError = err.message;
  }
  renderAll();
  selectTab("rubric");
}

function rubricStatusNote() {
  const c = state.rubricCheck;
  if (!c) return "";
  if (c.model_review === "sent") return `Compared against the prepared text by <strong>${esc(c.model || "the model")}</strong>. Only tokenized, gate-approved text was sent.`;
  if (c.model_review === "not_implemented") return "A model is configured but the comparison call is not implemented yet, so nothing was sent.";
  return "No review model is configured, so nothing was sent. Configure a model to fill in the results.";
}

function rubricVerdict(row) {
  // `row` may be a plain boolean (legacy) or a result object with needs_more_info.
  if (row && typeof row === "object") {
    if (row.needs_more_info) return `<span class="verdict verdict--info">Not enough information</span>`;
    return rubricVerdict(row.fulfilled);
  }
  const fulfilled = row;
  if (fulfilled === true) return `<span class="verdict verdict--yes">Fulfilled</span>`;
  if (fulfilled === false) return `<span class="verdict verdict--no">Not fulfilled</span>`;
  return `<span class="verdict verdict--unknown">—</span>`;
}

// Mirror of the backend check: a criterion that refers to an image/figure cannot
// be judged from the prepared text (no image content), so it is "not enough
// information". Detected client-side too, so the tag shows as soon as the rubric
// loads, before any model check runs.
const RUBRIC_IMAGE_RE = /\b(image|figure|diagram|chart|graph|photo|photograph|picture|illustration|screenshot|visual|plot|infographic)s?\b/i;

function rubricReferencesImage(row) {
  return RUBRIC_IMAGE_RE.test(`${row.parameter_title || ""} ${row.description || ""}`);
}

function rubricTableHtml() {
  // Prefer checked results (with verdict + comment); fall back to the loaded rubric.
  const rows = state.rubricCheck?.results || state.rubric.map((c) => ({ ...c, fulfilled: null, comment: "" }));
  const hasPoints = rows.some((r) => r.points !== undefined && r.points !== null);
  const checked = Boolean(state.rubricCheck);
  const header = `<tr>
      <th scope="col">Criterion</th>
      <th scope="col">Description</th>
      ${hasPoints ? `<th scope="col" class="rubric__pts">Points</th>` : ""}
      <th scope="col">Result</th>
      <th scope="col">Comment</th>
    </tr>`;
  const body = rows.map((r) => {
    // needs_more_info comes from the backend after a check; detect it locally too
    // so an image-referencing criterion is tagged the moment the rubric loads.
    const needsInfo = r.needs_more_info || rubricReferencesImage(r);
    const verdict = needsInfo
      ? rubricVerdict({ needs_more_info: true })
      : rubricVerdict(checked ? r.fulfilled : null);
    const fallbackComment = needsInfo && !r.comment
      ? "This criterion refers to an image or figure, which is not present in the prepared text."
      : "";
    const comment = r.comment || fallbackComment;
    const rowClass = needsInfo
      ? "is-info"
      : checked && r.fulfilled === true ? "is-yes"
      : checked && r.fulfilled === false ? "is-no"
      : "";
    return `<tr${rowClass ? ` class="${rowClass}"` : ""}>
      <th scope="row" class="rubric__title">${esc(r.parameter_title)}</th>
      <td class="rubric__desc">${esc(r.description || "")}</td>
      ${hasPoints ? `<td class="rubric__pts">${r.points ?? ""}</td>` : ""}
      <td class="rubric__verdict">${verdict}</td>
      <td class="rubric__comment">${comment ? esc(comment) : `<span class="muted">—</span>`}</td>
    </tr>`;
  }).join("");
  return `<table class="rubric-table"><caption class="visually-hidden">Rubric criteria and whether the document fulfils each</caption>
    <thead>${header}</thead><tbody>${body}</tbody></table>`;
}

function renderRubricPanel() {
  const gateReady = Boolean(state.scored?.gate_open);
  const m = state.model;
  const loadControls = `
    <div class="rubric-load">
      <div class="rubric-load__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 11h6M9 15h4"/><path d="M14 3v4a1 1 0 0 0 1 1h4"/>
          <path d="M5 3h9l5 5v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/>
        </svg>
      </div>
      <div class="rubric-load__body">
        <div class="rubric__controls">
          <label for="rubric-raw" class="btn btn--secondary btn--small">${state.rubric ? "Parse a different rubric file" : "Parse rubric file"}</label>
          <input type="file" id="rubric-raw" class="visually-hidden" accept=".pdf,.docx,.txt,.md,.markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown">
          ${state.rubricSource ? `<span class="rubric__source">${esc(state.rubricSource)}</span>` : ""}
        </div>
        <p class="rubric__controls-hint">Parse a rubric document (PDF, Word, text or Markdown). It is converted and structured into criteria locally, then each one is checked against the prepared document.</p>
      </div>
    </div>`;

  if (state.rubricError) {
    $("panel-rubric").innerHTML = `<div class="rubric-scene">
      <header class="panel__head"><h2 class="panel__title">Rubric</h2></header>
      <p class="panel__intro">The rubric grading system reads a grading rubric, breaks it into individual criteria, and checks whether this document meets each one — reporting a verdict and comment per criterion.</p>
      ${loadControls}
      <div class="notice notice--error" role="alert">${esc(state.rubricError)}</div>
    </div>`;
    return;
  }

  if (!state.rubric) {
    $("panel-rubric").innerHTML = `<div class="rubric-scene">
      <header class="panel__head"><h2 class="panel__title">Rubric</h2></header>
      <p class="panel__intro">The rubric grading system turns a grading rubric into a checklist and evaluates your document against it. Each criterion is listed in a table, and the configured model marks whether the document fulfils it, gives a short comment, and flags anything it can't judge from the text. Only tokenized, gate-approved text is ever sent for the check.</p>
      ${loadControls}
      <div class="rubric-empty">
        <svg class="rubric-empty__art" viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18"/><path d="M8 4v16"/>
        </svg>
        <p class="rubric-empty__title">No rubric loaded yet</p>
        <p class="rubric-empty__hint">Parse a rubric document to turn it into criteria, then check your document against each one.</p>
      </div>
    </div>`;
    return;
  }

  const checkLabel = state.rubricCheck ? "Check again" : "Check document against rubric";
  const canCheck = gateReady;
  const action = `<div class="panel__actions rubric-actions">
      <button type="button" class="btn btn--primary" data-action="rubric-check" ${canCheck ? "" : "disabled"}>${checkLabel}</button>
      <button type="button" class="btn btn--secondary" data-action="rubric-popout">Open in new window</button>
      ${m && !m.configured ? `<span class="rubric__hint">No model configured — the table loads, but results stay blank until one is set.</span>` : ""}
    </div>`;
  const gateBlocked = !gateReady
    ? `<div class="notice notice--info">The privacy gate is closed. Resolve high-risk participants in the Privacy check tab before comparing against the model.</div>`
    : "";
  const statusNote = state.rubricCheck ? `<div class="notice notice--info">${rubricStatusNote()}</div>` : "";

  $("panel-rubric").innerHTML = `<div class="rubric-scene">
    <header class="panel__head">
      <h2 class="panel__title">Rubric</h2>
      <span class="rubric-count">${plural(state.rubric.length, "criterion", "criteria")}</span>
    </header>
    <p class="panel__intro">${state.rubricCheck ? "The model's verdict and comment are shown per row." : "Run the check to have the model fill in each row."}</p>
    ${loadControls}
    ${gateBlocked}
    ${statusNote}
    <section class="panel__section rubric__tablewrap">${rubricTableHtml()}</section>
    ${action}
  </div>`;

  // Keep a popped-out rubric window in sync (e.g. after a model check).
  if (rubricWindowRef && !rubricWindowRef.closed) renderRubricWindow(rubricWindowRef);
}

// File inputs are recreated on each render, so delegate the change event.
$("panel-rubric").addEventListener("change", (e) => {
  const rawInput = e.target.closest("#rubric-raw");
  if (rawInput && rawInput.files?.length) {
    parseRubricFile(rawInput.files[0]);
  }
});

// Parse a raw rubric document (docx/pdf/txt/md) server-side, then pipe the
// structured result straight into the rubric table + check flow.
async function parseRubricFile(file) {
  if (state.busy) return;
  $("work-error").hidden = true;
  state.rubricError = null;
  setBusy(`Parsing ${file.name}`);
  try {
    const form = new FormData();
    form.append("file", file);
    const parsed = await request("/rubric-parse", { method: "POST", form });
    state.rubric = parsed.rubric;
    state.rubricCheck = null;
    state.rubricSource = file.name;
    setBusy("");
    renderAll();
    selectTab("rubric");
  } catch (err) {
    setBusy("");
    // Surface the problem inside the rubric panel rather than the generic banner.
    state.rubric = null;
    state.rubricCheck = null;
    state.rubricError = err.status === 503
      ? "No model is configured to structure the rubric. Set a model, then parse again. (The rubric parser uses the LLM only on the rubric text, never the document.)"
      : `Could not parse that rubric file: ${err.message}`;
    renderAll();
    selectTab("rubric");
  }
}

$("panel-rubric").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-action='rubric-check']");
  if (b && !b.disabled) runRubricCheck();
  const pop = e.target.closest("button[data-action='rubric-popout']");
  if (pop) openRubricWindow();
});

// Pop the rubric table into its own window so the whole rubric is visible at once,
// free of the inspector's width. The window is self-contained (inline styles), so
// it keeps rendering after the opener navigates; it is auto-refreshed on each app
// render (e.g. after a model check), and a "Refresh from app" button pulls the
// latest table on demand.
let rubricWindowRef = null;

function openRubricWindow() {
  if (!state.rubric) return;
  const win = window.open("", "stranger-rubric", "width=1000,height=800,resizable=yes,scrollbars=yes");
  if (!win) {
    showWorkError(new Error("The browser blocked the pop-out window. Allow pop-ups for this page and try again."));
    return;
  }
  rubricWindowRef = win;
  renderRubricWindow(win);
  // Let the window ask for a fresh copy of the current table.
  win.__refreshRubric = () => renderRubricWindow(win);
}

function rubricWindowStyles() {
  return `
    :root { color-scheme: light; }
    * { box-sizing: border-box; }
    body { margin: 0; padding: 28px 32px; font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; color: #282c29; background: #f7f6f2; }
    .head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 6px; }
    h1 { font-size: 22px; margin: 0; }
    .meta { color: #6b7169; font-size: 13px; margin: 0 0 18px; }
    .refresh { font: 13px system-ui, sans-serif; padding: 6px 12px; border: 1px solid #c9ccc4; border-radius: 8px; background: #fff; cursor: pointer; }
    .refresh:hover { background: #eef0ea; }
    table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d9dcd4; border-radius: 10px; overflow: hidden; }
    th, td { text-align: left; vertical-align: top; padding: 11px 14px; border-bottom: 1px solid #e6e8e1; }
    thead th { font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: #6b7169; background: #eef0ea; }
    tbody tr:last-child th, tbody tr:last-child td { border-bottom: 0; }
    .t-title { font-weight: 600; }
    .t-desc, .t-comment { color: #41463f; }
    .t-pts { text-align: right; white-space: nowrap; }
    .verdict { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap; }
    .verdict--yes { background: #e4f3e6; color: #2f7d3b; }
    .verdict--no { background: #f6e4e3; color: #a63d33; }
    .verdict--info { background: #fbf2dd; color: #8a6d1f; }
    .verdict--unknown { background: #eef0ea; color: #6b7169; }
    .muted { color: #9aa095; }
  `;
}

function rubricWindowVerdict(row, checked) {
  const needsInfo = row.needs_more_info || rubricReferencesImage(row);
  if (needsInfo) return `<span class="verdict verdict--info">Not enough information</span>`;
  const f = checked ? row.fulfilled : null;
  if (f === true) return `<span class="verdict verdict--yes">Fulfilled</span>`;
  if (f === false) return `<span class="verdict verdict--no">Not fulfilled</span>`;
  return `<span class="verdict verdict--unknown">—</span>`;
}

function renderRubricWindow(win) {
  if (!win || win.closed || !state.rubric) return;
  const rows = state.rubricCheck?.results || state.rubric.map((c) => ({ ...c, fulfilled: null, comment: "" }));
  const checked = Boolean(state.rubricCheck);
  const hasPoints = rows.some((r) => r.points !== undefined && r.points !== null);
  const header = `<tr>
      <th>Criterion</th><th>Description</th>
      ${hasPoints ? `<th class="t-pts">Points</th>` : ""}
      <th>Result</th><th>Comment</th>
    </tr>`;
  const body = rows.map((r) => {
    const needsInfo = r.needs_more_info || rubricReferencesImage(r);
    const fallback = needsInfo && !r.comment
      ? "This criterion refers to an image or figure, which is not present in the prepared text."
      : "";
    const comment = r.comment || fallback;
    return `<tr>
      <th class="t-title">${esc(r.parameter_title)}</th>
      <td class="t-desc">${esc(r.description || "")}</td>
      ${hasPoints ? `<td class="t-pts">${r.points ?? ""}</td>` : ""}
      <td>${rubricWindowVerdict(r, checked)}</td>
      <td class="t-comment">${comment ? esc(comment) : `<span class="muted">—</span>`}</td>
    </tr>`;
  }).join("");
  const count = plural(state.rubric.length, "criterion", "criteria");
  const statusLine = state.rubricCheck
    ? "Checked against the prepared text. Only tokenized, gate-approved text was sent."
    : "Not yet checked — run the check in the app to fill in results.";
  win.document.open();
  win.document.write(`<!doctype html><html lang="en"><head>
    <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Rubric — StrangerThesis</title><style>${rubricWindowStyles()}</style></head>
    <body>
      <div class="head">
        <h1>Rubric</h1>
        <button type="button" class="refresh" onclick="window.opener && !window.opener.closed && window.opener.__refreshRubric && window.opener.__refreshRubric()">Refresh from app</button>
      </div>
      <p class="meta">${count} loaded${state.rubricSource ? ` — ${esc(state.rubricSource)}` : ""}. ${statusLine}</p>
      <table><thead>${header}</thead><tbody>${body}</tbody></table>
    </body></html>`);
  win.document.close();
}

async function runRubricCheck() {
  if (state.busy || !state.rubric || !state.parsed) return;
  $("work-error").hidden = true;
  setBusy(state.model?.configured ? "Comparing the document against the rubric" : "Loading rubric (no model configured)");
  try {
    state.rubricCheck = await request(`/rubric-check/${state.parsed.doc_id}`, {
      method: "POST",
      body: { rubric: state.rubric },
    });
    setBusy("");
    renderAll();
    selectTab("rubric");
  } catch (err) {
    setBusy("");
    if (err.status === 403) {
      state.scored = await request("/score", { method: "POST", body: { doc_id: state.parsed.doc_id, accepted: [] } }).catch(() => state.scored);
      renderAll();
    }
    if (state.scored) renderAll();
    showWorkError(err, () => runRubricCheck());
  }
}

async function runReview() {
  if (state.busy) return;
  $("work-error").hidden = true;
  setBusy(state.model?.configured ? "Running local rules and model review" : "Running local format rules");
  try {
    state.review = await request("/review", { method: "POST", body: { doc_id: state.parsed.doc_id } });
    setBusy("");
    renderAll();
    selectTab("privacy");
    document.querySelector("#panel-privacy .review-findings")?.scrollIntoView({ block: "start" });
  } catch (err) {
    setBusy("");
    if (err.status === 403) {
      state.scored = await request("/score", { method: "POST", body: { doc_id: state.parsed.doc_id, accepted: [] } }).catch(() => state.scored);
      renderAll();
    }
    if (state.scored) renderAll();
    showWorkError(err, () => runReview());
  }
}

// Local format checks run automatically (no network): as soon as the privacy gate
// is open, fetch format-rule findings with format_only so nothing is sent to a
// model. Re-runs after fixes change the gate/pages. The model review stays an
// explicit user action (see the gate button, only shown when a model is set).
async function maybeAutoFormatCheck() {
  if (state.busy || !state.parsed || !state.scored?.gate_open) return;
  if (state.formatCheckedFor === state.parsed.doc_id && state.review) return;
  try {
    state.review = await request("/review", {
      method: "POST",
      body: { doc_id: state.parsed.doc_id, format_only: true },
    });
    state.formatCheckedFor = state.parsed.doc_id;
    renderAll();
  } catch (err) {
    if (state.scored?.check_error) {
      renderAll();
      showWorkError(err, () => applyFixes([]));
    }
  }
}

/* ---------- settings: configure the review/rubric LLM ---------- */
// Lets the user pick ChatGPT (OpenAI), Google Gemini, Anthropic Claude, or a
// custom/local OpenAI-compatible endpoint, set the model + API key, and test it.
// All three hosted providers are reached through the same OpenAI-compatible client.
const settings = {
  providers: [],       // [{ id, label, base_url, default_model, key_hint, models }]
  current: null,       // { configured, provider, base_url, endpoint, model, has_api_key }
};

async function refreshModelStatus() {
  try {
    const status = await request("/status");
    state.model = status.model;
  } catch { /* leave as-is */ }
  renderModelStatus();
}

function settingsProvider() {
  return settings.providers.find((p) => p.id === $("settings-provider").value);
}

function settingsFeedback(text, kind) {
  const el = $("settings-feedback");
  if (!text) { el.hidden = true; el.textContent = ""; return; }
  el.className = `notice notice--${kind || "info"}`;
  el.textContent = text;
  el.hidden = false;
}

function renderSettingsProviderFields() {
  const p = settingsProvider();
  if (!p) return;
  // Model: a dropdown of presets plus a free-text fallback.
  const modelSel = $("settings-model");
  const customInput = $("settings-model-custom");
  const hasPresets = p.models && p.models.length;
  modelSel.hidden = !hasPresets;
  if (hasPresets) {
    const opts = p.models.map((m) => `<option value="${esc(m)}">${esc(m)}</option>`).join("")
      + `<option value="__custom__">Other…</option>`;
    modelSel.innerHTML = opts;
    // Preselect the current model if it belongs to this provider, else the default.
    const cur = settings.current;
    if (cur?.provider === p.id && cur.model && p.models.includes(cur.model)) modelSel.value = cur.model;
    else modelSel.value = p.default_model || p.models[0];
    customInput.hidden = modelSel.value !== "__custom__";
    if (customInput.hidden) customInput.value = "";
  } else {
    customInput.hidden = false;
    customInput.value = (settings.current?.provider === p.id && settings.current.model) || p.default_model || "";
  }
  // Base URL: only for custom.
  const custom = p.id === "custom";
  $("settings-baseurl-field").hidden = !custom;
  if (custom && settings.current?.provider === "custom") $("settings-baseurl").value = settings.current.base_url || "";
  // Key hint + placeholder (don't reveal the stored key, just whether one exists).
  $("settings-key-hint").textContent = p.key_hint || "";
  $("settings-key").placeholder = settings.current?.has_api_key && settings.current.provider === p.id
    ? "A key is saved — leave blank to keep it" : "";
}

function chosenModel() {
  const modelSel = $("settings-model");
  const customInput = $("settings-model-custom");
  if (!modelSel.hidden && modelSel.value !== "__custom__") return modelSel.value;
  return customInput.value.trim();
}

async function loadSettings() {
  const [prov, cur] = await Promise.all([
    request("/settings/providers").then((r) => r.providers).catch(() => []),
    request("/settings").catch(() => null),
  ]);
  settings.providers = prov;
  settings.current = cur;
  $("settings-provider").innerHTML = prov.map((p) => `<option value="${esc(p.id)}">${esc(p.label)}</option>`).join("");
  if (cur?.provider) $("settings-provider").value = cur.provider;
  renderSettingsProviderFields();
  settingsFeedback(cur?.configured ? `Current: ${cur.model}${cur.endpoint ? ` (${cur.endpoint})` : ""}` : "No model configured yet.", "info");
}

function openSettings() {
  loadSettings();
  const dlg = $("settings-dialog");
  if (typeof dlg.showModal === "function") dlg.showModal();
  else dlg.setAttribute("open", "");
}

function closeSettings() {
  const dlg = $("settings-dialog");
  if (typeof dlg.close === "function") dlg.close();
  else dlg.removeAttribute("open");
}

async function saveSettings() {
  const p = settingsProvider();
  if (!p) return;
  const model = chosenModel();
  if (!model) { settingsFeedback("Enter a model name.", "error"); return; }
  const keyField = $("settings-key").value;
  const body = {
    provider: p.id,
    model,
    // Empty field means "keep existing key"; send null for that. A typed value sets it.
    api_key: keyField === "" ? null : keyField,
  };
  if (p.id === "custom") body.base_url = $("settings-baseurl").value.trim();
  try {
    settingsFeedback("Saving…", "info");
    settings.current = await request("/settings", { method: "PUT", body });
    $("settings-key").value = "";
    await refreshModelStatus();
    renderAll();
    renderSettingsProviderFields();
    settingsFeedback(`Saved. Using ${settings.current.model}${settings.current.endpoint ? ` (${settings.current.endpoint})` : ""}.`, "info");
  } catch (err) {
    settingsFeedback(err.message, "error");
  }
}

async function testSettings() {
  try {
    settingsFeedback("Testing…", "info");
    const r = await request("/settings/test", { method: "POST" });
    settingsFeedback(r.ok ? `Connection OK — ${r.detail}` : `Model did not respond: ${r.detail}`, r.ok ? "info" : "error");
  } catch (err) {
    settingsFeedback(err.status === 400 ? "Save a model first, then test." : err.message, "error");
  }
}

async function clearSettings() {
  try {
    settings.current = await request("/settings", { method: "DELETE" });
    $("settings-key").value = "";
    await refreshModelStatus();
    renderAll();
    renderSettingsProviderFields();
    settingsFeedback("Cleared. No model is configured, so nothing will be sent.", "info");
  } catch (err) {
    settingsFeedback(err.message, "error");
  }
}

$("open-settings").addEventListener("click", openSettings);
$("settings-close").addEventListener("click", closeSettings);
$("settings-provider").addEventListener("change", () => { renderSettingsProviderFields(); settingsFeedback(""); });
$("settings-model").addEventListener("change", () => {
  $("settings-model-custom").hidden = $("settings-model").value !== "__custom__";
});
$("settings-save").addEventListener("click", saveSettings);
$("settings-test").addEventListener("click", testSettings);
$("settings-clear").addEventListener("click", clearSettings);

/* ---------- source-aware setup ---------- */
async function refreshPopulationSetup() {
  state.populationSource = $("population-source").value;
  state.setupBlocked = true;
  $("start").disabled = true;
  $("open-sample").disabled = true;
  $("population-source").disabled = true;
  $("population-source").setAttribute("aria-busy", "true");
  $("population-retry").disabled = true;
  $("population-retry").hidden = true;
  $("population-note").textContent = state.populationSource === "jiff"
    ? "Compare participant details without sending them in readable form to the data holder. This demo uses fictional data."
    : "Compare participant details with a sample dataset to see how easily someone could stand out.";
  try {
    setLocalStatus("Getting your privacy check ready");
    const status = await request(`/status?source=${state.populationSource}`);
    state.model = status.model;
    const jiff = status.population_sources?.jiff;
    const jiffOption = $("population-source").querySelector('option[value="jiff"]');
    if (jiff) {
      jiffOption.disabled = jiff.configured === false && state.populationSource !== "jiff";
      jiffOption.textContent = jiff.available ? "Private comparison (JIFF demo)"
        : jiff.configured ? "Private comparison · try again shortly" : "Private comparison · unavailable";
      if (!jiff.available && state.populationSource === "jiff") {
        $("population-note").textContent = jiff.configured
          ? "The private comparison isn’t ready right now. Try again in a moment, or choose Standard comparison."
          : "Private comparison isn’t available here. Please choose Standard comparison.";
      }
      $("population-retry").hidden = jiff.available || state.populationSource !== "jiff";
    }
    const hosted = status.deployment_mode === "hosted-demo";
    $("deployment-notice").hidden = !hosted;
    $("upload-hint").textContent = hosted
      ? "Your file will be checked on this website’s server."
      : "Your file will be checked by the server running on your computer.";
    state.setupBlocked = !status.setup?.ready;
    if (state.setupBlocked) {
      showIntakeError(state.populationSource === "jiff"
        ? "The private comparison isn’t ready. Try again in a moment, or choose Standard comparison."
        : "The standard comparison isn’t ready. Choose Private comparison if available, or try again later.",
      status.setup.issues.join(" · "));
      setLocalStatus("Check unavailable · try again or change the method");
    } else {
      $("intake-error").hidden = true;
      setLocalStatus("Ready for a document");
    }
  } catch (err) {
    showIntakeError(err.message);
  } finally {
    $("population-source").disabled = false;
    $("population-source").setAttribute("aria-busy", "false");
    $("population-retry").disabled = false;
    if (state.setupBlocked) $("population-retry").hidden = false;
    $("open-sample").disabled = state.setupBlocked;
    $("start").disabled = state.setupBlocked || !state.file;
    renderModelStatus();
  }
}
$("population-source").addEventListener("change", refreshPopulationSetup);
$("population-retry").addEventListener("click", refreshPopulationSetup);
refreshPopulationSetup();
