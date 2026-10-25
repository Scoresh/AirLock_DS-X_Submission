# Add rubric-vs-document comparison feature (table + LLM check)

**Files changed:**
- `backend/app/schemas.py`
- `backend/app/rubric_check.py` (new)
- `backend/app/main.py`
- `frontend/index.html`
- `frontend/app.js`
- `frontend/styles.css`

Added an end-to-end feature that loads the JSON produced by the `rubric_parsing` package, renders it as a table, and asks the configured LLM whether the prepared document fulfils each criterion. On the backend, added additive schemas (`RubricCriterionIn`, `RubricCheckRequest`, `RubricCriterionResult`, `RubricCheckResult`), a new `rubric_check.py` module that reuses `rubric_parsing.llm` to send only the gate-approved, tokenized text and return a per-criterion `{fulfilled, comment}`, and a `POST /rubric-check/{doc_id}` endpoint that enforces the same privacy gate as `/review` (403 when closed, 400 on empty rubric, 404 on unknown doc). On the frontend, added a new "Rubric" tab and `panel-rubric` (no existing skeleton code removed, including `index.skeleton.html`), a JSON file loader that accepts `{"rubric":[...]}` or a bare array with validation, a results table showing criterion/description/points/verdict/comment, a "Check document against rubric" action wired to the endpoint, and matching styles using the existing palette (green = fulfilled, brick = not fulfilled). Verified the backend via FastAPI TestClient for the no-model path (blank verdicts), empty-rubric 400, closed-gate 403, and unknown-doc 404, and verified the LLM "sent" path against a local OpenAI-compatible stub server that confirmed verdicts and comments are filled and matched back by title. Confirmed `app.js` bundles without syntax errors via bun. When no model is configured the table still loads with blank results and an explanatory note, keeping the LLM a configurable setting rather than a hard dependency.
