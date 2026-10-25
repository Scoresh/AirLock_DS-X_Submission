# Call the configured model, restore tokens locally, and prove nothing leaks

**Files changed:**
- `backend/app/review.py`, `backend/app/main.py`, `backend/app/schemas.py` (`model_error`, status "failed"), `frontend/app.js`
- `tests/test_review_privacy.py` (new)

review.py now sends the gate-approved, scrubbed text to the configured OpenAI-compatible endpoint (LLM_BASE_URL, LLM_MODEL, LLM_API_KEY; TerrierGPT, a lab model or local Ollama), parses JSON findings with page, quote and quoted criterion, and reports "sent", "not_configured" or "failed" with the reason. Tokens in the model's feedback are swapped back to the original words locally from the key file. The request body is built in one place (build_payload) and sent through one function (_send), so the coming model dropdown only has to pass its selection. New tests replace _send with a recorder and show that the backend refuses review while the gate is closed without contacting the model, that no name, email, phone number or student ID appears in the request, that accepted rewrites are what the model receives, that tokens are restored in the feedback, and that nothing is sent without a configured model. 22 tests pass.
