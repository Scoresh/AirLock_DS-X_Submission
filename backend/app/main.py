"""StrangerThesis local API.  Owner: Dan.

Run from /backend:  uvicorn app.main:app --reload
Docs:               http://127.0.0.1:8000/docs
"""
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import format_rules, review, risk, rubric_check, scrub, settings, store
from .parse import ParseError, parse_pdf
from .schemas import (
    ParseResult,
    ReviewRequest,
    ReviewResult,
    RubricCheckRequest,
    RubricCheckResult,
    RubricParseResult,
    ScoreRequest,
    ScoreResult,
    ScrubResult,
    SettingsState,
    SettingsTestResult,
    SettingsUpdate,
)

app = FastAPI(title="StrangerThesis")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _state(doc_id: str, need: str) -> store.DocState:
    state = store.DOCS.get(doc_id)
    if state is None or getattr(state, need) is None:
        raise HTTPException(404, f"run the step that produces '{need}' for doc '{doc_id}' first")
    return state


@app.post("/parse", response_model=ParseResult)
async def parse(file: UploadFile = File(...)):
    doc_id = uuid.uuid4().hex[:8]
    state = store.get(doc_id)
    try:
        state.parsed = parse_pdf(await file.read(), doc_id)
    except ParseError as err:
        store.DOCS.pop(doc_id, None)
        raise HTTPException(400, str(err)) from err
    return state.parsed


@app.post("/scrub/{doc_id}", response_model=ScrubResult)
def run_scrub(doc_id: str):
    state = _state(doc_id, "parsed")
    try:
        state.scrubbed = scrub.scrub(state.parsed)
    except (scrub.SetupError, FileNotFoundError) as err:
        raise HTTPException(503, str(err)) from err  # never return a scrub that skipped detection
    return state.scrubbed


@app.post("/score", response_model=ScoreResult)
def run_score(req: ScoreRequest):
    state = _state(req.doc_id, "scrubbed")
    state.accepted += [fix for fix in req.accepted if fix not in state.accepted]
    state.scored = risk.score(state.scrubbed, state.accepted)
    return state.scored


@app.post("/review", response_model=ReviewResult)
def run_review(req: ReviewRequest):
    state = _state(req.doc_id, "scored")
    if not state.scored.gate_open:
        raise HTTPException(403, "privacy gate is closed: accept fixes for high-risk participants first")
    findings = format_rules.run_all(state.parsed)
    if req.format_only:
        # Local rules only; nothing crosses the network.
        return ReviewResult(doc_id=req.doc_id, findings=findings, model_review="not_configured",
                            model=review.model_config()["model"])
    sent = risk.rewrite(state.scrubbed, state.accepted)  # only this text crosses the network
    model_findings, status = review.llm_review(sent, req.rubric_text)
    findings += review.restore(model_findings, req.doc_id)
    return ReviewResult(doc_id=req.doc_id, findings=findings, model_review=status,
                        model=review.model_config()["model"])


@app.post("/rubric-parse", response_model=RubricParseResult)
async def run_rubric_parse(file: UploadFile = File(...)):
    """Parse an uploaded rubric file (docx/pdf/txt/md) into structured criteria.

    Runs the local `rubric_parsing` pipeline (extract text -> LLM -> validated JSON)
    and returns the same shape the /rubric-check endpoint expects, so the frontend
    can pipe it straight in. This handles only the user-supplied rubric, never the
    participant document, so it stays off the privacy-gate path.
    """
    data = await file.read()
    try:
        criteria = rubric_check.parse_upload(data, file.filename or "rubric.txt")
    except rubric_check.ParseFormatError as err:
        raise HTTPException(400, str(err)) from err
    except rubric_check.ParseConfigError as err:
        raise HTTPException(503, f"no model configured to parse the rubric: {err}") from err
    except (rubric_check.ParseRequestError, ValueError) as err:
        raise HTTPException(502, str(err)) from err
    return RubricParseResult(rubric=criteria)


@app.post("/rubric-check/{doc_id}", response_model=RubricCheckResult)
def run_rubric_check(doc_id: str, req: RubricCheckRequest):
    """Compare the prepared document against a parsed rubric, one row per criterion.

    Uses the same privacy gate as /review: only gate-approved, tokenized text is sent.
    """
    state = _state(doc_id, "scored")
    if not state.scored.gate_open:
        raise HTTPException(403, "privacy gate is closed: accept fixes for high-risk participants first")
    if not req.rubric:
        raise HTTPException(400, "rubric is empty: load a rubric JSON with at least one criterion")
    sent = risk.rewrite(state.scrubbed, state.accepted)  # only this text crosses the network
    results, status = rubric_check.check(sent, req.rubric)
    return RubricCheckResult(doc_id=doc_id, results=results, model_review=status,
                             model=rubric_check.model_config()["model"])


@app.get("/status")
def status():
    """Which review model is configured, and whether local detection is fully installed."""
    return {"model": review.model_config(), "setup": scrub.setup_status()}


# ---------- settings: configure the review/rubric LLM at runtime ----------

@app.get("/settings/providers")
def settings_providers():
    """Presets for ChatGPT, Gemini, Claude and a custom/local endpoint (no secrets)."""
    return {"providers": settings.providers_public()}


@app.get("/settings", response_model=SettingsState)
def settings_get():
    """Current LLM settings. The API key is never returned, only whether one is set."""
    return settings.current()


@app.put("/settings", response_model=SettingsState)
def settings_put(req: SettingsUpdate):
    """Apply an LLM provider + model (+ optional key) for review and rubric checks."""
    try:
        return settings.apply(req.provider, req.model or "", req.api_key, req.base_url)
    except ValueError as err:
        raise HTTPException(400, str(err)) from err


@app.delete("/settings", response_model=SettingsState)
def settings_delete():
    """Clear the configured model so nothing can be sent."""
    return settings.clear()


@app.post("/settings/test", response_model=SettingsTestResult)
def settings_test():
    """Send a tiny prompt to the configured endpoint to confirm it answers.

    No document or rubric content is involved; this only checks connectivity and
    credentials for the model the user just configured.
    """
    import sys as _sys
    from pathlib import Path as _Path

    repo_root = _Path(__file__).resolve().parents[2]
    if str(repo_root) not in _sys.path:
        _sys.path.insert(0, str(repo_root))
    from rubric_parsing.llm import LLMConfig, LLMConfigError, LLMRequestError, chat_json

    try:
        cfg = LLMConfig.from_env()
    except LLMConfigError as err:
        raise HTTPException(400, f"not configured: {err}") from err
    try:
        reply = chat_json(cfg, "You reply with JSON only.", 'Reply with {"ok": true} and nothing else.')
        return SettingsTestResult(ok=True, detail=f"{cfg.model} responded.")
    except LLMRequestError as err:
        return SettingsTestResult(ok=False, detail=str(err))


SAMPLE_PDF = Path(__file__).resolve().parents[2] / "samples" / "test-thesis.pdf"


@app.get("/sample", response_class=FileResponse)
def sample():
    """The test thesis, so the UI can offer an explicit "Open sample document" action."""
    return FileResponse(SAMPLE_PDF, media_type="application/pdf", filename="test-thesis.pdf")


@app.get("/llm-view/{doc_id}")
def llm_view(doc_id: str):
    """Original vs. exactly what the LLM receives, for the side-by-side view."""
    state = _state(doc_id, "scrubbed")
    sent = risk.rewrite(state.scrubbed, state.accepted)
    return {
        "doc_id": doc_id,
        "pages": [
            {"page": o.page, "original": o.text, "sent_to_llm": s.text}
            for o, s in zip(state.parsed.pages, sent.scrubbed_pages)
        ],
    }


FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
