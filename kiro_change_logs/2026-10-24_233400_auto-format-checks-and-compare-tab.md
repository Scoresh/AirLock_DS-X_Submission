# Auto-run local format checks; make Compare a real tab

**Files changed:**
- `backend/app/schemas.py`
- `backend/app/main.py`
- `frontend/index.html`
- `frontend/app.js`
- `frontend/styles.css`

Local format checks now run automatically with no button: once the privacy gate is open the frontend calls `/review` with a new `format_only` flag, so margins/page-number/font/required-page rules run locally and nothing crosses the network. Added `format_only: bool = False` to `ReviewRequest` and honored it in the `/review` route (returns only the local format findings when set). The gate's old "Run local format checks" / "Check the prepared text" buttons were removed; the explicit "Send prepared text for model review" button is kept only when a model is configured, since sending to a model must stay user-initiated. Promoted Compare from a toolbar toggle to a real tab (`#tab-compare`) alongside Privacy check and Rubric: `selectTab` now treats it as a reader-driven, full-width view via a new `data-view` attribute ("reader" vs "inspector"), and the CSS makes the chosen column span the whole workspace. Wired `maybeAutoFormatCheck()` into `enterWorkspace` and `applyFixes` (invalidating the cached findings after fixes change pages) and tracked completion with `state.formatCheckedFor`. Cleaned up the removed toggle button, its listener, the dead `data-action="compare"` branch, and the unused `.reader__bar` styles. Verified the backend compiles and that `ReviewRequest.format_only` defaults to False and accepts True.
