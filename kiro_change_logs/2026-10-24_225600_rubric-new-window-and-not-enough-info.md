# Rubric pop-out window + "not enough information" for image criteria

**Files changed:**
- `backend/app/schemas.py`
- `backend/app/rubric_check.py`
- `frontend/app.js`
- `frontend/styles.css`

Added a dedicated pop-out window for the rubric section so the full rubric table can be viewed without the inspector's width constraint. An "Open in new window" button in the rubric panel opens a self-contained window (inline styles) rendering the same table; it auto-refreshes on each app render (e.g. after a model check) and has a manual "Refresh from app" button. Added logic so that any rubric criterion whose title or description references visual content (image, figure, diagram, chart, screenshot, etc.) is marked "Not enough information" instead of being judged, because the prepared text carries no image content (no OCR). The backend detects these criteria deterministically via a word-list regex, skips sending them to the model, and returns them with a new `needs_more_info` flag and an explanatory comment on `RubricCriterionResult`. The frontend mirrors the same regex so the tag appears as soon as the rubric loads, and renders a new `verdict--info` pill in both the in-app table and the pop-out window. Verified the backend compiles and that image-referencing criteria are flagged while regular criteria are not.
