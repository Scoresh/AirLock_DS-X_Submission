"""Rubric review via the user's configured LLM, plus local token restore.  Owner: Dan.

Only ScrubResult text may be sent to the LLM. Never pass ParseResult text here.

TODO:
  - LLM endpoint from env: LLM_BASE_URL, LLM_MODEL, LLM_API_KEY (OpenAI-compatible, so Ollama works)
  - prompt asks for JSON findings with page numbers and the quoted rubric criterion
  - restore(): swap tokens back using keys/<doc_id>.json; accept "[PARTICIPANT_03]" and "Participant 03"
"""
from .mock import load
from .schemas import Finding, ScrubResult


def llm_review(scrubbed: ScrubResult, rubric_text: str | None) -> list[Finding]:
    findings = [Finding.model_validate(f) for f in load("review")["findings"]]
    return [f for f in findings if f.source == "llm"]


def restore(findings: list[Finding], doc_id: str) -> list[Finding]:
    return findings
