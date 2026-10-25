"""Orchestrator: rubric file -> text -> LLM -> validated JSON.

Because no two rubrics share a layout, an LLM does the structural extraction.
This module only sends the rubric text (grading criteria the user supplies);
it never handles participant document content, so it stays clear of the
privacy-gate path.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import extract
from .llm import LLMConfig, LLMRequestError, chat_json
from .schemas import Rubric

_SYSTEM_PROMPT = (
    "You convert grading rubrics into structured JSON. "
    "You are given the full text of one rubric and must extract every grading "
    "criterion. Respond with a single JSON object and nothing else."
)

_USER_TEMPLATE = """\
Extract the rubric below into this exact JSON shape:

{{"rubric": [{{"parameter_title": TITLE, "description": DESCRIPTION, "points": POINTS}}, ...]}}

Rules:
- One array entry per distinct grading criterion / parameter.
- A **maximum** of three sentences per grading criterion / parameter.
- "parameter_title": the short name of the criterion (string).
- "description": what the criterion asks for; combine sub-bullets into one string.
- "points": the numeric weight for that criterion. OMIT this key entirely if the
  rubric does not state points for it. Never invent point values.
- Preserve the rubric's original order.
- Output ONLY the JSON object. No markdown fences, no commentary.

RUBRIC TEXT:
---
{rubric_text}
---
"""


def _extract_json(text: str) -> str:
    """Pull the JSON object out of an LLM response.

    Handles plain JSON, ```json ... ``` fences, and stray leading/trailing prose
    by falling back to the first balanced {...} block.
    """
    s = text.strip()

    # drop a leading fence line like ```json (or ``` )
    if s.startswith("```"):
        first_nl = s.find("\n")
        s = s[first_nl + 1 :] if first_nl != -1 else s.lstrip("`")
        fence = s.rfind("```")
        if fence != -1:
            s = s[:fence]
        s = s.strip()

    if s.startswith("{"):
        return s

    # fallback: first balanced brace block
    start = s.find("{")
    if start == -1:
        return s
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return s[start:]


def parse_rubric_text(rubric_text: str, config: LLMConfig | None = None) -> Rubric:
    """Parse already-extracted rubric text into a validated Rubric."""
    if not rubric_text.strip():
        raise ValueError("rubric text is empty")
    cfg = config or LLMConfig.from_env()

    raw = chat_json(
        cfg,
        _SYSTEM_PROMPT,
        _USER_TEMPLATE.format(rubric_text=rubric_text),
    )
    cleaned = _extract_json(raw)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMRequestError(
            f"LLM did not return valid JSON: {exc}\n---\n{raw}"
        ) from exc

    return Rubric.from_dict(payload)


def parse_rubric_file(path: str | Path, config: LLMConfig | None = None) -> Rubric:
    """Full pipeline: extract text from a rubric file, then parse via LLM."""
    text = extract.to_text(path)
    return parse_rubric_text(text, config=config)
