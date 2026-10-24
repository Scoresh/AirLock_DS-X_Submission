"""Measurable BU thesis-guide rules, checked with code (no LLM).  Owners: Aedyn + Florian.

Each rule takes the parsed pages and returns findings with source="rule".
Cap: 8 rules. Thresholds still need confirming against the BU guide.
"""
import re
from collections import Counter

from .schemas import BBox, Finding, ParseResult

PT_PER_IN = 72
MIN_LEFT_MARGIN_IN = 1.5  # TODO: confirm against the BU guide
ABSTRACT_HEADING = re.compile(r"^\s*abstract\b", re.I | re.M)


def check_left_margin(parsed: ParseResult) -> list[Finding]:
    findings = []
    for p in parsed.pages:
        m = p.layout.margins_in
        if not p.text or m.left >= MIN_LEFT_MARGIN_IN:
            continue
        # Highlight the strip where text intrudes into the required margin.
        strip = BBox(x0=m.left * PT_PER_IN, y0=m.top * PT_PER_IN,
                     x1=MIN_LEFT_MARGIN_IN * PT_PER_IN, y1=(p.layout.height_in - m.bottom) * PT_PER_IN)
        findings.append(Finding(
            page=p.page,
            criterion=f"Left margin must be at least {MIN_LEFT_MARGIN_IN} inches",
            issue=f"Left margin is {m.left} in",
            severity="error",
            source="rule",
            bbox=[strip],
        ))
    return findings


def check_abstract(parsed: ParseResult) -> list[Finding]:
    if not parsed.pages or any(ABSTRACT_HEADING.search(p.text[:300]) for p in parsed.pages):
        return []
    return [Finding(
        page=min(2, len(parsed.pages)),
        criterion="An abstract page must follow the title page",
        issue="No page starting with an “Abstract” heading was found",
        severity="error",
        source="rule",
    )]


def check_page_number_position(parsed: ParseResult) -> list[Finding]:
    positions = {p.page: p.layout.page_label_position for p in parsed.pages if p.layout.page_label_position}
    if len(positions) < 2:
        return []
    usual, _ = Counter(positions.values()).most_common(1)[0]
    return [
        Finding(
            page=page,
            criterion="Page numbers must appear in the same position on every page",
            issue=f"Page number is {position}; most pages use {usual}",
            severity="error",
            source="rule",
        )
        for page, position in positions.items() if position != usual
    ]


def check_font_consistency(parsed: ParseResult) -> list[Finding]:
    main_fonts = {p.page: (p.layout.fonts[0].name, p.layout.fonts[0].size)
                  for p in parsed.pages if p.layout.fonts}
    if len(main_fonts) < 2:
        return []
    usual, _ = Counter(main_fonts.values()).most_common(1)[0]
    return [
        Finding(
            page=page,
            criterion="Body text should use one font and size throughout",
            issue=f"Main font is {font[0]} {font[1]:g} pt; most pages use {usual[0]} {usual[1]:g} pt",
            severity="warning",
            source="rule",
        )
        for page, font in main_fonts.items() if font != usual
    ]


RULES = [check_left_margin, check_abstract, check_page_number_position, check_font_consistency]


def run_all(parsed: ParseResult) -> list[Finding]:
    return sorted((f for rule in RULES for f in rule(parsed)), key=lambda f: f.page)
