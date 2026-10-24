# Add Stranger Mode project skeleton

**Files changed:**
- `README.md`
- `.gitignore`
- `backend/` (FastAPI app: `main.py`, `schemas.py`, `parse.py`, `format_rules.py`, `scrub.py`, `risk.py`, `review.py`, `store.py`, `mock.py`, `requirements.txt`)
- `frontend/index.html`
- `mock/parse.json`, `mock/scrub.json`, `mock/score.json`, `mock/review.json`
- `data/README.md`, `docs/NSSE-2026-US-Codebook.docx`, `keys/.gitkeep`

Added a runnable skeleton so all four teammates can start in parallel without waiting on each other. The four data contracts (parse, scrub, score, review) are defined in `backend/app/schemas.py`, with matching example files in `mock/`. Every module has a named owner and currently returns the mock data, so the full pipeline runs end to end today. The privacy gate is enforced in `/review`, which returns 403 until high-risk participants' fixes are accepted. A minimal test page in `frontend/` drives the whole flow: upload, gate, heatmap, and what the LLM saw. The `.gitignore` keeps token keys (`keys/`) and NSSE data (`data/`) out of git. The public NSSE 2026 US codebook was added to `docs/` and the scoring fields are listed in the README. The full flow was tested with FastAPI's test client; the UI was not clicked through in a browser.
