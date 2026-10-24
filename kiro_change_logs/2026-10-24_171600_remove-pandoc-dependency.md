# Remove pandoc dependency from the rubric checker

**Files changed:**
- rubric_parsing/convert.py (new)
- rubric_parsing/pandoc.py (now a backward-compat shim)
- rubric_parsing/__init__.py
- rubric_parsing/parser.py
- rubric_parsing/__main__.py
- testing_superduper.py
- backend/requirements.txt
- scripts/setup.bat
- scripts/README.md
- .gitignore

Replaced the `libdump/pandoc.exe` dependency in `rubric_parsing` with a new pure-Python converter module `convert.py` that routes by file type: PDFs stay on PyMuPDF/pdfplumber, `.txt/.md/.tex` are read off disk, `.docx` uses python-docx with a stdlib unzip+XML fallback, `.odt` and `.epub` use stdlib `zipfile`+XML, `.html/.htm/.xhtml` use the stdlib `html.parser`, and `.rtf` uses striprtf with a minimal built-in stripper fallback. The old `pandoc.py` is now a thin shim re-exporting `ConversionError` as `PandocError` and `to_text` as `to_markdown`, so existing imports keep working; `__init__.py`, `parser.py`, `__main__.py`, and `testing_superduper.py` were updated to the new names. Legacy binary `.doc` now raises a clear `ConversionError` telling the user to resave as a supported format. `requirements.txt` adds pinned `python-docx==1.1.2` and `striprtf==0.0.26`, `setup.bat` dropped its pandoc verification step, and the scripts README plus `.gitignore` no longer reference pandoc. Verified all converters (txt, md, tex, html, docx, odt, rtf, epub) and the error paths with generated sample files, and confirmed the package, aliases, and `python -m rubric_parsing --help` all import and run without pandoc. The `libdump/pandoc.exe` binary remains on disk but is no longer referenced by any code.
