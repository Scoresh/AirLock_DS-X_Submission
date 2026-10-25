# Remove "Load rubric JSON" button from rubric panel

**Files changed:**
- `frontend/app.js`

Removed the "Load rubric JSON" button and its hidden `#rubric-file` file input from the rubric load controls in `renderRubricPanel()`, so only the "Parse rubric file" action remains. Also removed the now-dead `#rubric-file` branch from the delegated `change` handler on `#panel-rubric`. The `loadRubricFromText` and `normalizeRubric` helper functions are now unused but were left in place in case a JSON-load path returns. The intro and empty-state copy still mention loading saved JSON and were left unchanged pending confirmation. Node is not installed in this environment, so the change was verified by review rather than a syntax checker.
