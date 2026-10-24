"""k-value scoring, generalization suggestions, privacy gate.  Owner: Selina.

k = sum of WEIGHT2 over NSSE rows matching every attribute
    (WEIGHT2 scales survey respondents up to the institution's population).

Generalization ladder (exact field -> coarser NSSE field):
    IRage -> IRagecol
    country22 -> countrycol22 -> internat26
    MAJfirstcode -> MAJfirstcol
"""
from .mock import load
from .schemas import AcceptedFix, Risk, ScoreResult, ScrubResult

HIGH_MAX_K = 4     # 1-4 blocks sending
MEDIUM_MAX_K = 19  # 5-19 warns


def risk_level(k: int) -> Risk:
    if k <= HIGH_MAX_K:
        return "high"
    if k <= MEDIUM_MAX_K:
        return "medium"
    return "low"


def score(scrubbed: ScrubResult, accepted: list[AcceptedFix]) -> ScoreResult:
    result = ScoreResult.model_validate(load("score"))
    result.doc_id = scrubbed.doc_id
    if accepted:  # mock behavior: pretend accepting fixes makes everyone safe
        for p in result.participants:
            p.k, p.risk, p.suggestions = 41, "low", []
    result.gate_open = all(p.risk != "high" for p in result.participants)
    return result
