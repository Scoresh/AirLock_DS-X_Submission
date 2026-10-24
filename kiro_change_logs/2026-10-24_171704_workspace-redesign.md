# Redesign the frontend as a document-centered workspace

**Files changed:**
- `frontend/index.html`, `frontend/styles.css`, `frontend/app.js` (rewritten)
- `backend/app/main.py` (`GET /status`, `GET /sample`, review reports model status)
- `backend/app/review.py` (no more mock model findings; reports `not_configured` / `not_implemented` / `sent`)
- `backend/app/schemas.py` (`ReviewResult.model_review`, `ReviewResult.model`, both optional), `mock/review.json`
- `backend/app/format_rules.py` (margin rule gets a highlight box; new rules: missing abstract, page-number position, font consistency)

The UI is now a three-column workspace (page index / PDF pages / inspector with Document, Privacy check and Review), replacing the hero plus stacked cards. The intake page has an explicit "Open sample document" action instead of launching the demo when no file is chosen. Privacy concerns show the passage, the attribute combination, the estimated k and risk level, and original → proposed rewrites that can be applied one at a time or all at once; the gate explains why it is blocked and never claims anonymity. The masthead separates local processing from model status. `review.py` used to return hard-coded findings labelled as model output although nothing was sent; it now returns no model findings and says why, so the UI can say "nothing was sent" truthfully until the real model call is added (Dan: return "sent" from `llm_review` once it calls the model). Format rules now catch all four planted problems in the test thesis. Google Fonts was removed; PDF.js is still loaded from jsDelivr as before. Checked in the browser at desktop and phone widths: sample upload, individual and bulk rewrites, gate blocked → ready, review with highlighted margin strip, comparison view, keyboard tab navigation, and the non-PDF error.
