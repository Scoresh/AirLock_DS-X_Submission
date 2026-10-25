# Hide empty model-review notice box in Review tab

**Files changed:**
- `frontend/app.js`

After removing the `not_configured` model-review text, the `<div class="notice notice--info">` still rendered as an empty box in the right-hand Review findings tab. `reviewFindingsHtml()` now stores `modelNote()` in a `note` variable and only emits the notice div when `note` is non-empty. For the `not_implemented` and `sent` states the note still shows as before; for `not_configured` the box is omitted entirely.
