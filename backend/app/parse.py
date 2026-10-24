"""PDF -> pages with text and layout.  Owners: Aedyn + Florian.

TODO: replace the mock with PyMuPDF (fitz):
  - page.get_text() for text
  - page.get_text("dict") for font names/sizes and text-block positions (margins)
  - detect the printed page number from the top/bottom text blocks
"""
from .mock import load
from .schemas import ParseResult


def parse_pdf(pdf_bytes: bytes, doc_id: str) -> ParseResult:
    result = ParseResult.model_validate(load("parse"))
    result.doc_id = doc_id
    return result
