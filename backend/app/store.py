"""In-memory state per document. Nothing is written to disk except the token key file."""
from dataclasses import dataclass, field
from threading import RLock

from .schemas import ParseResult, ScoreResult, ScrubResult


@dataclass
class DocState:
    parsed: ParseResult | None = None
    scrubbed: ScrubResult | None = None
    scored: ScoreResult | None = None
    accepted: list = field(default_factory=list)
    population_source: str = "local"
    score_binding: str | None = None
    population_manifest: dict | None = None
    scored_at: float = 0
    lock: object = field(default_factory=RLock)



DOCS: dict[str, DocState] = {}


def get(doc_id: str) -> DocState:
    return DOCS.setdefault(doc_id, DocState())
