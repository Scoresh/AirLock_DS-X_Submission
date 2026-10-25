# Add .docx support to rubric_parsing extract

**Files changed:**
- `rubric_parsing/extract.py`
- `testing_superduper.py`
- `backend/requirements.txt`

Added a `_docx_to_text()` function to `rubric_parsing/extract.py` and routed `.docx` files to it in `to_text()`, so Word rubrics can be parsed without pandoc. It uses `python-docx` and walks the document body in order, extracting text from both paragraphs and table cells (rubrics are commonly laid out as Word tables); rows are tab-joined and blocks newline-joined to preserve rough structure for the LLM step. If `python-docx` is not installed it raises a clear `ExtractError` telling the user to `pip install python-docx`, and an unreadable/empty docx also raises `ExtractError`. Pinned `python-docx==1.1.2` in `backend/requirements.txt` and re-added `.docx` to the `testing_superduper.py` file dialog filter. Verified end to end by generating a docx with a heading, paragraph, and a 3-column rubric table and confirming all content is extracted in document order.
