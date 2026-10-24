"""Configurable LLM client for rubric parsing.

Matches the backend's convention (see backend/app/review.py): the endpoint is
read from environment variables and speaks the OpenAI-compatible chat API, so a
lab-approved hosted model OR a local Ollama server both work with no code change.

    LLM_BASE_URL   e.g. https://api.openai.com/v1  or  http://localhost:11434/v1
    LLM_MODEL      e.g. gpt-4o-mini  or  llama3.1
    LLM_API_KEY    bearer token; may be empty/"ollama" for a local server

The LLM is a configurable setting, never a hard dependency. Uses only the
standard library (urllib) so this folder adds no new packages.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


class LLMConfigError(RuntimeError):
    """Raised when required LLM settings are missing."""


class LLMRequestError(RuntimeError):
    """Raised when the LLM call fails or returns an unusable response."""


@dataclass
class LLMConfig:
    base_url: str
    model: str
    api_key: str = ""
    timeout: int = 90

    @classmethod
    def from_env(cls) -> "LLMConfig":
        base_url = os.getenv("LLM_BASE_URL", "").strip()
        model = os.getenv("LLM_MODEL", "").strip()
        api_key = os.getenv("LLM_API_KEY", "").strip()
        if not base_url:
            raise LLMConfigError("LLM_BASE_URL is not set")
        if not model:
            raise LLMConfigError("LLM_MODEL is not set")
        return cls(base_url=base_url.rstrip("/"), model=model, api_key=api_key)


def chat_json(
    config: LLMConfig,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Send one chat completion and return the raw assistant message content.

    Requests JSON output via response_format; callers parse/validate the result.
    """
    url = f"{config.base_url}/chat/completions"
    payload = {
        "model": config.model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=config.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMRequestError(f"LLM returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMRequestError(f"could not reach LLM at {url}: {exc.reason}") from exc

    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMRequestError(f"unexpected LLM response shape: {body!r}") from exc
