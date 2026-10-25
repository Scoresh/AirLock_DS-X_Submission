"""StrangerThesis local API.  Owner: Dan.

Run from /backend:  uvicorn app.main:app --reload
Docs:               http://127.0.0.1:8000/docs
"""
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import csv_mode, format_rules, review, risk, scrub, store
from .parse import ParseError, parse_pdf
from .schemas import ParseResult, ReviewRequest, ReviewResult, ScoreRequest, ScoreResult, ScrubResult

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
    sent = risk.rewrite(state.scrubbed, state.accepted)  # only this text crosses the network
    model_findings, status, error = review.llm_review(sent, req.rubric_text)
    findings += review.restore(model_findings, req.doc_id)
    return ReviewResult(doc_id=req.doc_id, findings=findings, model_review=status,
                        model=review.model_config()["model"], model_error=error)


@app.get("/status")
def status():
    """Which review model is configured, and whether local detection is fully installed."""
    return {"model": review.model_config(), "setup": scrub.setup_status()}


CSV_TABLES: dict[str, bytes] = {}  # scrubbed CSVs kept in memory for download


@app.post("/csv/scrub")
async def csv_scrub(file: UploadFile = File(...)):
    """Scrub an uploaded data table locally; returns column roles and the k distribution before and after."""
    table_id = uuid.uuid4().hex[:8]
    try:
        scrubbed, report = csv_mode.scrub_table(await file.read(), table_id)
    except (ValueError, UnicodeDecodeError) as err:
        raise HTTPException(400, f"could not read this CSV: {err}") from err
    CSV_TABLES[table_id] = scrubbed.to_csv(index=False).encode()
    return report | {"download": f"/csv/{table_id}/download"}


@app.get("/csv/{table_id}/download")
def csv_download(table_id: str):
    if table_id not in CSV_TABLES:
        raise HTTPException(404, "this scrubbed table is no longer on the local server")
    return Response(CSV_TABLES[table_id], media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="scrubbed-{table_id}.csv"'})


SAMPLE_PDF = Path(__file__).resolve().parents[2] / "samples" / "demo-thesis.pdf"  # see scripts/make_demo_thesis.py


@app.get("/sample", response_class=FileResponse)
def sample():
    """The test thesis, so the UI can offer an explicit "Open sample document" action."""
    return FileResponse(SAMPLE_PDF, media_type="application/pdf", filename="demo-thesis.pdf")


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
