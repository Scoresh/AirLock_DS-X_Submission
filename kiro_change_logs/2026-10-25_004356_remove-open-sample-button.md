# Remove "Open sample document" button from the home/intake page

**Files changed:**
- `frontend/index.html`
- `frontend/app.js`

Removed the "Open sample document" button (`#open-sample`) from the intake form in `index.html`. In `app.js`, deleted its click handler that fetched `/sample` and started a check, and removed the two `$("open-sample").disabled = …` references — one in `setIntakeBusy()` and one in the setup-incomplete startup branch — which would have thrown once the element was gone. The setup-incomplete branch now disables the `#start` button instead and still sets `state.setupBlocked`, so checks remain blocked when the server is not ready. The `/sample` backend endpoint and the `state.isSample` flag were left in place as harmless unused metadata. Verified by review and a reference search (no remaining `open-sample` references); Node is not installed here, so no syntax checker was run.
