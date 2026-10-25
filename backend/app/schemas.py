"""Data contracts shared by every module. Change these only after telling the team.

Examples of each shape live in /mock/*.json.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------- shared geometry ----------

class BBox(BaseModel):
    """A rectangle on a page, in PDF points (72 per inch), origin at top-left.

    The frontend scales these to its rendered page width.
    """
    x0: float
    y0: float
    x1: float
    y1: float


# ---------- 1. parse (owners: Aedyn + Florian) ----------

class Margins(BaseModel):
    top: float
    bottom: float
    left: float
    right: float


class FontUse(BaseModel):
    name: str
    size: float
    chars: int


class Layout(BaseModel):
    width_in: float
    height_in: float
    margins_in: Margins
    fonts: list[FontUse]
    page_label: str | None = None           # the printed page number, e.g. "iv" or "12"
    page_label_position: str | None = None  # e.g. "bottom-center", "top-right"


class PageImage(BaseModel):
    """A raster image embedded on a page, located in PDF points (72 per inch).

    Surfaced so the pipeline knows text extraction may have missed content that
    lives inside an image (a scan, a figure, a screenshot) — which can carry PII
    the text path never sees. `page_coverage` is the fraction of the page area
    the image covers (1.0 = full-page scan). No OCR is performed here; this is
    metadata only, built so OCR can slot in behind the same contract later.
    """
    xref: int                  # PDF cross-reference id of the image object
    bbox: BBox                 # where it sits on the page, in points
    width_px: int              # pixel dimensions of the stored image
    height_px: int
    colorspace: str | None = None  # e.g. "DeviceRGB", "DeviceGray"
    page_coverage: float = 0.0      # 0..1 fraction of the page area covered


class Page(BaseModel):
    page: int  # 1-based physical page index
    text: str
    layout: Layout
    images: list["PageImage"] = []  # raster images embedded on this page
    image_only: bool = False        # has image(s) but little/no extractable text
                                     # (likely a scan: the text pipeline will miss its content)


class ParseResult(BaseModel):
    doc_id: str
    pages: list[Page]
    has_images: bool = False              # any page carries at least one raster image
    image_only_pages: list[int] = []      # 1-based pages that are image-only (likely scans);
                                          # their content is NOT in the extracted text


# ---------- 2. scrub (owner: Selina) ----------

class ScrubbedPage(BaseModel):
    page: int
    text: str


class DirectIdentifier(BaseModel):
    token: str  # e.g. "[EMAIL_01]"; the original value lives only in keys/<doc_id>.json
    type: Literal["PERSON", "EMAIL", "PHONE", "STUDENT_ID", "SECTION", "OTHER"]
    page: int


class Evidence(BaseModel):
    page: int
    quote: str


class Participant(BaseModel):
    id: str  # e.g. "PARTICIPANT_03"
    pages: list[int]
    attributes: dict[str, str | int]  # keys are NSSE field names: IRage, country22, MAJfirstcode, ...
    evidence: list[Evidence]
    mentions: dict[str, str] = {}  # NSSE field -> exact words in the scrubbed text, e.g. {"country22": "Iceland"}


class ScrubResult(BaseModel):
    doc_id: str
    scrubbed_pages: list[ScrubbedPage]
    direct_identifiers: list[DirectIdentifier]
    participants: list[Participant]


# ---------- 3. score + gate (owner: Selina) ----------

Risk = Literal["high", "medium", "low"]


class Suggestion(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    field: str                         # current NSSE field, e.g. "country22"
    from_: str = Field(alias="from")   # "from" is a Python keyword
    to: str
    new_field: str                     # coarser NSSE field, e.g. "countrycol22"
    new_k: int


class ScoredParticipant(BaseModel):
    id: str
    k: int
    risk: Risk
    attributes: dict[str, str | int]
    suggestions: list[Suggestion]


class ScoreResult(BaseModel):
    doc_id: str
    participants: list[ScoredParticipant]
    gate_open: bool


class AcceptedFix(BaseModel):
    participant_id: str
    field: str  # which suggestion to apply, by its "field"


class ScoreRequest(BaseModel):
    doc_id: str
    accepted: list[AcceptedFix] = []


# ---------- 4. review (owner: Dan) ----------

class Finding(BaseModel):
    page: int
    quote: str | None = None
    criterion: str  # the rubric rule, quoted
    issue: str
    severity: Literal["error", "warning"]
    source: Literal["rule", "llm"]
    bbox: list[BBox] = []  # regions to highlight; empty = page-level, render as a badge.
                           # A quote that wraps across lines yields one box per line.


ModelReviewStatus = Literal["not_configured", "not_implemented", "sent", "failed"]


class ReviewResult(BaseModel):
    doc_id: str
    findings: list[Finding]
    model_review: ModelReviewStatus = "not_configured"  # did the prepared text actually reach a model?
    model: str | None = None
    model_error: str | None = None  # why a model review failed, if it did


class ReviewRequest(BaseModel):
    doc_id: str
    rubric_text: str | None = None  # None = use the BU thesis guide
    format_only: bool = False       # True = run only local format rules, send nothing to a model
                                    # (used by the UI to auto-run checks without a network call)


# ---------- 5. rubric check (compare prepared document against a parsed rubric) ----------
# Additive feature. The rubric itself comes from the `rubric_parsing` package
# (shape: {"rubric": [{"parameter_title", "description", "points"?}, ...]}).
# Only the gate-approved, tokenized prepared text is ever sent to the model.

class RubricCriterionIn(BaseModel):
    parameter_title: str
    description: str
    points: float | None = None


class RubricCheckRequest(BaseModel):
    rubric: list[RubricCriterionIn]


class RubricParseResult(BaseModel):
    """Structured rubric parsed from an uploaded rubric file (docx/pdf/txt/md).

    Same shape the `rubric_parsing` package emits, ready to pipe straight into
    the rubric-check request.
    """
    rubric: list[RubricCriterionIn]


class RubricCriterionResult(BaseModel):
    parameter_title: str
    description: str
    points: float | None = None
    fulfilled: bool | None = None  # True/False from the model; None if it could not decide / not run
    comment: str = ""              # the model's explanation for this criterion
    needs_more_info: bool = False  # criterion references an image/figure the text path cannot see,
                                   # so it cannot be judged from the prepared text alone


class RubricCheckResult(BaseModel):
    doc_id: str
    results: list[RubricCriterionResult]
    model_review: ModelReviewStatus = "not_configured"  # did the prepared text actually reach a model?
    model: str | None = None
    model_error: str | None = None  # why the model request failed, if it did (same as ReviewResult)


# ---------- 6. settings (LLM endpoint configuration) ----------
# Applied to os.environ at runtime; never persisted, API key never returned.

class SettingsUpdate(BaseModel):
    provider: str                       # "openai" | "gemini" | "claude" | "custom"
    model: str | None = None            # defaults to the provider preset if omitted
    api_key: str | None = None          # None = keep existing key; "" = clear it
    base_url: str | None = None         # required only for "custom"


class SettingsState(BaseModel):
    configured: bool
    provider: str | None = None
    base_url: str | None = None
    endpoint: str | None = None
    model: str | None = None
    has_api_key: bool = False


class SettingsTestResult(BaseModel):
    ok: bool
    detail: str
