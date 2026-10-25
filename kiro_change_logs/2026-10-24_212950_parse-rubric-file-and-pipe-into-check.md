# Parse raw rubric files and pipe straight into the rubric-check logic

**Files changed:**
- `backend/app/schemas.py`
- `backend/app/rubric_check.py`
- `backend/app/main.py`
- `frontend/app.js`
- `frontend/styles.css`

Extended only the rubric feature so it can also accept a raw rubric document (docx/pdf/txt/md), parse it, and immediately feed the result into the existing rubric-check flow. Added a `parse_upload(data, filename)` helper to `rubric_check.py` that writes the upload to a temp file (so `rubric_parsing.extract` routes by extension), runs the package's `parse_rubric_file` pipeline, deletes the temp file, and returns `RubricCriterionIn` objects; it re-exports the parser's error types as `ParseFormatError`/`ParseConfigError`/`ParseRequestError`. Added a `RubricParseResult` schema and a `POST /rubric-parse` endpoint that returns the same shape `/rubric-check` consumes, mapping errors to 400 (unsupported/unreadable format), 503 (no model configured to structure the rubric), and 502 (model/JSON failure); it touches only the user-supplied rubric, never the participant document, so it stays off the privacy-gate path. On the frontend, added a "Parse rubric file" control (and hint) next to the existing "Load rubric JSON" option in the Rubric tab, with a `parseRubricFile()` handler that uploads to `/rubric-parse`, stores the structured result in `state.rubric`, and lets the existing table + "Check document against rubric" logic take over. Verified end to end against a stub OpenAI-compatible server: `/rubric-parse` returns structured criteria (points preserved/omitted), rejects unsupported formats with 400 and missing-model with 503, and the parsed criteria pipe directly into `check()` to produce filled verdicts/comments; `app.js` still bundles cleanly via bun. No other feature paths (scrub, risk, review) were modified.
