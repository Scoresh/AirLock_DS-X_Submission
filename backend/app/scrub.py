"""Direct identifiers -> tokens, and participant profiles.  Owner: Selina.

Runs fully locally. The token key (token -> original text) is saved to keys/<doc_id>.json
and never included in any API response or LLM request.

TODO:
  - Presidio + regex (BU emails, U-numbers) for direct identifiers
  - rule-based extraction of NSSE quasi-identifiers from participant descriptions
"""
from .mock import load
from .schemas import ParseResult, ScrubResult


def scrub(parsed: ParseResult) -> ScrubResult:
    result = ScrubResult.model_validate(load("scrub"))
    result.doc_id = parsed.doc_id
    return result
