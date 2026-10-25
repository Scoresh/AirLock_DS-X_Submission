"""Trusted local Researcher bridge adapter. No browser-supplied counts are accepted."""
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class PopulationError(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def manifest() -> dict:
    try:
        value = json.loads(Path(os.environ["JIFF_MANIFEST"]).read_text())
        if not value["population_id"] or not value["version"] or type(value["row_count"]) is not int or not 1 <= value["row_count"] <= 64:
            raise ValueError("invalid dimensions")
        schema = value["schema"]
        if not isinstance(schema, dict) or not 1 <= len(schema) <= 8:
            raise ValueError("invalid schema")
        for values in schema.values():
            if not isinstance(values, list) or not 1 <= len(values) <= 32 or any(not isinstance(v, str) or not v for v in values) or len(values) != len(set(values)):
                raise ValueError("invalid categories")
        return value
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise PopulationError("JIFF public manifest is missing or invalid; configure JIFF_MANIFEST") from exc


def call(path: str, payload=None) -> dict:
    url = os.getenv("JIFF_BRIDGE_URL", "http://127.0.0.1:9112").rstrip("/")
    parsed = urlparse(url)
    token = os.getenv("JIFF_BRIDGE_TOKEN", "")
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1") or parsed.username or parsed.password or len(token) < 32:
        raise PopulationError("Configure a localhost JIFF bridge and JIFF_BRIDGE_TOKEN (32+ characters)")
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(url + path, data=data, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=65) as response:
            result = json.load(response)
        if not isinstance(result, dict):
            raise ValueError("Expected bridge object")
        return result
    except (OSError, ValueError) as exc:
        raise PopulationError("Secure population check unavailable; review stays blocked. Check relay, registrar and bridge.") from exc


def batch(profiles: list[dict], binding: str, public: dict) -> list[int]:
    if not profiles:
        raise PopulationError("No participant profiles recognized; JIFF cannot establish a privacy count")
    if len(profiles) > 32:
        raise PopulationError("This JIFF prototype supports at most 32 distinct candidate profiles per batch")
    schema = public["schema"]
    for profile in profiles:
        for field, value in profile.items():
            if field not in schema or value not in schema[field]:
                raise PopulationError("A participant attribute is outside the approved JIFF public codebook")
    result = call("/batch", {"profiles": profiles, "binding": binding, "fingerprint": digest(public)})
    counts = result.get("counts")
    if result.get("binding") != binding or result.get("fingerprint") != digest(public) or result.get("population_id") != public["population_id"] or result.get("version") != public["version"] or not isinstance(counts, list) or len(counts) != len(profiles) or any(type(k) is not int or not 0 <= k <= public["row_count"] for k in counts):
        raise PopulationError("Invalid or stale JIFF response; review stays blocked")
    return counts


def verify_manifest(public: dict) -> None:
    current = call("/manifest")
    if current.get("fingerprint") != digest(public):
        raise PopulationError("JIFF population version changed; run the privacy check again")
