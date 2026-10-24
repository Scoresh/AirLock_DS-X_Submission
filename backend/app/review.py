"""Rubric review via the user's configured LLM, plus local token restore.  Owner: Dan.

Only ScrubResult text may be sent to the LLM. Never pass ParseResult text here.

llm_review reports what actually happened, so the UI never claims text was sent:
    "not_configured"   LLM_BASE_URL / LLM_MODEL are not set; nothing was sent
    "not_implemented"  a model is configured but the call below is still a TODO; nothing was sent
    "sent"             the prepared text was sent and the model's findings are returned

TODO:
  - call the model (OpenAI-compatible, see rubric_parsing/llm.py) and return "sent"
  - prompt asks for JSON findings with page numbers and the quoted rubric criterion
  - restore(): swap tokens back using keys/<doc_id>.json; accept "[PARTICIPANT_03]" and "Participant 03"
"""
import os
from urllib.parse import urlparse

from .schemas import Finding, ModelReviewStatus, ScrubResult


def model_config() -> dict:
    """Which model the review would use. Never includes the API key."""
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    return {
        "configured": bool(base_url and model),
        "model": model or None,
        "endpoint": urlparse(base_url).netloc or None,
    }


def llm_review(scrubbed: ScrubResult, rubric_text: str | None) -> tuple[list[Finding], ModelReviewStatus]:
    if not model_config()["configured"]:
        return [], "not_configured"
    return [], "not_implemented"


def restore(findings: list[Finding], doc_id: str) -> list[Finding]:
    return findings
