"""Data contracts shared by every module. Change these only after telling the team.

Examples of each shape live in /mock/*.json.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class Page(BaseModel):
    page: int  # 1-based physical page index
    text: str
    layout: Layout


class ParseResult(BaseModel):
    doc_id: str
    pages: list[Page]


# ---------- 2. scrub (owner: Selina) ----------

class ScrubbedPage(BaseModel):
    page: int
    text: str


class DirectIdentifier(BaseModel):
    token: str  # e.g. "[EMAIL_01]"; the original value lives only in keys/<doc_id>.json
    type: Literal["PERSON", "EMAIL", "PHONE", "STUDENT_ID", "OTHER"]
    page: int


class Evidence(BaseModel):
    page: int
    quote: str


class Participant(BaseModel):
    id: str  # e.g. "PARTICIPANT_03"
    pages: list[int]
    attributes: dict[str, str | int]  # keys are NSSE field names: IRage, country22, MAJfirstcode, ...
    evidence: list[Evidence]


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

class BBox(BaseModel):
    """A rectangle on a page, in PDF points (72 per inch), origin at top-left.

    The frontend scales these to its rendered page width.
    """
    x0: float
    y0: float
    x1: float
    y1: float


class Finding(BaseModel):
    page: int
    quote: str | None = None
    criterion: str  # the rubric rule, quoted
    issue: str
    severity: Literal["error", "warning"]
    source: Literal["rule", "llm"]
    bbox: list[BBox] = []  # regions to highlight; empty = page-level, render as a badge.
                           # A quote that wraps across lines yields one box per line.


class ReviewResult(BaseModel):
    doc_id: str
    findings: list[Finding]


class ReviewRequest(BaseModel):
    doc_id: str
    rubric_text: str | None = None  # None = use the BU thesis guide
