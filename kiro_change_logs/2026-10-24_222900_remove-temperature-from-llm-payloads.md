# Remove temperature from both LLM request payloads

**Files changed:**
- `rubric_parsing/llm.py`

Removed the `"temperature": 0` field from both request payloads in `rubric_parsing/llm.py`: the OpenAI-compatible path (`_chat_openai`, used for OpenAI and Gemini) and the native Anthropic path (`_chat_anthropic`). Newer models reject an explicit `temperature: 0` (e.g. some only allow the default), which was causing an HTTP 400; dropping the field lets each provider use its own default and keeps all current models working. Determinism for our JSON-grading use case comes primarily from the prompt and the OpenAI `response_format: json_object` mode, not from `temperature`, so behavior is effectively unchanged for the models that did accept it. Verified against localhost stubs that the OpenAI payload now contains only `model`, `messages`, and `response_format`, and the Anthropic payload only `model`, `max_tokens`, `system`, and `messages`, with no `temperature` in either and all other required fields intact.
