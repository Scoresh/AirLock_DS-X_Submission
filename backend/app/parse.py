"""PDF -> pages with text and layout.  Owner: Selina (taken over from Aedyn + Florian).

PyMuPDF reads each page locally:
  - text: the page's text blocks in reading order, without the printed page number
  - margins: distance from the page edges to the outermost text block
  - fonts: font name and size of every text span, with character counts
  - page label: a short number (arabic or roman) alone in the top or bottom band

Uploading nothing (the UI sends a placeholder) or a .txt file still works, so the
pipeline can be tested without a real PDF.
"""
import re
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

from .schemas import FontUse, Layout, Margins, Page, ParseResult

PT_PER_IN = 72
LABEL_BAND_IN = 0.9  # page numbers sit within this distance of the top or bottom edge
PAGE_LABEL = re.compile(r"^(\d{1,4}|[ivxlcdm]{1,7})$", re.I)
SAMPLE_PDF = Path(__file__).resolve().parents[2] / "samples" / "test-thesis.pdf"
PLACEHOLDER = b"%PDF-mock"


class ParseError(ValueError):
    """The upload is not a readable PDF or text file."""


def _label_position(rect: fitz.Rect, page: fitz.Rect) -> str:
    vertical = "top" if rect.y1 < page.height / 2 else "bottom"
    center = (rect.x0 + rect.x1) / 2
    if center < page.width / 3:
        horizontal = "left"
    elif center > page.width * 2 / 3:
        horizontal = "right"
    else:
        horizontal = "center"
    return f"{vertical}-{horizontal}"


def _paragraphs(body: list) -> list[str]:
    """Join blocks that are consecutive lines of one paragraph.

    Some PDF writers emit every justified line as its own block; without this, sentences
    (and names) would be split by paragraph breaks at every line end.
    """
    paras: list[tuple[fitz.Rect, list[str], float]] = []
    for rect, block in body:
        lines = ["".join(s["text"] for s in line["spans"]).strip() for line in block["lines"]]
        last = block["lines"][-1]["bbox"]
        line_h = last[3] - last[1]
        if paras:
            prev, prev_lines, prev_h = paras[-1]
            close = 0 <= rect.y0 - prev.y1 < 0.5 * prev_h
            aligned = abs(rect.x0 - prev.x0) < 0.25 * PT_PER_IN
            if close and aligned:
                paras[-1] = (prev | rect, prev_lines + lines, line_h)
                continue
        paras.append((rect, lines, line_h))
    return ["\n".join(l for l in lines if l) for _, lines, _ in paras]


def _parse_page(page: fitz.Page, number: int) -> Page:
    area = page.rect
    band = LABEL_BAND_IN * PT_PER_IN
    blocks = [b for b in page.get_text("dict")["blocks"] if b.get("type") == 0]

    label, label_position, body = None, None, []
    for block in blocks:
        text = " ".join(s["text"] for line in block["lines"] for s in line["spans"]).strip()
        rect = fitz.Rect(block["bbox"])
        in_band = rect.y1 < band or rect.y0 > area.height - band
        if label is None and in_band and PAGE_LABEL.match(text):
            label, label_position = text, _label_position(rect, area)
        elif text:
            body.append((rect, block))

    fonts: Counter = Counter()
    for _, block in body:
        for line in block["lines"]:
            for span in line["spans"]:
                fonts[(span["font"], round(span["size"], 1))] += len(span["text"].strip())

    if body:
        x0 = min(r.x0 for r, _ in body)
        y0 = min(r.y0 for r, _ in body)
        x1 = max(r.x1 for r, _ in body)
        y1 = max(r.y1 for r, _ in body)
        margins = Margins(top=y0 / PT_PER_IN, bottom=(area.height - y1) / PT_PER_IN,
                          left=x0 / PT_PER_IN, right=(area.width - x1) / PT_PER_IN)
    else:  # blank page
        margins = Margins(top=0, bottom=0, left=0, right=0)

    text = "\n\n".join(_paragraphs(body))
    return Page(
        page=number,
        text=text,
        layout=Layout(
            width_in=round(area.width / PT_PER_IN, 2),
            height_in=round(area.height / PT_PER_IN, 2),
            margins_in=Margins(**{k: round(v, 2) for k, v in margins.model_dump().items()}),
            fonts=[FontUse(name=n, size=s, chars=c) for (n, s), c in fonts.most_common() if c],
            page_label=label,
            page_label_position=label_position,
        ),
    )


def _parse_text(raw: bytes, doc_id: str) -> ParseResult:
    """Plain text: pages split on form feeds, letter size, no layout data."""
    text = raw.decode("utf-8", errors="replace")
    no_layout = Layout(width_in=8.5, height_in=11, margins_in=Margins(top=1, bottom=1, left=1.5, right=1),
                       fonts=[])
    pages = [Page(page=i, text=t.strip(), layout=no_layout)
             for i, t in enumerate(text.split("\f"), start=1) if t.strip()]
    return ParseResult(doc_id=doc_id, pages=pages)


def parse_pdf(pdf_bytes: bytes, doc_id: str) -> ParseResult:
    if not pdf_bytes or pdf_bytes.startswith(PLACEHOLDER):
        pdf_bytes = SAMPLE_PDF.read_bytes()
    if not pdf_bytes.startswith(b"%PDF"):
        try:
            pdf_bytes.decode("utf-8")
        except UnicodeDecodeError as err:
            raise ParseError("upload a PDF or a UTF-8 .txt file") from err
        return _parse_text(pdf_bytes, doc_id)
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except (fitz.FileDataError, RuntimeError) as err:
        raise ParseError(f"could not read PDF: {err}") from err
    with doc:
        pages = [_parse_page(page, i) for i, page in enumerate(doc, start=1)]
    return ParseResult(doc_id=doc_id, pages=pages)
