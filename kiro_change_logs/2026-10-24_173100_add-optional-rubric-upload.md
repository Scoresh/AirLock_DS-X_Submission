# Add optional rubric upload

**Files changed:**
- backend/app/main.py
- frontend/index.html
- frontend/app.js
- frontend/styles.css
- rubric_parsing/convert.py

Added an optional way to upload a custom grading rubric and review the document against it, defaulting to the built-in academic-writing rubric when none is provided. Backend: new `POST /rubric` endpoint accepts an uploaded file (pdf/docx/odt/html/rtf/md/txt/tex/epub), writes it to a temp file, converts it to plain text locally via the pure-Python `rubric_parsing.convert.to_text`, deletes the temp file, and returns `{filename, rubric_text}`; the `rubric_parsing` import is lazy and the repo root is added to `sys.path` so the package stays optional and never blocks startup. The rubric is grading criteria (not participant content), so it is outside the privacy-gate path, and conversion makes no network call. Frontend: added a collapsible "Use a custom rubric (optional)" uploader inside the step-2 gate card; choosing a file posts it to `/rubric`, stores the returned text, and shows a parsed-word count (errors fall back to the default with a visible message). The existing `/review` call now includes `rubric_text` only when a custom rubric was uploaded, so default behavior is unchanged. Also made the plaintext converter read with `utf-8-sig` to strip stray BOMs. Verified `/rubric` with txt/docx/empty inputs, confirmed a headless browser upload sets the status correctly, and confirmed `/review` accepts the custom `rubric_text` once the gate is open; no existing data contract changed. The running server was restarted via the StrangerModeUvicorn scheduled task to load the new endpoint.
