/* ThesisGuard workspace.
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

const FIELD_LABEL = {
  IRage: "Age", IRagecol: "Age band", class: "Class year", MAJfirstcode: "Major", MAJfirstcol: "Major group",
  country22: "Country", countrycol22: "Region", internat: "International student", living18: "Housing",
  athlete: "Student-athlete", IRsex19: "Sex", firstgen: "First-generation",
};
const LOSS = {
  IRage: "exact age → age band",
  country22: "country → world region",
  countrycol22: "region → “international student”",
  MAJfirstcode: "major → major group",
};
const ID_LABEL = { PERSON: "name", EMAIL: "email", PHONE: "phone number", STUDENT_ID: "student ID", OTHER: "identifier" };
const RISK_TEXT = { high: "High risk", medium: "Medium risk", low: "Low risk" };
const RISK_ORDER = { high: 0, medium: 1, low: 2 };

const state = {
  model: null,          // { configured, model, endpoint }
  file: null, isSample: false,
  parsed: null, scrubbed: null, scored: null, view: null, review: null,
  pdfDoc: null, pageGeom: {}, textItems: {},
  page: 1, tab: "document", compare: false, focus: null, busy: false,
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
    throw Object.assign(new Error("The local server isn't responding. Check that it is running, then try again."), { status: 0 });
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* not JSON */ }
    throw Object.assign(new Error(detail), { status: res.status });
  }
  return res.json();
}

const participantName = (id) => `Participant ${Number(String(id).replace(/\D/g, ""))}`;
const fileSize = (n) => n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(1)} MB`;
const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const fieldValue = (field, v) => (field === "internat" || field === "athlete" || field === "firstgen")
  ? (Number(v) === 1 ? "Yes" : "No") : v;

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
  if (!m) text = "Configuration unavailable";
  else if (state.review?.model_review === "sent") text = `Prepared text sent to ${state.review.model}`;
  else if (state.review?.model_review === "not_implemented") text = `${m.model} configured · model review not implemented, nothing sent`;
  else if (state.review) text = "Not configured · nothing was sent";
  else if (m.configured) text = `${m.model}${m.endpoint ? ` (${m.endpoint})` : ""} · nothing sent yet`;
  else text = "Not configured · nothing will be sent";
  $("status-model").textContent = text;
}

/* ---------- intake ---------- */
function showIntakeError(message) {
  $("intake-error").innerHTML = `${esc(message)}`;
  $("intake-error").hidden = false;
}

function chooseFile(file) {
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
    const res = await fetch("/sample");
    if (!res.ok) throw new Error("The sample document isn't available on the local server.");
    const blob = await res.blob();
    const file = new File([blob], "test-thesis.pdf", { type: "application/pdf" });
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
  if (busy) setLocalStatus(step);
}

async function startCheck(file, isSample = false) {
  state.file = file;
  state.isSample = isSample;
  $("intake-error").hidden = true;
  try {
    setIntakeBusy(true, "Parsing PDF");
    const form = new FormData();
    form.append("file", file, file.name);
    const [parsed, pdfDoc] = await Promise.all([request("/parse", { method: "POST", form }), openPdf(file)]);
    state.parsed = parsed;
    state.pdfDoc = pdfDoc;

    setIntakeBusy(true, "Checking identifiers");
    setLocalStatus("Checking identifiers");
    state.scrubbed = await request(`/scrub/${parsed.doc_id}`, { method: "POST" });

    setIntakeBusy(true, "Estimating risk");
    state.scored = await request("/score", { method: "POST", body: { doc_id: parsed.doc_id, accepted: [] } });

    setIntakeBusy(true, "Preparing comparison");
    state.view = await request(`/llm-view/${parsed.doc_id}`);
    state.review = null;

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
  setLocalStatus(`Checked on this machine · ${plural(n, "page")}`);

  const scored = state.scored.participants;
  const firstConcern = state.scrubbed.participants.find((p) => scoredById()[p.id]?.risk === "high");
  state.page = firstConcern ? firstConcern.pages[0] : 1;

  // Navigation and findings first; page images can take a moment to draw.
  $("doc-view").innerHTML = "";
  renderAll();
  selectTab(scored.some((p) => p.risk !== "low") ? "privacy" : "document");
  setBusy("Drawing pages");
  await renderDocument();
  setBusy("");
  renderAll();
  selectPage(state.page, { scroll: true });
}

function renderAll() {
  renderModelStatus();
  renderSidebar();
  renderOverlays();
  renderCompare();
  renderDocumentPanel();
  renderPrivacyPanel();
  renderReviewPanel();
  $("toggle-compare").setAttribute("aria-pressed", String(state.compare));
  $("toggle-compare").textContent = state.compare ? "Show document pages" : "Compare original and prepared text";
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
$("toggle-compare").addEventListener("click", () => {
  state.compare = !state.compare;
  renderAll();
  selectPage(state.page, { scroll: true });
});

/* tabs */
const TABS = ["document", "privacy", "review"];
function selectTab(name, { focus = false } = {}) {
  state.tab = name;
  TABS.forEach((t) => {
    const tab = $(`tab-${t}`);
    const on = t === name;
    tab.setAttribute("aria-selected", String(on));
    tab.tabIndex = on ? 0 : -1;
    $(`panel-${t}`).hidden = !on;
    if (on && focus) tab.focus();
  });
}
TABS.forEach((t) => $(`tab-${t}`).addEventListener("click", () => {
  selectTab(t);
  showPane("inspector");
}));
$("workspace").querySelector(".viewtabs").addEventListener("keydown", (e) => {
  const i = TABS.indexOf(state.tab);
  const next = { ArrowRight: (i + 1) % 3, ArrowLeft: (i + 2) % 3, Home: 0, End: 2 }[e.key];
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
    const f = findingsOnPage(n, "rule").length;
    const m = findingsOnPage(n, "llm").length;
    const parts = [
      p && `${plural(p, "privacy concern")}`, f && `${plural(f, "format finding")}`, m && `${plural(m, "model finding")}`,
    ].filter(Boolean);
    return `<li><button type="button" data-page="${n}" aria-current="${n === state.page}"
        aria-label="Page ${n}${parts.length ? `: ${parts.join(", ")}` : ": no findings"}">
      <span class="pagelist__num">p. ${n}</span>
      <span class="pagelist__marks" aria-hidden="true">
        ${p ? `<b class="mk mk--privacy">P${p > 1 ? p : ""}</b>` : ""}
        ${f ? `<b class="mk mk--format">F${f > 1 ? f : ""}</b>` : ""}
        ${m ? `<b class="mk mk--model">M${m > 1 ? m : ""}</b>` : ""}
      </span></button></li>`;
  }).join("");

  const high = state.scored.participants.filter((p) => p.risk === "high");
  $("gate-chip").innerHTML = state.scored.gate_open
    ? `<span class="risk risk--ready">Ready for review</span>`
    : `<span class="risk risk--high">Blocked · ${plural(high.length, "high-risk participant")}</span>`;

  const unresolved = state.scored.participants.filter((p) => p.risk !== "low").length;
  $("count-privacy").textContent = unresolved ? `(${unresolved})` : "";
  $("count-review").textContent = state.review ? `(${state.review.findings.length})` : "";
}

$("page-list").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-page]");
  if (!b) return;
  selectPage(Number(b.dataset.page), { scroll: true });
  if (state.tab !== "document") selectTab("document");
  showPane("reader");
});

function selectPage(n, { scroll = false, highlight = null } = {}) {
  state.page = n;
  document.querySelectorAll("#page-list button").forEach((b) =>
    b.setAttribute("aria-current", String(Number(b.dataset.page) === n)));
  document.querySelectorAll(".sheet").forEach((s) => s.classList.toggle("is-current", Number(s.dataset.page) === n));
  renderDocumentPanel();
  document.querySelectorAll(".hl.is-active, .annot.is-active").forEach((el) => el.classList.remove("is-active"));
  if (highlight) document.querySelectorAll(`[data-key="${highlight}"]`).forEach((el) => el.classList.add("is-active"));
  if (scroll) {
    const target = state.compare ? $(`cmp-${n}`) : $(`sheet-${n}`);
    target?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  }
}

/* ---------- reader: PDF pages ---------- */
async function renderDocument() {
  const view = $("doc-view");
  view.innerHTML = "";
  $("reader-note").hidden = Boolean(state.pdfDoc);
  $("reader-note").textContent = state.pdfDoc ? "" :
    "Page images couldn't be drawn because PDF.js didn't load. Showing the text extracted on this machine instead.";

  for (const { page: n, text, layout } of state.parsed.pages) {
    const sheet = document.createElement("figure");
    sheet.className = "sheet";
    sheet.id = `sheet-${n}`;
    sheet.dataset.page = n;
    sheet.innerHTML = `<figcaption class="sheet__caption"><span>Page ${n} of ${state.parsed.pages.length}</span>
        <span>${layout.page_label ? `printed “${esc(layout.page_label)}”` : "no printed page number"}</span></figcaption>
      <div class="sheet__page"><div class="sheet__edge" hidden></div></div>`;
    view.appendChild(sheet);
    const pageEl = sheet.querySelector(".sheet__page");

    if (state.pdfDoc && n <= state.pdfDoc.numPages) {
      const page = await state.pdfDoc.getPage(n);
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
    } else {
      pageEl.insertAdjacentHTML("beforeend", `<div class="sheet__text">${esc(text)}</div>`);
      state.pageGeom[n] = { w: layout.width_in * 72, h: layout.height_in * 72 };
    }
  }
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
    const privacy = concernsOnPage(n).length > 0;
    const format = findingsOnPage(n).length > 0;
    edge.hidden = !(privacy || format);
    edge.className = `sheet__edge ${privacy ? "sheet__edge--privacy" : "sheet__edge--format"}`;
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
    selectTab("review");
    selectPage(n, { highlight: key });
    document.querySelector(`.annot[data-key="${key}"]`)?.scrollIntoView({ block: "nearest" });
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

/* ---------- inspector: document notes ---------- */
function renderDocumentPanel() {
  if (!state.parsed) return;
  const n = state.page;
  const page = state.parsed.pages.find((p) => p.page === n);
  const L = page.layout;
  const scored = scoredById();
  const concerns = concernsOnPage(n);
  const ids = state.scrubbed.direct_identifiers.filter((d) => d.page === n);
  const uniqueIds = [...new Map(ids.map((d) => [d.token, d])).values()];
  const findings = (state.review?.findings || []).map((f, i) => [f, i]).filter(([f]) => f.page === n);
  const font = L.fonts[0];

  $("panel-document").innerHTML = `
    <h2 class="panel__title">Page ${n} <span class="num" style="color:var(--text-2);font-weight:400">of ${state.parsed.pages.length}</span></h2>

    <section class="panel__section">
      <span class="label">Privacy on this page</span>
      ${concerns.length ? concerns.map((p) => {
        const s = scored[p.id];
        return `<button type="button" class="annot annot--privacy" data-participant="${esc(p.id)}">
          <span class="annot__meta"><span class="annot__src">${esc(participantName(p.id))}</span>
            <span class="risk risk--${s.risk}">${RISK_TEXT[s.risk]}</span><span>k ≈ ${s.k} (estimate)</span></span>
          <span class="annot__issue" style="display:block">Description may single this person out</span>
          <span class="annot__scope" style="display:block">Open in privacy check to see suggested rewrites</span></button>`;
      }).join("") : `<p class="panel__empty">No participant on this page is above the low-risk level.</p>`}
      ${uniqueIds.length ? `<p class="idsummary" style="margin-top:10px">Replaced locally: ${uniqueIds.map((d) =>
        `<span class="tok">${esc(d.token)}</span> ${esc(ID_LABEL[d.type] || "identifier")}`).join(", ")}</p>` : ""}
    </section>

    <section class="panel__section">
      <span class="label">Review findings</span>
      ${state.review ? (findings.length ? findings.map(([f, i]) => annotationHtml(f, i)).join("")
        : `<p class="panel__empty">No findings on this page.</p>`)
        : `<p class="panel__empty">Review hasn't run yet. It becomes available once the privacy gate passes.</p>`}
    </section>

    <section class="panel__section">
      <span class="label">Measured layout</span>
      <dl class="attrs">
        <dt>Margins</dt><dd class="num">top ${L.margins_in.top} · right ${L.margins_in.right} · bottom ${L.margins_in.bottom} · left ${L.margins_in.left} in</dd>
        <dt>Main font</dt><dd>${font ? `${esc(font.name)} ${font.size} pt` : "No text found"}</dd>
        <dt>Page number</dt><dd>${L.page_label ? `“${esc(L.page_label)}”, ${esc(L.page_label_position)}` : "None found"}</dd>
      </dl>
      <p class="panel__intro">Margins are measured to the outermost text on the page.</p>
    </section>`;
}

$("panel-document").addEventListener("click", (e) => {
  const p = e.target.closest("[data-participant]");
  if (p) return focusParticipant(p.dataset.participant);
  const a = e.target.closest(".annot[data-key]");
  if (a) openFinding(a.dataset.key);
});

/* ---------- inspector: privacy check ---------- */
function gateHtml() {
  const s = state.scored;
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
  const sendLabel = m?.configured ? "Send prepared text for review" : "Run local format checks";
  return `<div class="gate gate--ready">
    <p class="gate__title">Ready for review</p>
    ${medium.length ? `<p class="gate__body">${esc(joinNames(medium.map((p) => participantName(p.id))))}
      ${medium.length === 1 ? "is" : "are"} still in a narrow group (k between 5 and 19). You can continue, or apply the remaining suggestions first.</p>` : ""}
    <p class="gate__body">${m?.configured
      ? `Sending shares the prepared text with <strong>${esc(m.model)}</strong>${m.endpoint ? ` at ${esc(m.endpoint)}` : ""}. The original text and the token key stay on this machine.`
      : "No review model is configured, so only local format rules will run. Nothing will be sent."}</p>
    <div class="panel__actions"><button type="button" class="btn btn--primary" data-action="review">${state.review ? "Run review again" : sendLabel}</button>
      <button type="button" class="btn btn--quiet btn--small" data-action="compare">Check the prepared text</button></div>
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

  $("panel-privacy").innerHTML = `
    <h2 class="panel__title">Privacy check</h2>
    <p class="panel__intro">Each described participant is compared with a synthetic reference population.
      <strong>k</strong> is the estimated number of people who fit the same description: the smaller it is, the easier that person is to single out.</p>
    <details class="explain"><summary>How to read k</summary>
      <p>k of 1–4: high risk, blocks review. k of 5–19: medium, a narrow group. k of 20 or more: low.
      These are estimates from synthetic data, not counts of real students, and a low k is a reason to rewrite rather than proof of identification.</p></details>

    <section class="panel__section">
      <span class="label">Direct identifiers</span>
      <p class="idsummary">${ids.length ? `<strong>${idText}</strong> replaced with tokens on this machine. The token key never leaves it.`
        : "No names, emails, phone numbers or student IDs were found."}</p>
    </section>

    <section class="panel__section">
      <span class="label">Described participants</span>
      ${people.length ? people.map((p) => concernHtml(p, scored[p.id])).join("")
        : `<p class="panel__empty">No participant descriptions were recognised. Descriptions are found when they name a participant, for example “Participant 3, a 19-year-old sophomore…”.</p>`}
      ${anySuggestions ? `<div class="panel__actions"><button type="button" class="btn btn--secondary" data-action="apply-all">Apply all suggestions</button></div>` : ""}
    </section>
    ${gateHtml()}`;
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
  if (!fixes.length || state.busy) return;
  $("work-error").hidden = true;
  setBusy("Estimating risk");
  try {
    state.scored = await request("/score", { method: "POST", body: { doc_id: state.parsed.doc_id, accepted: fixes } });
    setBusy("Preparing comparison");
    state.view = await request(`/llm-view/${state.parsed.doc_id}`);
    setBusy("");
    renderAll();
    if (state.focus) $(`concern-${state.focus}`)?.scrollIntoView({ block: "nearest" });
  } catch (err) {
    setBusy("");
    showWorkError(err, () => applyFixes(fixes));
  }
}

$("inspector").addEventListener("click", (e) => {
  const t = e.target.closest("button");
  if (!t || t.disabled) return;
  if (t.dataset.apply) {
    const [participant_id, field] = t.dataset.apply.split("|");
    state.focus = participant_id;
    applyFixes([{ participant_id, field }]);
  } else if (t.dataset.action === "apply-all") {
    applyFixes(state.scored.participants.flatMap((p) => p.suggestions.map((g) => ({ participant_id: p.id, field: g.field }))));
  } else if (t.dataset.action === "review") {
    runReview();
  } else if (t.dataset.action === "compare") {
    state.compare = true;
    renderAll();
    showPane("reader");
    selectPage(state.page, { scroll: true });
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
  return `<button type="button" class="annot annot--${kind}" data-key="f-${i}">
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
  if (r.model_review === "not_implemented") return `A model (${esc(r.model)}) is configured, but model review isn't implemented in this build yet. Nothing was sent; only local rules ran.`;
  return "Model review didn't run because no model is configured, so nothing was sent. Only local format rules ran. Set LLM_BASE_URL and LLM_MODEL on the server to enable it.";
}

function renderReviewPanel() {
  const r = state.review;
  if (!r) {
    $("panel-review").innerHTML = `<h2 class="panel__title">Review</h2>
      <p class="panel__intro">Local format rules check margins, page numbers, fonts and required pages.
      A configured model reviews the prepared text against the rubric.</p>
      ${gateHtml()}
      <p class="panel__empty">No review has run for this document yet.</p>`;
    return;
  }
  const rules = r.findings.filter((f) => f.source === "rule").length;
  const model = r.findings.filter((f) => f.source === "llm").length;
  $("panel-review").innerHTML = `<h2 class="panel__title">Review</h2>
    <p class="review-summary">${plural(rules, "local rule finding")}${r.model_review === "sent" ? ` · ${plural(model, "model finding")}` : ""}</p>
    <div class="notice notice--info">${modelNote()}</div>
    <section class="panel__section">
      ${r.findings.length ? r.findings.map((f, i) => annotationHtml(f, i)).join("")
        : `<p class="panel__empty">No findings. The checks that ran found nothing to flag.</p>`}
    </section>
    ${gateHtml()}`;
}

function openFinding(key) {
  const i = Number(key.slice(2));
  const f = state.review.findings[i];
  if (state.compare) { state.compare = false; renderAll(); }
  selectPage(f.page, { scroll: true, highlight: key });
  showPane("reader");
}

$("panel-review").addEventListener("click", (e) => {
  const a = e.target.closest(".annot[data-key]");
  if (a) openFinding(a.dataset.key);
});

async function runReview() {
  if (state.busy) return;
  $("work-error").hidden = true;
  setBusy(state.model?.configured ? "Running local rules and model review" : "Running local format rules");
  try {
    state.review = await request("/review", { method: "POST", body: { doc_id: state.parsed.doc_id } });
    setBusy("");
    renderAll();
    selectTab("review");
  } catch (err) {
    setBusy("");
    if (err.status === 403) {
      state.scored = await request("/score", { method: "POST", body: { doc_id: state.parsed.doc_id, accepted: [] } }).catch(() => state.scored);
      renderAll();
    }
    showWorkError(err, () => runReview());
  }
}

/* ---------- start ---------- */
(async () => {
  try {
    state.model = (await request("/status")).model;
  } catch {
    state.model = null;
  }
  renderModelStatus();
})();
