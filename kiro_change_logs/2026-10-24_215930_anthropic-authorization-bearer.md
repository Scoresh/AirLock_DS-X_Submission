# Switch Anthropic auth to Authorization: Bearer (primary header)

**Files changed:**
- `rubric_parsing/llm.py`

Fetched Anthropic's current API docs (overview + versioning pages) and found that `Authorization: Bearer <token>` is now the primary documented auth header for the Messages API, while `x-api-key` is relabeled a still-supported "legacy fallback"; the pinned `anthropic-version: 2023-06-01` remains a valid, listed version. Updated `_chat_anthropic` in `rubric_parsing/llm.py` to send `Authorization: Bearer <api_key>` instead of `x-api-key`, and refreshed the module and function docstrings to describe the new auth header. The request path (`/v1/messages`), `anthropic-version` header, required `max_tokens`, top-level `system` field, and `content[].text` response parsing are unchanged. Verified against a localhost stub server that the Anthropic request now sends `Authorization: Bearer <key>`, sends no `x-api-key`, keeps `anthropic-version: 2023-06-01` and `content-type: application/json`, includes `max_tokens` and a top-level `system`, and still parses the reply from `content[].text`. This is a docs-alignment change; the previous `x-api-key` form would also still work.
