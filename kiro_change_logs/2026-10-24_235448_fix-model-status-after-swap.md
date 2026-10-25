# Fix masthead MODEL status staying stuck after swapping models

**Files changed:**
- `frontend/app.js`

The masthead MODEL status line stayed on "Not configured · nothing was sent" even after the user configured or swapped in a model. The cause was a branch in `renderModelStatus()` that returned that hardcoded string whenever a prior `state.review` existed, short-circuiting before the `m.configured` check and ignoring the freshly refreshed `state.model`. Removed that stale-review branch so the logic falls through to `m.configured`, which shows the current model name and endpoint ("… · nothing sent yet") or "Not configured · nothing will be sent" when cleared. The settings save/clear flow already calls `refreshModelStatus()` and `renderAll()`, so the line now updates immediately on a model swap. No other code referenced the removed phrase. Node is not installed here, so the change was verified by review and by tracing the save flow rather than a syntax checker.
