# Reflect finding severity in the heatmap detail panel

**Files changed:**
- frontend/index.html

Added a display-only severity layer to the submission heatmap. Introduced
`.finding`, `.finding.error`, and `.finding.warning` CSS classes that give each
finding a colored left border (red for errors, amber for warnings). Updated the
detail-panel render inside the `$("send").onclick` handler so each finding is
wrapped in a `div.finding` keyed to `f.severity` and labeled `[error]` or
`[warning]` instead of the previous `[source]` tag. No backend, pipeline, or JSON
contract changes were made; severity was already carried end to end in the
`Finding` model and was simply not surfaced to the user before. Tile colors remain
keyed to risk-vs-rubric category and were intentionally left unchanged.
