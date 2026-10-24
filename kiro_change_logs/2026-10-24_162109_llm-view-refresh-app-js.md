# Re-apply "What the LLM saw" refresh in the redesigned UI

**Files changed:**
- `frontend/app.js`

The UI redesign moved the page logic into `app.js`, which was written before the earlier fix, so the "What the LLM saw" panel again stopped updating after "Accept all suggestions". It kept showing "19-year-old ... from Iceland" even though the backend already sends the rewritten text. The accept handler now reloads the panel after rescoring. Checked in the browser with the test thesis: two clicks open the gate and the panel shows "a teenage sophomore majoring in social sciences from abroad". The new UI already disables the button while a request runs, so that part of the earlier fix was not needed.
