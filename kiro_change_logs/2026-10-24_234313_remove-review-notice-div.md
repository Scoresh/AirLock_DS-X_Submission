# Remove model-review notice div from Review tab entirely

**Files changed:**
- `frontend/app.js`

The user wanted the model-review notice div never rendered. `reviewFindingsHtml()` no longer emits the `<div class="notice notice--info">` block in any state (`not_configured`, `not_implemented`, or `sent`). The Review findings section now shows only the label and the findings summary. The `modelNote()` function is now unused but was left in place pending confirmation.
