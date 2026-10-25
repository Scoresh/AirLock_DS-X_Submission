"""Document-to-text conversion for rubric parsing.

Routing by file type:
  * .pdf           -> PyMuPDF (fitz), falling back to pdfplumber
  * .docx          -> python-docx (paragraphs + table cells)
  * .txt/.md       -> read straight off disk

Other binary formats (odt, rtf, html, epub, ...) are not converted here;
convert them to PDF, .docx, or a plaintext/Markdown file first.
"""
from __future__ import annotations

from pathlib import Path

# Extensions we read straight off disk.
_PLAINTEXT_SUFFIXES = {".txt", ".md", ".markdown"}


class ExtractError(RuntimeError):
    """Raised when document-to-text conversion fails."""


def _pdf_to_text(src: Path) -> str:
    """Extract text from a PDF. Tries PyMuPDF first, then pdfplumber."""
    # PyMuPDF (fitz) — fast, part of the project's declared stack.
    try:
        import fitz  # type: ignore

        parts: list[str] = []
        with fitz.open(src) as doc:
            for page in doc:
                parts.append(page.get_text())
        text = "\n".join(parts).strip()
        if text:
            return text
    except ModuleNotFoundError:
        pass  # fall through to pdfplumber
    except Exception as exc:  # noqa: BLE001 - surface as a clear ExtractError
        raise ExtractError(f"PyMuPDF failed to read {src}: {exc}") from exc

    # pdfplumber fallback.
    try:
        import pdfplumber  # type: ignore

        parts = []
        with pdfplumber.open(src) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        text = "\n".join(parts).strip()
        if text:
            return text
        raise ExtractError(f"no extractable text in {src} (is it a scanned image?)")
    except ModuleNotFoundError as exc:
        raise ExtractError(
            f"cannot read PDF {src}: install a PDF reader, e.g. "
            f"`pip install pymupdf`."
        ) from exc


def _docx_to_text(src: Path) -> str:
    """Extract text from a .docx using python-docx.

    Rubrics are frequently laid out as Word tables, so this walks the document
    body in order, pulling text from both paragraphs and table cells. Rows are
    joined with tabs and blocks with newlines to preserve rough structure for
    the LLM.
    """
    try:
        import docx  # type: ignore
        from docx.document import Document as _Document
        from docx.oxml.ns import qn
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ModuleNotFoundError as exc:
        raise ExtractError(
            f"cannot read .docx {src}: install python-docx, e.g. "
            f"`pip install python-docx`."
        ) from exc

    try:
        document = docx.Document(str(src))
    except Exception as exc:  # noqa: BLE001 - surface as a clear ExtractError
        raise ExtractError(f"python-docx failed to read {src}: {exc}") from exc

    def _iter_block_items(parent):
        """Yield Paragraphs and Tables from the body, in document order."""
        parent_elm = parent.element.body
        for child in parent_elm.iterchildren():
            if child.tag == qn("w:p"):
                yield Paragraph(child, parent)
            elif child.tag == qn("w:tbl"):
                yield Table(child, parent)

    parts: list[str] = []
    for block in _iter_block_items(document):
        if isinstance(block, Paragraph):
            line = block.text.strip()
            if line:
                parts.append(line)
        elif isinstance(block, Table):
            for row in block.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    parts.append("\t".join(cells))

    text = "\n".join(parts).strip()
    if text:
        return text
    raise ExtractError(f"no extractable text in {src}")


def to_text(path: str | Path) -> str:
    """Convert a rubric file to text, routing by file type.

    Supports PDF (via PyMuPDF/pdfplumber), .docx (via python-docx), and
    plaintext/Markdown files.
    """
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(f"rubric file not found: {src}")

    suffix = src.suffix.lower()
    if suffix == ".pdf":
        return _pdf_to_text(src)
    if suffix == ".docx":
        return _docx_to_text(src)
    if suffix in _PLAINTEXT_SUFFIXES:
        return src.read_text(encoding="utf-8", errors="replace")
    raise ExtractError(
        f"unsupported rubric format '{suffix or src.name}': only PDF, .docx, and "
        f"plaintext/Markdown (.txt/.md) are supported. Convert to one of those first."
    )
