# Add a settings page to configure the review/rubric LLM (ChatGPT, Gemini, Claude)

**Files changed:**
- `backend/app/settings.py` (new)
- `backend/app/schemas.py`
- `backend/app/main.py`
- `frontend/index.html`
- `frontend/app.js`
- `frontend/styles.css`

Added a settings page that lets the user configure which LLM reviews prepared text and rubric checks, with presets for ChatGPT (OpenAI), Google Gemini, and Anthropic Claude plus a custom/local OpenAI-compatible option. On the backend, a new `settings.py` holds the runtime configuration and applies it to `os.environ` (LLM_BASE_URL / LLM_MODEL / LLM_API_KEY), so every existing consumer — `review.model_config`, `rubric_check`, and `rubric_parsing.llm.LLMConfig.from_env` — picks it up with no further changes; all three hosted providers are reached through the same OpenAI-compatible `/chat/completions` client by setting the right base URL and model. Added `GET /settings/providers`, `GET/PUT/DELETE /settings`, and `POST /settings/test` endpoints with `SettingsUpdate`/`SettingsState`/`SettingsTestResult` schemas; the API never returns the key (only `has_api_key`), nothing is persisted to disk, and validation enforces a key for hosted providers and a base URL for custom. On the frontend, added a "Settings" button in the masthead that opens a modal dialog with a provider dropdown, model picker (presets + "Other…"), base-URL field for custom, password API-key field (blank keeps the saved key), and Save / Test connection / Clear actions, then refreshes the masthead model status. Verified end to end with a FastAPI TestClient suite: provider list, applying each of the three providers (correct base URLs, hidden key), model-only update keeping the existing key, 400s for missing key / missing custom URL, an allowed keyless custom/local config, a successful test against a stub server, and clear; also confirmed `review` and `rubric_check` see the applied config, and `app.js` bundles cleanly via bun. No existing feature paths (scrub, risk, review, rubric) were modified beyond reading the now-settable env vars.
