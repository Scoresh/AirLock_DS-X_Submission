"""Measurable BU thesis-guide rules, checked with code (no LLM).  Owners: Aedyn + Florian.

Each rule takes the parsed pages and returns findings with source="rule". Every criterion
cites the page of the "BU Guide for Writers of Theses and Dissertations" it comes from
(see docs/RULES_CHECKLIST.md). Margins are measured to the outermost text on the page,
not counting the page number, so a short page can only fail top, left and right margins.
"""
import re
from collections import Counter
from dataclasses import dataclass
from typing import Callable

from .schemas import BBox, Finding, Page, ParseResult

PT_PER_IN = 72
TOLERANCE_IN = 0.05  # measurement slack for justified text and PDF rounding

MIN_LEFT_IN, MIN_RIGHT_IN, MIN_TOP_IN, MIN_BOTTOM_IN = 1.5, 1.0, 1.5, 1.0
BODY_PT, MIN_PT = 12, 10
ALLOWED_ARABIC = {"top-center", "top-right", "bottom-center", "bottom-right"}
ROMAN = re.compile(r"^[ivxlcdm]+$", re.I)
HEADINGS = {
    "abstract": re.compile(r"^\s*abstract\b", re.I | re.M),
    "contents": re.compile(r"^\s*table of contents\b", re.I | re.M),
    "bibliography": re.compile(r"^\s*(bibliography|references|works cited)\b", re.I | re.M),
}


@dataclass
class Rule:
    id: str
    guide_page: int
    title: str
    check: Callable[[ParseResult], list[Finding]]


def _finding(page: int, guide_page: int, criterion: str, issue: str, severity: str = "error",
             bbox: list[BBox] | None = None) -> Finding:
    return Finding(page=page, criterion=f"BU guide p.{guide_page}: {criterion}", issue=issue,
                   severity=severity, source="rule", bbox=bbox or [])


def _text_pages(parsed: ParseResult) -> list[Page]:
    return [p for p in parsed.pages if p.text.strip()]


def check_left_margin(parsed: ParseResult) -> list[Finding]:
    findings = []
    for p in _text_pages(parsed):
        m = p.layout.margins_in
        if m.left < MIN_LEFT_IN - TOLERANCE_IN:
            # Highlight the strip where text intrudes into the required margin.
            strip = BBox(x0=m.left * PT_PER_IN, y0=m.top * PT_PER_IN,
                         x1=MIN_LEFT_IN * PT_PER_IN, y1=(p.layout.height_in - m.bottom) * PT_PER_IN)
            findings.append(_finding(p.page, 5, "Left margin 1.5 inches",
                                     f"Left margin is {m.left} in", bbox=[strip]))
    return findings


def check_right_margin(parsed: ParseResult) -> list[Finding]:
    return [_finding(p.page, 5, "Right margin 1 inch; do not exceed it",
                     f"Text reaches {p.layout.margins_in.right} in from the right edge")
            for p in _text_pages(parsed) if p.layout.margins_in.right < MIN_RIGHT_IN - TOLERANCE_IN]


def check_top_margin(parsed: ParseResult) -> list[Finding]:
    return [_finding(p.page, 5, "Top margin 1.5 inches to the first line of text or heading",
                     f"First line starts {p.layout.margins_in.top} in from the top")
            for p in _text_pages(parsed) if p.layout.margins_in.top < MIN_TOP_IN - TOLERANCE_IN]


def check_bottom_margin(parsed: ParseResult) -> list[Finding]:
    return [_finding(p.page, 5, "Bottom margin at least 1 inch",
                     f"Text runs to {p.layout.margins_in.bottom} in from the bottom")
            for p in _text_pages(parsed) if p.layout.margins_in.bottom < MIN_BOTTOM_IN - TOLERANCE_IN]


def check_font_size(parsed: ParseResult) -> list[Finding]:
    findings = []
    for p in _text_pages(parsed):
        if not p.layout.fonts:
            continue
        main = p.layout.fonts[0]  # the font with the most characters on the page
        if abs(main.size - BODY_PT) > 0.5:
            findings.append(_finding(p.page, 4, "Use 12-point font for the text",
                                     f"Body text is {main.size:g} pt", "warning"))
        tiny = [f for f in p.layout.fonts if f.size < MIN_PT - 0.25 and f.chars >= 20]
        if tiny:
            findings.append(_finding(p.page, 4, "Do not use smaller than 10-point font",
                                     f"Text set at {min(f.size for f in tiny):g} pt"))
    return findings


def check_calibri(parsed: ParseResult) -> list[Finding]:
    return [_finding(p.page, 5, "Avoid Calibri, the default MS Word typeface",
                     "Calibri is used on this page", "warning")
            for p in _text_pages(parsed) if any("calibri" in f.name.lower() for f in p.layout.fonts)]


def check_font_consistency(parsed: ParseResult) -> list[Finding]:
    main_fonts = {p.page: (p.layout.fonts[0].name, p.layout.fonts[0].size)
                  for p in parsed.pages if p.layout.fonts}
    if len(main_fonts) < 2:
        return []
    usual, _ = Counter(main_fonts.values()).most_common(1)[0]
    return [_finding(page, 5, "Use font type and sizes consistently throughout the work",
                     f"Main font is {font[0]} {font[1]:g} pt; most pages use {usual[0]} {usual[1]:g} pt", "warning")
            for page, font in main_fonts.items() if font != usual]


def check_number_not_left(parsed: ParseResult) -> list[Finding]:
    return [_finding(p.page, 6, "No page number should be placed on the left-hand side of any page",
                     f"Page number is {p.layout.page_label_position}")
            for p in parsed.pages if (p.layout.page_label_position or "").endswith("left")]


def check_roman_bottom_center(parsed: ParseResult) -> list[Finding]:
    return [_finding(p.page, 6, "Preliminary pages have lower-case Roman numerals at the bottom center",
                     f"Roman numeral “{p.layout.page_label}” is {p.layout.page_label_position}")
            for p in parsed.pages
            if p.layout.page_label and ROMAN.match(p.layout.page_label)
            and p.layout.page_label_position != "bottom-center"]


def check_title_page_unnumbered(parsed: ParseResult) -> list[Finding]:
    first = parsed.pages[0] if parsed.pages else None
    if first and first.layout.page_label:
        return [_finding(first.page, 6, "The title page is counted but shows no page number",
                         f"Page number “{first.layout.page_label}” is printed on the title page")]
    return []


def check_number_position(parsed: ParseResult) -> list[Finding]:
    positions = {p.page: p.layout.page_label_position for p in parsed.pages
                 if p.layout.page_label and not ROMAN.match(p.layout.page_label)}
    if len(positions) < 2:
        return []
    usual, _ = Counter(positions.values()).most_common(1)[0]
    findings = []
    for page, position in positions.items():
        if position != usual:
            findings.append(_finding(page, 6, "Select one page number placement for pages with Arabic numerals",
                                     f"Page number is {position}; most pages use {usual}"))
        elif position not in ALLOWED_ARABIC and not position.endswith("left"):
            findings.append(_finding(page, 6, "Arabic page numbers go top center, top right, bottom center or bottom right",
                                     f"Page number is {position}"))
    return findings


def check_required_sections(parsed: ParseResult) -> list[Finding]:
    if not parsed.pages:
        return []
    found = {name: next((p.page for p in parsed.pages if rx.search(p.text[:300])), None)
             for name, rx in HEADINGS.items()}
    findings = []
    labels = {"abstract": "an abstract page", "contents": "a table of contents", "bibliography": "a bibliography"}
    for name, page in found.items():
        if page is None:
            findings.append(_finding(min(2, len(parsed.pages)), 7, f"Required section: {labels[name]}",
                                     f"No page starting with a “{name.title() if name != 'contents' else 'Table of Contents'}” heading was found"))
    if found["abstract"] and found["contents"] and found["abstract"] > found["contents"]:
        findings.append(_finding(found["abstract"], 7, "Order of preliminary pages: abstract comes before the table of contents",
                                 f"Abstract (p. {found['abstract']}) comes after the table of contents (p. {found['contents']})"))
    return findings


RULES = [
    Rule("left-margin", 5, "Left margin at least 1.5 in", check_left_margin),
    Rule("right-margin", 5, "Right margin at least 1 in", check_right_margin),
    Rule("top-margin", 5, "Top margin at least 1.5 in", check_top_margin),
    Rule("bottom-margin", 5, "Bottom margin at least 1 in", check_bottom_margin),
    Rule("font-size", 4, "Body text 12 pt; nothing below 10 pt", check_font_size),
    Rule("no-calibri", 5, "Avoid Calibri", check_calibri),
    Rule("font-consistency", 5, "One font and size throughout", check_font_consistency),
    Rule("number-not-left", 6, "No page number on the left", check_number_not_left),
    Rule("roman-bottom-center", 6, "Roman numerals at bottom center", check_roman_bottom_center),
    Rule("title-unnumbered", 6, "Title page shows no number", check_title_page_unnumbered),
    Rule("number-position", 6, "One page-number position for Arabic pages", check_number_position),
    Rule("required-sections", 7, "Abstract, table of contents, bibliography present and in order", check_required_sections),
]


def run_all(parsed: ParseResult) -> list[Finding]:
    return sorted((f for rule in RULES for f in rule.check(parsed)), key=lambda f: f.page)


def checklist(parsed: ParseResult) -> list[dict]:
    """Pass/fail per rule with the pages that failed, for reports and validation."""
    rows = []
    for rule in RULES:
        failed = rule.check(parsed)
        rows.append({"id": rule.id, "title": rule.title, "guide_page": rule.guide_page,
                     "passed": not failed, "pages": sorted({f.page for f in failed})})
    return rows
