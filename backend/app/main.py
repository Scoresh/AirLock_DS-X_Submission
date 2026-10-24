"""Stranger Mode local API.  Owner: Dan.

Run from /backend:  uvicorn app.main:app --reload
Docs:               http://127.0.0.1:8000/docs
"""
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import format_rules, review, risk, scrub, store
from .parse import parse_pdf
from .schemas import ParseResult, ReviewRequest, ReviewResult, ScoreRequest, ScoreResult, ScrubResult

app = FastAPI(title="Stranger Mode")
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
    state.parsed = parse_pdf(await file.read(), doc_id)
    return state.parsed


@app.post("/scrub/{doc_id}", response_model=ScrubResult)
def run_scrub(doc_id: str):
    state = _state(doc_id, "parsed")
    state.scrubbed = scrub.scrub(state.parsed)
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
    findings += review.restore(review.llm_review(sent, req.rubric_text), req.doc_id)
    return ReviewResult(doc_id=req.doc_id, findings=findings)


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
