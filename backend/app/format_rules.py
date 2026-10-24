"""Measurable BU thesis-guide rules, checked with code (no LLM).  Owners: Aedyn + Florian.

Each rule takes the parsed pages and returns findings with source="rule".
Cap: 8 rules. Start with margins, font, page-number position.
"""
from .schemas import Finding, ParseResult

MIN_LEFT_MARGIN_IN = 1.5  # TODO: confirm against the BU guide


def check_left_margin(parsed: ParseResult) -> list[Finding]:
    return [
        Finding(
            page=p.page,
            criterion=f"Left margin must be at least {MIN_LEFT_MARGIN_IN} inches",
            issue=f"Left margin is {p.layout.margins_in.left} in",
            severity="error",
            source="rule",
        )
        for p in parsed.pages
        if p.layout.margins_in.left < MIN_LEFT_MARGIN_IN
    ]


RULES = [check_left_margin]


def run_all(parsed: ParseResult) -> list[Finding]:
    return [f for rule in RULES for f in rule(parsed)]
