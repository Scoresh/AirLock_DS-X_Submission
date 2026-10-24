/* ThesisGuard frontend logic.
   Same API contract as the original skeleton:
     POST /parse            (multipart: file)        -> { doc_id, pages[] }
     POST /scrub/{doc_id}                            -> { scrubbed_pages[], direct_identifiers[], participants[] }
     POST /score            { doc_id, accepted[] }   -> { participants[], gate_open }
     POST /review           { doc_id }               -> { findings[] }
     GET  /llm-view/{doc_id}                         -> { pages[] }
   Response field names are read exactly as the backend emits them
   (note the Suggestion `from` key is read as s.from). */

const $ = (id) => document.getElementById(id);

function api(path, body) {
  return fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (r) => {
    if (!r.ok) {
      let detail;
      try { detail = (await r.json()).detail; } catch { detail = r.statusText; }
      throw new Error(detail || `Request to ${path} failed (${r.status})`);
    }
    return r.json();
  });
}

const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ---------- small UI helpers ---------- */
function setLoading(btn, on) {
  if (!btn) return;
  btn.classList.toggle("is-loading", on);
  btn.disabled = on;
}

function showError(message) {
  const box = $("error");
  box.textContent = message || "Something went wrong.";
  box.hidden = false;
  box.scrollIntoView({ behavior: "smooth", block: "center" });
}
function clearError() { $("error").hidden = true; }

function reveal(id) {
  const el = $(id);
  if (el && el.hidden) el.hidden = false;
}

function setStep(active) {
  document.querySelectorAll(".step").forEach((li) => {
    const n = Number(li.dataset.step);
    li.classList.toggle("is-active", n === active);
    li.classList.toggle("is-done", n < active);
  });
}

/* ---------- state ---------- */
let docId, scrubbed, scored;

/* ---------- step 1: upload -> parse -> scrub -> score -> llm view ---------- */
$("pdf").addEventListener("change", () => {
  const f = $("pdf").files[0];
  $("filename").innerHTML = f
    ? `Selected: <strong>${esc(f.name)}</strong>`
    : "";
});

$("go").onclick = async () => {
  clearError();
  setLoading($("go"), true);
  try {
    const form = new FormData();
    form.append(
      "file",
      $("pdf").files[0] || new Blob(["%PDF-mock"], { type: "application/pdf" }),
      "doc.pdf"
    );
    const parsed = await fetch("/parse", { method: "POST", body: form }).then(async (r) => {
      if (!r.ok) throw new Error(`Parsing failed (${r.status})`);
      return r.json();
    });
    docId = parsed.doc_id;
    scrubbed = await api(`/scrub/${docId}`);
    await rescore([]);
    await showLlmView();
    reveal("heat");
    $("gate").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading($("go"), false);
  }
};

/* ---------- step 2: privacy gate ---------- */
async function rescore(accepted) {
  scored = await api("/score", { doc_id: docId, accepted });
  reveal("gate");
  setStep(scored.gate_open ? 3 : 2);

  const status = $("gate-status");
  if (scored.gate_open) {
    status.className = "gate-status gate-status--open";
    status.textContent = "Gate open — scrubbed text is safe to send for review.";
  } else {
    status.className = "gate-status gate-status--closed";
    status.textContent = "Gate closed — accept suggestions for high-risk participants to continue.";
  }

  $("people").innerHTML = scored.participants.map((p) => {
    const attrs = Object.entries(p.attributes)
      .map(([k, v]) => `<span class="chip"><b>${esc(k)}</b> ${esc(v)}</span>`)
      .join("");
    const suggestions = p.suggestions.length
      ? `<ul class="person__suggestions">${p.suggestions.map((s) =>
          `<li class="suggestion">Change <b>${esc(s.from)}</b> to <b>${esc(s.to)}</b>
           <span class="suggestion__k">(k ≈ ${esc(s.new_k)})</span></li>`).join("")}</ul>`
      : "";
    return `
      <div class="person person--${esc(p.risk)}">
        <div class="person__head">
          <span class="person__id">${esc(p.id)}</span>
          <span class="badge badge--${esc(p.risk)}">${esc(p.risk)} risk · k ≈ ${esc(p.k)}</span>
        </div>
        <div class="person__attrs">${attrs}</div>
        ${suggestions}
      </div>`;
  }).join("");

  $("send").disabled = !scored.gate_open;
}

$("accept").onclick = async () => {
  clearError();
  setLoading($("accept"), true);
  try {
    const accepted = scored.participants.flatMap((p) =>
      p.suggestions.map((s) => ({ participant_id: p.id, field: s.field })));
    await rescore(accepted);
    await showLlmView();  // accepted fixes rewrite the text the LLM will get
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading($("accept"), false);
  }
};

/* ---------- step 3: review + heatmap ---------- */
$("send").onclick = async () => {
  clearError();
  setLoading($("send"), true);
  try {
    const review = await api("/review", { doc_id: docId });
    const riskPages = new Set(
      scrubbed.participants.flatMap((p) => p.pages)
        .concat(scrubbed.direct_identifiers.map((d) => d.page))
    );
    const byPage = {};
    for (const f of review.findings) (byPage[f.page] ||= []).push(f);

    const pages = [...new Set([...riskPages, ...Object.keys(byPage).map(Number)])]
      .sort((a, b) => a - b);

    reveal("heat");
    setStep(4);

    $("tiles").innerHTML = pages.map((n) => {
      const cls = riskPages.has(n) && byPage[n] ? "both" : riskPages.has(n) ? "risk" : "rubric";
      return `<button type="button" class="tile ${cls}" data-page="${n}">p. ${esc(n)}</button>`;
    }).join("");

    $("tiles").onclick = (e) => {
      const tile = e.target.closest(".tile");
      if (!tile) return;
      document.querySelectorAll(".tile").forEach((t) => t.classList.remove("is-selected"));
      tile.classList.add("is-selected");
      const n = Number(tile.dataset.page);
      const findings = byPage[n] || [];
      $("detail").innerHTML = `<h3>Page ${esc(n)}</h3>` + (
        findings.length
          ? findings.map((f) => `
              <div class="finding">
                <div>
                  <span class="finding__src finding__src--${esc(f.source)}">${esc(f.source)}</span>
                  <span class="finding__issue">${esc(f.issue)}</span>
                </div>
                <div class="finding__rule">Rule: ${esc(f.criterion)}</div>
              </div>`).join("")
          : `<p class="detail__empty">No rubric findings on this page — flagged for privacy risk only.</p>`
      );
    };

    $("heat").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading($("send"), false);
  }
};

/* ---------- step 4: what the LLM saw ---------- */
async function showLlmView() {
  const view = await fetch(`/llm-view/${docId}`).then(async (r) => {
    if (!r.ok) throw new Error(`Could not load LLM view (${r.status})`);
    return r.json();
  });
  reveal("llmview");
  $("pages").innerHTML = view.pages.map((p) => `
    <div class="page-block">
      <h4>Page ${esc(p.page)}</h4>
      <div class="side">
        <div class="side__col">
          <span class="side__label">Original · stays local</span>
          <pre>${esc(p.original)}</pre>
        </div>
        <div class="side__col side__col--sent">
          <span class="side__label side__label--sent">Sent to the LLM</span>
          <pre>${esc(p.sent_to_llm)}</pre>
        </div>
      </div>
    </div>`).join("");
}
