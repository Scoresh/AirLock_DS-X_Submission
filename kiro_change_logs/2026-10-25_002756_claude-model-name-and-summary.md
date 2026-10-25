# Correct the Claude model name and the project summary

**Files changed:**
- `backend/app/settings.py`, `SUMMARY.md`

The Claude preset's default model was "claude-5-5-sonnet", which is not a valid model ID; it is now "claude-sonnet-5-5" and is listed in the dropdown next to "claude-haiku-5-5". SUMMARY.md said PDF parsing and review still returned example data; it now says every step is real and that only local checks run without a configured model. Checked with a placeholder key: the OpenAI and Claude presets both reach their endpoints and get HTTP 401 (invalid key), not 404, so the URLs and request format are right; /review and /rubric-check report "failed" with the reason and still return the local format findings. A real key is still needed for a full end-to-end check. 43 tests pass.
