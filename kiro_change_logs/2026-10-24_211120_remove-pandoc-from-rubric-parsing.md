# Remove pandoc functionality from rubric_parsing

**Files changed:**
- `rubric_parsing/pandoc.py` (deleted)
- `rubric_parsing/extract.py` (new)
- `rubric_parsing/__init__.py`
- `rubric_parsing/parser.py`
- `rubric_parsing/__main__.py`
- `testing_superduper.py`
- `.gitignore`

Removed all pandoc functionality from the `rubric_parsing` package. Deleted `pandoc.py` (which shelled out to the bundled `libdump/pandoc.exe` for docx/odt/rtf/html/epub/tex conversion) and replaced it with `extract.py`, which exposes `to_text()` and `ExtractError`. The new module supports only PDF (via PyMuPDF with a pdfplumber fallback) and plaintext/Markdown (`.txt`/`.md`) read off disk; any other format now raises a clear `ExtractError` telling the user to convert to PDF or text first. Updated the public API (`__init__.py`) to export `to_text`/`ExtractError` instead of `to_markdown`/`PandocError`, updated `parser.py` to call `extract.to_text`, and updated the CLI (`__main__.py`) exception handling and help text. Updated `testing_superduper.py` imports, dialog filetypes, and error handling to match, and removed the `libdump/pandoc.exe` entry from `.gitignore`. Verified that all modules import cleanly, plaintext extraction works, and a former-pandoc format (`.docx`) is now correctly rejected.
