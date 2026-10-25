# Code review cleanup: fix broken frontend and align the LLM paths

**Files changed:**
- `frontend/app.js`
- `backend/app/review.py`
- `rubric_parsing/convert.py` (deleted)

Reviewed the whole codebase and fixed the things that pointed the wrong way or were dead weight. The biggest problem was an unresolved Git merge conflict left in `frontend/app.js` (`<<<<<<< / ======= / >>>>>>>`), which was invalid JavaScript that would have stopped the entire page from running; resolved it by dropping the orphaned "Open sample document" handler, since the `#open-sample` button had already been removed from `index.html`. Reworded three stale intake error hints in `app.js` that still told users to "open the sample document," an action that no longer exists. In `backend/app/review.py`, removed `temperature: 0` from the review payload (newer models reject it, matching the earlier fix in `rubric_parsing/llm.py`) and made `_send` route Anthropic Claude through its native `/v1/messages` API when `LLM_API_STYLE`/host indicates Anthropic, so `/review` now works for the same providers the Settings page offers (previously only `/rubric-check` did). Deleted `rubric_parsing/convert.py`, an elaborate 11 KB document converter that was superseded by `extract.py` and imported nowhere. Verified with `py_compile` on all backend sources, a clean conflict-marker sweep, `from app.main import app`, and the full test suite: 43 passed.
