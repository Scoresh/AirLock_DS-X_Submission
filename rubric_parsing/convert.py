"""Document-to-text conversion for rubric parsing (pure Python, no pandoc).

Routing by file type, because no single tool reads everything:
  * .pdf              -> PyMuPDF (fitz), falling back to pdfplumber
  * .txt/.md/.tex     -> read straight off disk
  * .docx             -> python-docx if present, else unzip + XML (stdlib)
  * .odt              -> unzip + XML (stdlib)
  * .html/.htm/.xhtml -> stdlib HTML parser (tags stripped)
  * .rtf              -> striprtf if present, else a minimal built-in stripper
  * .epub             -> unzip + strip the XHTML spine (stdlib)

Everything here runs locally. The extracted text is the rubric's grading
criteria supplied by the user; this module never touches participant document
content, so it stays clear of the privacy-gate path.
"""
from __future__ import annotations

import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

# Extensions we read straight off disk (already plain text / Markdown-ish).
_PLAINTEXT_SUFFIXES = {".txt", ".md", ".markdown", ".tex", ".latex"}


class ConversionError(RuntimeError):
    """Raised when document-to-text conversion fails."""


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
def _pdf_to_text(src: Path) -> str:
    """Extract text from a PDF. Tries PyMuPDF first, then pdfplumber."""
    try:
        import fitz  # type: ignore  # PyMuPDF — part of the declared stack.

        parts: list[str] = []
        with fitz.open(src) as doc:
            for page in doc:
                parts.append(page.get_text())
        text = "\n".join(parts).strip()
        if text:
            return text
    except ModuleNotFoundError:
        pass  # fall through to pdfplumber
    except Exception as exc:  # noqa: BLE001 - surface as a clear ConversionError
        raise ConversionError(f"PyMuPDF failed to read {src}: {exc}") from exc

    try:
        import pdfplumber  # type: ignore

        parts = []
        with pdfplumber.open(src) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        text = "\n".join(parts).strip()
        if text:
            return text
        raise ConversionError(f"no extractable text in {src} (is it a scanned image?)")
    except ModuleNotFoundError as exc:
        raise ConversionError(
            f"cannot read PDF {src}: install a PDF reader, e.g. `pip install pymupdf`."
        ) from exc


# --------------------------------------------------------------------------- #
# DOCX (Office Open XML — a zip of XML parts)
# --------------------------------------------------------------------------- #
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx_to_text(src: Path) -> str:
    # Prefer python-docx when available (handles tables/sections more robustly).
    try:
        import docx  # type: ignore  # python-docx

        document = docx.Document(str(src))
        parts = [p.text for p in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append("\t".join(cell.text for cell in row.cells))
        text = "\n".join(parts).strip()
        if text:
            return text
    except ModuleNotFoundError:
        pass  # fall through to the stdlib unzip path
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"python-docx failed to read {src}: {exc}") from exc

    # stdlib fallback: pull text out of word/document.xml directly.
    try:
        with zipfile.ZipFile(src) as zf:
            xml = zf.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise ConversionError(f"not a readable .docx file: {src} ({exc})") from exc

    root = ET.fromstring(xml)
    lines: list[str] = []
    for para in root.iter(f"{_W_NS}p"):
        runs = [node.text or "" for node in para.iter(f"{_W_NS}t")]
        lines.append("".join(runs))
    text = "\n".join(lines).strip()
    if not text:
        raise ConversionError(f"no extractable text in {src}")
    return text


# --------------------------------------------------------------------------- #
# ODT (OpenDocument Text — a zip whose content.xml holds the body)
# --------------------------------------------------------------------------- #
def _odt_to_text(src: Path) -> str:
    try:
        with zipfile.ZipFile(src) as zf:
            xml = zf.read("content.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise ConversionError(f"not a readable .odt file: {src} ({exc})") from exc

    root = ET.fromstring(xml)
    text_ns = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
    para_tags = {f"{text_ns}p", f"{text_ns}h"}
    lines: list[str] = []
    # Walk in document order so headings and paragraphs stay interleaved.
    for node in root.iter():
        if node.tag in para_tags:
            lines.append("".join(node.itertext()))
    text = "\n".join(lines).strip()
    if not text:
        raise ConversionError(f"no extractable text in {src}")
    return text


# --------------------------------------------------------------------------- #
# HTML / XHTML
# --------------------------------------------------------------------------- #
class _TextExtractor(HTMLParser):
    """Collect visible text, dropping <script>/<style> and collapsing tags."""

    _BLOCK = {
        "p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
        "table", "ul", "ol", "section", "article", "header", "footer",
    }
    _SKIP = {"script", "style", "head", "meta", "link"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BLOCK:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in self._BLOCK:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._chunks.append(data)

    def get_text(self) -> str:
        raw = "".join(self._chunks)
        # Collapse runs of blank lines / trailing spaces.
        lines = [ln.strip() for ln in raw.splitlines()]
        out: list[str] = []
        for ln in lines:
            if ln or (out and out[-1]):
                out.append(ln)
        return "\n".join(out).strip()


def _html_to_text(src: Path) -> str:
    html = src.read_text(encoding="utf-8", errors="replace")
    parser = _TextExtractor()
    parser.feed(html)
    text = parser.get_text()
    if not text:
        raise ConversionError(f"no extractable text in {src}")
    return text


# --------------------------------------------------------------------------- #
# RTF
# --------------------------------------------------------------------------- #
def _rtf_to_text(src: Path) -> str:
    raw = src.read_text(encoding="utf-8", errors="replace")
    try:
        from striprtf.striprtf import rtf_to_text  # type: ignore

        text = rtf_to_text(raw).strip()
        if text:
            return text
    except ModuleNotFoundError:
        pass  # fall through to the minimal built-in stripper

    text = _strip_rtf_minimal(raw)
    if not text:
        raise ConversionError(
            f"could not extract text from {src}; for better RTF support "
            f"`pip install striprtf`."
        )
    return text


def _strip_rtf_minimal(raw: str) -> str:
    """Very small RTF stripper for the common case (no striprtf installed)."""
    # Drop binary/font/color tables and groups we never want as text.
    raw = re.sub(r"\\'[0-9a-fA-F]{2}", "", raw)          # hex-escaped chars
    raw = re.sub(r"\\\*\\[a-zA-Z]+[^{}]*", "", raw)      # ignorable destinations
    raw = re.sub(r"\\par[d]?\b", "\n", raw)              # paragraph breaks
    raw = re.sub(r"\\tab\b", "\t", raw)
    raw = re.sub(r"\\[a-zA-Z]+-?\d*\s?", "", raw)        # other control words
    raw = raw.replace("{", "").replace("}", "")
    lines = [ln.strip() for ln in raw.splitlines()]
    return "\n".join(ln for ln in lines if ln).strip()


# --------------------------------------------------------------------------- #
# EPUB (zip of XHTML documents)
# --------------------------------------------------------------------------- #
def _epub_to_text(src: Path) -> str:
    try:
        with zipfile.ZipFile(src) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith((".xhtml", ".html", ".htm"))]
            names.sort()
            parser = _TextExtractor()
            for name in names:
                parser.feed(zf.read(name).decode("utf-8", "replace"))
    except zipfile.BadZipFile as exc:
        raise ConversionError(f"not a readable .epub file: {src} ({exc})") from exc

    text = parser.get_text()
    if not text:
        raise ConversionError(f"no extractable text in {src}")
    return text


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #
_HANDLERS = {
    ".pdf": _pdf_to_text,
    ".docx": _docx_to_text,
    ".odt": _odt_to_text,
    ".html": _html_to_text,
    ".htm": _html_to_text,
    ".xhtml": _html_to_text,
    ".rtf": _rtf_to_text,
    ".epub": _epub_to_text,
}


def to_text(path: str | Path, timeout: int = 60) -> str:  # noqa: ARG001 - kept for API compat
    """Convert a rubric file to plain text/Markdown, routing by file type.

    ``timeout`` is accepted for backward compatibility with the old pandoc
    wrapper but is unused now that conversion runs in-process.
    """
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(f"rubric file not found: {src}")

    suffix = src.suffix.lower()
    if suffix in _PLAINTEXT_SUFFIXES:
        # utf-8-sig transparently strips a leading BOM if present.
        return src.read_text(encoding="utf-8-sig", errors="replace")

    handler = _HANDLERS.get(suffix)
    if handler is not None:
        return handler(src)

    # Unknown extension: best-effort plain-text read so we fail soft, not hard.
    if suffix in ("", ".doc"):
        raise ConversionError(
            f"unsupported format '{suffix or 'no extension'}' for {src}. "
            f"Legacy .doc is not supported; save as .docx, .pdf, .odt, .rtf, "
            f"or .txt and retry."
        )
    return src.read_text(encoding="utf-8", errors="replace")
