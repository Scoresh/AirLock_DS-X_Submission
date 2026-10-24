"""Document-to-text conversion for rubric parsing.

Routing by file type, because no single tool reads everything:
  * .pdf           -> PyMuPDF (fitz), falling back to pdfplumber
  * .txt/.md       -> read straight off disk
  * everything else-> bundled libdump/pandoc.exe (docx, odt, html, rtf, epub, tex...)

Pandoc CANNOT read PDF (it is a write-only target for pandoc), so PDFs are
handled separately with the project's declared PDF library.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

# repo root = two levels up from this file (rubric_parsing/pandoc.py -> repo root)
_REPO_ROOT = Path(__file__).resolve().parents[1]
PANDOC_EXE = _REPO_ROOT / "libdump" / "pandoc.exe"

# Extensions we read straight off disk.
_PLAINTEXT_SUFFIXES = {".txt", ".md", ".markdown"}


class PandocError(RuntimeError):
    """Raised when document-to-text conversion fails."""


def _pandoc_exe() -> Path:
    if not PANDOC_EXE.is_file():
        raise PandocError(f"pandoc.exe not found at {PANDOC_EXE}")
    return PANDOC_EXE


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
    except Exception as exc:  # noqa: BLE001 - surface as a clear PandocError
        raise PandocError(f"PyMuPDF failed to read {src}: {exc}") from exc

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
        raise PandocError(f"no extractable text in {src} (is it a scanned image?)")
    except ModuleNotFoundError as exc:
        raise PandocError(
            f"cannot read PDF {src}: install a PDF reader, e.g. "
            f"`pip install pymupdf` (pandoc cannot read PDF input)."
        ) from exc


def _run_pandoc(src: Path, timeout: int) -> str:
    exe = _pandoc_exe()
    cmd = [str(exe), str(src), "--to", "gfm", "--wrap", "none"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise PandocError(f"pandoc timed out after {timeout}s on {src}") from exc

    if proc.returncode != 0:
        raise PandocError(
            f"pandoc failed on {src} (exit {proc.returncode}): {proc.stderr.strip()}"
        )

    text = proc.stdout.strip()
    if not text:
        raise PandocError(f"pandoc produced no text for {src}")
    return text


def to_markdown(path: str | Path, timeout: int = 60) -> str:
    """Convert a rubric file to text/Markdown, routing by file type."""
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(f"rubric file not found: {src}")

    suffix = src.suffix.lower()
    if suffix == ".pdf":
        return _pdf_to_text(src)
    if suffix in _PLAINTEXT_SUFFIXES:
        return src.read_text(encoding="utf-8", errors="replace")
    return _run_pandoc(src, timeout)
