# Remove "not configured" model-review note from Review tab

**Files changed:**
- `frontend/app.js`

In `modelNote()`, the `not_configured` fallback branch previously returned the sentence "Model review didn't run because no model is configured, so nothing was sent. Only local format rules ran. Set LLM_BASE_URL and LLM_MODEL on the server to enable it." The user asked to remove only that small bit of text shown in the right-hand Review findings tab. The branch now returns an empty string, so the message no longer appears when no model is configured. No backend, schema, or review-flow logic was changed.
