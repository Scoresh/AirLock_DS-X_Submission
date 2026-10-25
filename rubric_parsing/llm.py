"""Configurable LLM client for rubric parsing.

Matches the backend's convention (see backend/app/review.py): the endpoint is
read from environment variables. Two request styles are supported:

  * "openai"    OpenAI-compatible /chat/completions (OpenAI, Google Gemini's
                OpenAI endpoint, local Ollama, and most hosted models).
  * "anthropic" Anthropic's native Messages API (/v1/messages). Anthropic does
                NOT use the OpenAI chat shape: it needs an `anthropic-version`
                header, a required `max_tokens`, a top-level `system` string, and
                returns text in content[0].text. Auth uses `Authorization: Bearer`
                (the current primary header; `x-api-key` is a legacy fallback).

    LLM_BASE_URL   e.g. https://api.openai.com/v1
                        https://generativelanguage.googleapis.com/v1beta/openai
                        https://api.anthropic.com/v1
                        http://localhost:11434/v1
    LLM_MODEL      e.g. gpt-4o-mini / gemini-1.5-flash / claude-5-5-sonnet
    LLM_API_KEY    the provider API key (may be empty for a local server)
    LLM_API_STYLE  "openai" (default) or "anthropic". If unset, the style is
                   auto-detected from the base URL (api.anthropic.com -> anthropic).

The LLM is a configurable setting, never a hard dependency. Uses only the
standard library (urllib) so this folder adds no new packages.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

ANTHROPIC_VERSION = "2026-10-21"
ANTHROPIC_MAX_TOKENS = 8192


class LLMConfigError(RuntimeError):
    """Raised when required LLM settings are missing."""


class LLMRequestError(RuntimeError):
    """Raised when the LLM call fails or returns an unusable response."""


def detect_style(base_url: str) -> str:
    """Infer the request style from the endpoint host."""
    return "anthropic" if "api.anthropic.com" in base_url else "openai"


@dataclass
class LLMConfig:
    base_url: str
    model: str
    api_key: str = ""
    timeout: int = 90
    api_style: str = "openai"  # "openai" | "anthropic"

    @classmethod
    def from_env(cls) -> "LLMConfig":
        base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
        model = os.getenv("LLM_MODEL", "").strip()
        api_key = os.getenv("LLM_API_KEY", "").strip()
        style = os.getenv("LLM_API_STYLE", "").strip().lower()
        if not base_url:
            raise LLMConfigError("LLM_BASE_URL is not set")
        if not model:
            raise LLMConfigError("LLM_MODEL is not set")
        if style not in ("openai", "anthropic"):
            style = detect_style(base_url)
        return cls(base_url=base_url, model=model, api_key=api_key, api_style=style)


def _request(url: str, payload: dict, headers: dict, timeout: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMRequestError(f"LLM returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMRequestError(f"could not reach LLM at {url}: {exc.reason}") from exc


def _chat_openai(config: LLMConfig, system_prompt: str, user_prompt: str) -> str:
    """OpenAI-compatible /chat/completions (OpenAI, Gemini's OpenAI endpoint, Ollama)."""
    url = f"{config.base_url}/chat/completions"
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    body = _request(url, payload, headers, config.timeout)
    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMRequestError(f"unexpected LLM response shape: {body!r}") from exc


def _chat_anthropic(config: LLMConfig, system_prompt: str, user_prompt: str) -> str:
    """Anthropic native Messages API (/v1/messages).

    Differs from OpenAI: an anthropic-version header, a required max_tokens, the
    system prompt as a top-level field, and the reply text in content[0].text.
    Auth is `Authorization: Bearer <key>` (Anthropic's current primary header;
    `x-api-key` remains a documented legacy fallback). There is no response_format,
    so JSON is requested in the prompt (callers already tolerate fenced / stray-prose JSON).
    """
    url = f"{config.base_url}/messages"
    payload = {
        "model": config.model,
        "max_tokens": ANTHROPIC_MAX_TOKENS,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": ANTHROPIC_VERSION,
    }
    if config.api_key:
        # Anthropic's current docs make `Authorization: Bearer` the primary auth
        # header (API key or OAuth token); `x-api-key` is still accepted as a
        # documented legacy fallback. We send Bearer to match the current docs.
        headers["x-api-key"] = config.api_key

    body = _request(url, payload, headers, config.timeout)
    try:
        blocks = body["content"]
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        if not text:
            # A refusal (stop_reason / stop_details.type == "refusal") returns no
            # usable text. Surface Anthropic's own explanation instead of the raw body.
            detail = body.get("stop_details") or {}
            if body.get("stop_reason") == "refusal" or detail.get("type") == "refusal":
                why = detail.get("explanation") or "the request was declined by the model"
                raise LLMRequestError(f"Anthropic declined the request: {why}")
            raise LLMRequestError(f"Anthropic returned no text content: {body!r}")
        return text
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMRequestError(f"unexpected Anthropic response shape: {body!r}") from exc


def chat_json(
    config: LLMConfig,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Send one chat request and return the raw assistant message text.

    Routes to the Anthropic Messages API or the OpenAI-compatible chat API based
    on config.api_style. Callers parse/validate the returned text as JSON.
    """
    if config.api_style == "anthropic":
        return _chat_anthropic(config, system_prompt, user_prompt)
    return _chat_openai(config, system_prompt, user_prompt)
