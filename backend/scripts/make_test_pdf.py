"""Build a short test thesis PDF with planted privacy and formatting problems.

Writes samples/test-thesis.pdf and mock/parse.json (the same pages, as parse.py
should return them), so the test page and parse.py work on identical content.

Participants are real rows of the fallback population (scripts/make_population.py),
so their k-values are at least 1:
    Participant 3  student 3459  high risk -> low after rewrites (k 1 -> 4 -> 74)
    Participant 5  control       low risk
    Participant 7  student 54    high risk -> low
    Participant 9  student 3490  high risk -> low

Run from /backend:  python scripts/make_test_pdf.py
"""
import json
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = ROOT / "samples" / "test-thesis.pdf"
MOCK_PATH = ROOT / "mock" / "parse.json"

PT_PER_IN = 72
PAGE_W, PAGE_H = 8.5, 11

PAGES = [
    {
        "text": "LEARNING UNDER THE NIGHT SKY:\nSTUDENT EXPERIENCES OF CAMPUS STUDY SPACES\n\n"
                "A thesis submitted in partial fulfillment of the requirements\n"
                "for the degree of Bachelor of Arts\n\nBoston University\n2026",
        "margins": {"top": 2.0, "bottom": 1.0, "left": 1.5, "right": 1.0},
        "font": ("tiro", "Times-Roman", 12),
        "label": None,
    },
    {
        "text": "Chapter 2. Methods\n\n"
                "We interviewed four undergraduates about where they study at night. "
                "Participant 3, a 19-year-old sophomore majoring in ethnic studies from Iceland, "
                "lives in campus housing. "
                "Participant 5 is a senior majoring in economics who lives off campus. "
                "Participant 7, a 20-year-old sophomore majoring in biomedical engineering from Sweden, "
                "lives in campus housing. "
                "Participant 9, a 19-year-old first-year majoring in physics, lives in campus housing "
                "and is a varsity athlete.",
        "margins": {"top": 1.0, "bottom": 1.0, "left": 1.5, "right": 1.0},
        "font": ("tiro", "Times-Roman", 12),
        "label": ("1", "bottom-center"),
    },
    {
        "text": "Chapter 3. Findings\n\n"
                "Most participants preferred quiet spaces after 10 PM. Participant 3 described the "
                "library basement as the only place that felt calm during exam weeks, while "
                "Participant 9 studied in team facilities between practices.",
        "margins": {"top": 1.0, "bottom": 1.0, "left": 0.75, "right": 1.0},  # planted: margin too small
        "font": ("tiro", "Times-Roman", 12),
        "label": ("2", "top-right"),  # planted: page number moves
    },
    {
        "text": "Appendix B. Interview Logistics\n\n"
                "Interview scheduling was handled by Maya Lindqvist (mlindq@bu.edu, 617-555-0142). "
                "Maya also transcribed the recordings.",
        "margins": {"top": 1.0, "bottom": 1.0, "left": 1.5, "right": 1.0},
        "font": ("helv", "Helvetica", 11),  # planted: font changes
        "label": ("3", "bottom-center"),
    },
]
# Also planted: no abstract page after the title page.


def _label_point(position: str) -> fitz.Point:
    if position == "top-right":
        return fitz.Point((PAGE_W - 1.0) * PT_PER_IN - 10, 0.6 * PT_PER_IN)
    return fitz.Point(PAGE_W / 2 * PT_PER_IN - 3, (PAGE_H - 0.5) * PT_PER_IN)


def build() -> list[dict]:
    doc = fitz.open()
    mock_pages = []
    for number, spec in enumerate(PAGES, start=1):
        page = doc.new_page(width=PAGE_W * PT_PER_IN, height=PAGE_H * PT_PER_IN)
        m = spec["margins"]
        rect = fitz.Rect(m["left"] * PT_PER_IN, m["top"] * PT_PER_IN,
                         (PAGE_W - m["right"]) * PT_PER_IN, (PAGE_H - m["bottom"]) * PT_PER_IN)
        fontname, font_label, size = spec["font"]
        page.insert_textbox(rect, spec["text"], fontname=fontname, fontsize=size)
        label, position = spec["label"] or (None, None)
        if label:
            page.insert_text(_label_point(position), label, fontname=fontname, fontsize=size)
        mock_pages.append({
            "page": number,
            "text": spec["text"],
            "layout": {
                "width_in": PAGE_W, "height_in": PAGE_H,
                "margins_in": m,
                "fonts": [{"name": font_label, "size": size, "chars": len(spec["text"])}],
                "page_label": label, "page_label_position": position,
            },
        })
    PDF_PATH.parent.mkdir(exist_ok=True)
    doc.save(PDF_PATH)
    return mock_pages


def main() -> None:
    pages = build()
    MOCK_PATH.write_text(json.dumps({"doc_id": "demo", "pages": pages}, indent=2) + "\n")
    print(f"wrote {PDF_PATH} and {MOCK_PATH}")


if __name__ == "__main__":
    main()
