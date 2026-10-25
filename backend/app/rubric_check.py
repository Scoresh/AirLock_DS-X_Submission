"""Compare the prepared (gate-approved) document text against a parsed rubric.

The rubric is produced locally by the `rubric_parsing` package. This module takes
that rubric plus the prepared ScrubResult text and asks the user's configured LLM,
for each criterion, whether the document fulfils it and why.

Privacy: like review.py, only ScrubResult text crosses the network. Never pass
ParseResult (original) text here. The call runs only when the privacy gate is open
(enforced by the /rubric-check route in main.py) and a model is configured.

Reuses rubric_parsing.llm (OpenAI-compatible, configured via LLM_BASE_URL /
LLM_MODEL / LLM_API_KEY) so there is a single LLM client convention in the repo.
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from .schemas import (
    ModelReviewStatus,
    RubricCriterionIn,
    RubricCriterionResult,
    ScrubResult,
)

# Make the repo-root `rubric_parsing` package importable from the backend.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from rubric_parsing.llm import (  # noqa: E402
    LLMConfig,
    LLMConfigError,
    LLMRequestError,
    chat_json,
)
from rubric_parsing.extract import ExtractError  # noqa: E402
from rubric_parsing.parser import parse_rubric_file  # noqa: E402

_SYSTEM_PROMPT = (
    "You grade a document against a rubric. You are given the full prepared text "
    "of one document (identifying details already replaced with tokens) and a list "
    "of rubric criteria. For EACH criterion, decide whether the document fulfils it "
    "and write a short, specific comment citing what in the document supports your "
    "decision. Judge only from the provided text; never invent content. "
    "Respond with a single JSON object and nothing else."
)

_USER_TEMPLATE = """\
Compare the DOCUMENT against each rubric criterion and return this exact JSON shape:

{{"results": [{{"parameter_title": TITLE, "fulfilled": true|false, "comment": TEXT}}, ...]}}

Rules:
- One array entry per criterion, in the same order, using the criterion's exact
  "parameter_title" so entries can be matched back.
- "fulfilled": true if the document clearly meets the criterion, false otherwise.
- "comment": one to three sentences explaining the decision, referencing concrete
  evidence from the document. Be concise.
- Output ONLY the JSON object. No markdown fences, no commentary.

RUBRIC CRITERIA:
{criteria_block}

DOCUMENT (prepared text, tokenized):
---
{document_text}
---
"""


def model_config() -> dict:
    """Which model this would use. Defined via review.py's convention."""
    from . import review

    return review.model_config()


def _criteria_block(rubric: list[RubricCriterionIn]) -> str:
    lines = []
    for i, c in enumerate(rubric, start=1):
        pts = f" (points: {c.points})" if c.points is not None else ""
        lines.append(f"{i}. {c.parameter_title}{pts}: {c.description}")
    return "\n".join(lines)


def _document_text(scrubbed: ScrubResult) -> str:
    return "\n\n".join(p.text for p in scrubbed.scrubbed_pages)


# Words that mean a criterion is about visual content the text pipeline never sees.
# The prepared text has no image content (no OCR), so any criterion resting on an
# image/figure/diagram cannot be judged from text alone -> "not enough information".
_IMAGE_WORDS = (
    "image",
    "figure",
    "diagram",
    "chart",
    "graph",
    "photo",
    "photograph",
    "picture",
    "illustration",
    "screenshot",
    "visual",
    "plot",
    "infographic",
)
_IMAGE_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in _IMAGE_WORDS) + r")s?\b",
    re.IGNORECASE,
)


def _references_image(criterion: RubricCriterionIn) -> bool:
    """True if the criterion's text asks about an image/figure/visual.

    These cannot be judged from the prepared text (which carries no image content),
    so they are flagged as "not enough information" rather than sent to the model.
    """
    text = f"{criterion.parameter_title} {criterion.description}"
    return bool(_IMAGE_RE.search(text))


_NEEDS_IMAGE_NOTE = (
    "This criterion refers to an image or figure. The prepared text does not "
    "include image content, so there is not enough information to judge it from "
    "the text alone."
)


def _unjudged(rubric: list[RubricCriterionIn], status: ModelReviewStatus) -> list[RubricCriterionResult]:
    """Return the rubric as a table with no decisions yet (model not run).

    Image-referencing criteria are still flagged as "not enough information", since
    that verdict comes from the document (no image content), not from the model.
    """
    note = {
        "not_configured": "No review model is configured, so nothing was sent.",
        "not_implemented": "Model review is not implemented yet, so nothing was sent.",
    }.get(status, "")
    rows: list[RubricCriterionResult] = []
    for c in rubric:
        needs_image = _references_image(c)
        rows.append(
            RubricCriterionResult(
                parameter_title=c.parameter_title,
                description=c.description,
                points=c.points,
                fulfilled=None,
                comment=_NEEDS_IMAGE_NOTE if needs_image else note,
                needs_more_info=needs_image,
            )
        )
    return rows


def check(
    scrubbed: ScrubResult,
    rubric: list[RubricCriterionIn],
) -> tuple[list[RubricCriterionResult], ModelReviewStatus]:
    """Fill the rubric table by asking the model about the prepared document text.

    Criteria that reference an image/figure are not sent to the model: the prepared
    text has no image content, so they are flagged "not enough information" locally.
    """
    if not model_config()["configured"]:
        return _unjudged(rubric, "not_configured"), "not_configured"

    try:
        cfg = LLMConfig.from_env()
    except LLMConfigError:
        return _unjudged(rubric, "not_configured"), "not_configured"

    # Split image-referencing criteria out; only the rest go to the model.
    judgeable = [c for c in rubric if not _references_image(c)]

    by_title: dict = {}
    if judgeable:
        raw = chat_json(
            cfg,
            _SYSTEM_PROMPT,
            _USER_TEMPLATE.format(
                criteria_block=_criteria_block(judgeable),
                document_text=_document_text(scrubbed),
            ),
        )
        payload = _parse_results(raw)
        # Index the model's answers by title so order/missing entries are tolerated.
        for row in payload:
            if isinstance(row, dict) and isinstance(row.get("parameter_title"), str):
                by_title[row["parameter_title"].strip().lower()] = row

    results: list[RubricCriterionResult] = []
    for c in rubric:
        if _references_image(c):
            results.append(
                RubricCriterionResult(
                    parameter_title=c.parameter_title,
                    description=c.description,
                    points=c.points,
                    fulfilled=None,
                    comment=_NEEDS_IMAGE_NOTE,
                    needs_more_info=True,
                )
            )
            continue
        row = by_title.get(c.parameter_title.strip().lower(), {})
        fulfilled = row.get("fulfilled")
        if not isinstance(fulfilled, bool):
            fulfilled = None
        comment = row.get("comment")
        results.append(
            RubricCriterionResult(
                parameter_title=c.parameter_title,
                description=c.description,
                points=c.points,
                fulfilled=fulfilled,
                comment=str(comment).strip() if comment is not None else "",
            )
        )
    return results, "sent"


def _parse_results(raw: str) -> list:
    """Pull the results array out of the LLM response, tolerating fences/prose."""
    cleaned = _extract_json(raw)
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMRequestError(
            f"model did not return valid JSON: {exc}\n---\n{raw}"
        ) from exc
    if isinstance(obj, dict):
        rows = obj.get("results", [])
    elif isinstance(obj, list):
        rows = obj
    else:
        rows = []
    return rows if isinstance(rows, list) else []


def _extract_json(text: str) -> str:
    """Pull the JSON object/array out of an LLM response (fences or stray prose)."""
    s = text.strip()
    if s.startswith("```"):
        first_nl = s.find("\n")
        s = s[first_nl + 1 :] if first_nl != -1 else s.lstrip("`")
        fence = s.rfind("```")
        if fence != -1:
            s = s[:fence]
        s = s.strip()
    if s.startswith("{") or s.startswith("["):
        return s
    # fallback: first balanced {...} block
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



# ---------- parse an uploaded rubric file, then feed the rubric-check logic ----------

# Error types a caller (the route) should translate into HTTP responses.
ParseConfigError = LLMConfigError
ParseFormatError = ExtractError
ParseRequestError = LLMRequestError


def parse_upload(data: bytes, filename: str) -> list[RubricCriterionIn]:
    """Parse an uploaded rubric file into criteria, ready to pipe into check().

    Writes the bytes to a temp file (so rubric_parsing.extract routes by
    extension: PDF via PyMuPDF, .docx via python-docx, .txt/.md off disk),
    runs the package's parse pipeline, then deletes the temp file.

    Raises:
        ExtractError      unsupported/unreadable rubric format
        LLMConfigError    no model configured to do the structural extraction
        LLMRequestError   the model call failed or returned unusable JSON
        ValueError        the rubric text was empty / produced no criteria
    """
    suffix = Path(filename or "").suffix or ".txt"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(data)
        tmp.close()
        rubric = parse_rubric_file(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    return [
        RubricCriterionIn(
            parameter_title=c.parameter_title,
            description=c.description,
            points=c.points,
        )
        for c in rubric.rubric
    ]
