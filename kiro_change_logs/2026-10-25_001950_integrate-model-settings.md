# Integrate Dan's model settings and rubric check with the review pipeline

**Files changed:**
- `backend/app/main.py`, `backend/app/parse.py`, `backend/app/schemas.py` (conflict resolution and glue)
- `tests/test_settings_integration.py` (new)

Dan's settings, rubric-check and page-image work (commit "more", author Scoresh) was moved onto current main without the pre-rewrite history. Conflicts: main.py keeps every endpoint from both sides (CSV mode, status and sample; rubric-parse, rubric-check and the settings endpoints) and serves the demo thesis as the sample; parse.py keeps the paragraph merging and adds Dan's image detection. /rubric-check now behaves like /review: a failed model request returns model_review "failed" with model_error instead of a 500, and tokens in the model's comments are restored locally. New tests check that saved settings reach /status and /review, that format_only sends nothing, that rubric-check keeps names out of the request and restores them in comments, that failures are reported, and that clearing settings stops all sending. Note: rubric_check imports rubric_parsing/extract.py, which is not committed yet; with a temporary stand-in all 43 tests pass, and the branch should not be merged until that file is pushed.
