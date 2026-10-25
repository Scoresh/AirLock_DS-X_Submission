"""Rubric review via the user's configured LLM, plus local token restore.  Owner: Dan.

Only ScrubResult text may be sent to the LLM. Never pass ParseResult text here.
main.py calls llm_review only after the privacy gate is open.

llm_review reports what actually happened, so the UI never claims text was sent:
    "not_configured"   LLM_BASE_URL / LLM_MODEL are not set; nothing was sent
    "sent"             the prepared text was sent and the model's findings are returned
    "failed"           a request was attempted but the model could not be reached or answered badly

The endpoint speaks the OpenAI-compatible chat API (a lab-approved hosted model, TerrierGPT,
or a local Ollama server), like rubric_parsing/llm.py. The model is a setting, never hard-coded.
"""
import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from .schemas import Finding, ModelReviewStatus, ScrubResult

TIMEOUT_S = 90
TOKEN = re.compile(r"\[([A-Z_]+_\d+)\]")

DEFAULT_RUBRIC = """Boston University thesis and dissertation guide (summary used when no rubric is uploaded):
- Front matter in order: title page, copyright page (optional), abstract, table of contents.
- An abstract that states the question, method and main findings.
- Chapters with numbered headings and a consistent heading style.
- Every in-text citation has a matching reference, in one consistent citation style.
- Participants are described in aggregate where possible, without details that could identify them."""

SYSTEM_PROMPT = """You review a student's thesis draft against a rubric and report problems.
The text was de-identified before it reached you: tokens such as [PERSON_01], [EMAIL_01] or
[PARTICIPANT_03] replace private details. Keep tokens exactly as written and never guess what
they stand for. Do not report layout issues (margins, fonts, page numbers); those are checked elsewhere.
Answer with JSON only: {"findings": [{"page": <int>, "quote": <short exact quote or null>,
"criterion": <the rubric line you applied, quoted>, "issue": <one sentence>,
"severity": "error" | "warning"}]}. Return {"findings": []} if nothing is wrong."""


def model_config() -> dict:
    """Which model the review would use. Never includes the API key."""
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    return {
        "configured": bool(base_url and model),
        "model": model or None,
        "endpoint": urlparse(base_url).netloc or None,
    }


def build_payload(scrubbed: ScrubResult, rubric_text: str | None, model: str) -> dict:
    """The exact request body sent to the model: scrubbed, gate-approved text only."""
    pages = "\n\n".join(f"--- Page {p.page} ---\n{p.text}" for p in scrubbed.scrubbed_pages)
    user = f"RUBRIC:\n{rubric_text or DEFAULT_RUBRIC}\n\nDOCUMENT:\n{pages}"
    return {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
    }


def _send(base_url: str, api_key: str, payload: dict) -> str:
    """POST one chat request and return the assistant's text. The only network call in the app.

    Routes Anthropic Claude through its native Messages API (/v1/messages) and
    everything else through the OpenAI-compatible /chat/completions endpoint, so
    /review works for the same providers the Settings page offers (and matches
    rubric_parsing/llm.py). The OpenAI-shaped `payload` is translated for Anthropic.
    """
    style = os.getenv("LLM_API_STYLE", "").strip().lower()
    if style not in ("openai", "anthropic"):
        style = "anthropic" if "api.anthropic.com" in base_url else "openai"

    if style == "anthropic":
        system = next((m["content"] for m in payload["messages"] if m["role"] == "system"), "")
        user = next((m["content"] for m in payload["messages"] if m["role"] == "user"), "")
        body = {"model": payload["model"], "max_tokens": 4096, "system": system,
                "messages": [{"role": "user", "content": user}]}
        headers = {"Content-Type": "application/json", "anthropic-version": "2026-10-21"}
        if api_key:
            headers["x-api-key"] = api_key
        req = urllib.request.Request(f"{base_url.rstrip('/')}/messages",
                                     data=json.dumps(body).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            blocks = json.loads(resp.read())["content"]
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(f"{base_url.rstrip('/')}/chat/completions",
                                 data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]


def _parse(content: str, pages: set[int]) -> list[Finding]:
    data = json.loads(content[content.find("{"):content.rfind("}") + 1])
    findings = []
    for item in data.get("findings", []):
        try:
            page = int(item.get("page") or 0)
            findings.append(Finding(
                page=page if page in pages else min(pages),
                quote=item.get("quote") or None,
                criterion=str(item.get("criterion") or "Rubric"),
                issue=str(item["issue"]),
                severity="error" if item.get("severity") == "error" else "warning",
                source="llm",
            ))
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed items rather than fail the whole review
    return findings


def llm_review(scrubbed: ScrubResult, rubric_text: str | None) -> tuple[list[Finding], ModelReviewStatus, str | None]:
    """Returns (findings, status, error message)."""
    config = model_config()
    if not config["configured"]:
        return [], "not_configured", None
    payload = build_payload(scrubbed, rubric_text, config["model"])
    try:
        content = _send(os.environ["LLM_BASE_URL"], os.getenv("LLM_API_KEY", ""), payload)
        return _parse(content, {p.page for p in scrubbed.scrubbed_pages}), "sent", None
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError, TypeError) as err:
        return [], "failed", f"{type(err).__name__}: {err}"[:300]


def restore(findings: list[Finding], doc_id: str) -> list[Finding]:
    """Swap tokens in model feedback back to the original words, on this machine only."""
    from .scrub import load_key  # local import: scrub imports risk, which is heavy

    key = load_key(doc_id)
    if not key:
        return findings

    def put_back(text: str | None) -> str | None:
        return TOKEN.sub(lambda m: key.get(m.group(0), m.group(0)), text) if text else text

    return [f.model_copy(update={"quote": put_back(f.quote), "issue": put_back(f.issue),
                                 "criterion": put_back(f.criterion)}) for f in findings]
