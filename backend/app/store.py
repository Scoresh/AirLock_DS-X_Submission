"""In-memory state per document. Nothing is written to disk except the token key file."""
from dataclasses import dataclass, field

from .schemas import ParseResult, ScoreResult, ScrubResult


@dataclass
class DocState:
    parsed: ParseResult | None = None
    scrubbed: ScrubResult | None = None
    scored: ScoreResult | None = None
    accepted: list = field(default_factory=list)


DOCS: dict[str, DocState] = {}


def get(doc_id: str) -> DocState:
    return DOCS.setdefault(doc_id, DocState())
