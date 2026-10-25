"""Runtime LLM settings for the review / rubric features.

Every LLM consumer in this repo reads its configuration from the environment
variables LLM_BASE_URL / LLM_MODEL / LLM_API_KEY (see rubric_parsing/llm.py and
review.py). Rather than change all of them, the settings page writes the chosen
configuration back into os.environ, so existing code picks it up with no change.

Nothing here is persisted to disk: settings live for the lifetime of the server
process, matching the project's "process in memory" stance. The API key is kept
in memory and never returned by the API.

Providers ChatGPT (OpenAI), Google Gemini, and Anthropic Claude are all reachable
through an OpenAI-compatible /chat/completions endpoint, so the single existing
client works for all three once the base URL and model are set.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

# Provider presets: the OpenAI-compatible base URL and a sensible default model.
# base_url is None for "custom", where the user supplies their own (e.g. a local
# Ollama server at http://localhost:11434/v1).
PROVIDERS: dict[str, dict] = {
    "openai": {
        "label": "ChatGPT (OpenAI)",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "key_hint": "OpenAI API key (sk-...)",
        # Two current, broadly-available GA models. Use "Other…" in the UI for
        # others (e.g. gpt-4.1) your account has access to.
        "models": ["gpt-4o", "gpt-4o-mini"],
        "api_style": "openai",
    },
    "claude": {
        "label": "Anthropic Claude",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-5-5",
        "key_hint": "Anthropic API key (sk-ant-...)",
        # Only broadly-available aliases are listed. Opus and dated model IDs are
        # account/tier-dependent and 404 on many accounts; use "Other…" in the UI
        # to enter a specific model your account has access to.
        "models": [
            "claude-sonnet-5-5",
            "claude-haiku-5-5",
        ],
        "api_style": "anthropic",
    },
    "custom": {
        "label": "Custom / local (OpenAI-compatible)",
        "base_url": None,
        "default_model": "",
        "key_hint": "Bearer token (leave blank for a local Ollama server)",
        "models": [],
        "api_style": "openai",
    },
}

# Which provider preset the current config matches (for the UI). Not persisted.
_current_provider: str | None = None


def providers_public() -> list[dict]:
    """Provider presets for the settings UI (no secrets)."""
    return [
        {
            "id": pid,
            "label": p["label"],
            "base_url": p["base_url"],
            "default_model": p["default_model"],
            "key_hint": p["key_hint"],
            "models": p["models"],
        }
        for pid, p in PROVIDERS.items()
    ]


def current() -> dict:
    """Current settings for the UI. NEVER includes the API key."""
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    return {
        "configured": bool(base_url and model),
        "provider": _current_provider,
        "base_url": base_url or None,
        "endpoint": urlparse(base_url).netloc or None,
        "model": model or None,
        "has_api_key": bool(os.getenv("LLM_API_KEY", "").strip()),
    }


def apply(
    provider: str,
    model: str,
    api_key: str | None,
    base_url: str | None = None,
) -> dict:
    """Validate and apply settings into os.environ so all consumers use them.

    For a known provider the preset base_url is used; "custom" requires base_url.
    An empty/omitted api_key for custom is allowed (local servers often need none);
    for hosted providers a key is required.
    """
    global _current_provider

    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider '{provider}'")
    preset = PROVIDERS[provider]

    resolved_base = (base_url or preset["base_url"] or "").strip().rstrip("/")
    if not resolved_base:
        raise ValueError("a base URL is required for a custom provider")
    if not urlparse(resolved_base).scheme in ("http", "https"):
        raise ValueError("base URL must start with http:// or https://")

    model = (model or preset["default_model"] or "").strip()
    if not model:
        raise ValueError("a model name is required")

    # api_key: None means "leave the existing key unchanged" (so the UI can save a
    # model change without re-entering the secret). Empty string clears it.
    if api_key is None:
        resolved_key = os.getenv("LLM_API_KEY", "")
    else:
        resolved_key = api_key.strip()

    if provider != "custom" and not resolved_key:
        raise ValueError(f"an API key is required for {preset['label']}")

    os.environ["LLM_BASE_URL"] = resolved_base
    os.environ["LLM_MODEL"] = model
    os.environ["LLM_API_KEY"] = resolved_key
    # Anthropic needs its native Messages API; everything else uses the OpenAI
    # chat shape. For custom endpoints, detect from the host.
    style = preset.get("api_style") or "openai"
    if provider == "custom":
        style = "anthropic" if "api.anthropic.com" in resolved_base else "openai"
    os.environ["LLM_API_STYLE"] = style
    _current_provider = provider

    return current()


def clear() -> dict:
    """Remove the configured model so nothing can be sent."""
    global _current_provider
    for var in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_API_STYLE"):
        os.environ.pop(var, None)
    _current_provider = None
    return current()
