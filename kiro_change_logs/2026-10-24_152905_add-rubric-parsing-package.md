# Add rubric_parsing package (file -> pandoc -> LLM -> structured JSON)

**Files changed:**
- rubric_parsing/__init__.py
- rubric_parsing/schemas.py
- rubric_parsing/pandoc.py
- rubric_parsing/llm.py
- rubric_parsing/parser.py
- rubric_parsing/__main__.py

Created a self-contained `rubric_parsing` Python package that turns an arbitrary rubric file into the JSON shape `{"rubric": [{"parameter_title", "description", "points"(optional)}, ...]}`. `schemas.py` defines dependency-free dataclasses (`Rubric`, `RubricCriterion`) that validate input and make `points` optional. `pandoc.py` wraps the bundled `libdump/pandoc.exe` to convert docx/pdf/html/etc. to Markdown, reading plain .txt/.md directly. `llm.py` is a configurable OpenAI-compatible client using only stdlib `urllib`, reading `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY` from the environment to match the backend convention and work with hosted models or local Ollama. `parser.py` orchestrates pandoc then the LLM, robustly extracts JSON (handling code fences and stray prose via a balanced-brace fallback), and validates it. `__main__.py` adds a CLI (`python -m rubric_parsing <file> [--out]`). An external LLM is used because rubric layouts vary and the LLM remains a configurable setting, not a hard dependency. This module handles only user-supplied grading criteria (not participant document text), so it stays clear of the privacy-gate path. Verified with schema round-trip/validation tests, a real pandoc HTML-to-Markdown conversion, and a full end-to-end run against a mock OpenAI-compatible server.
