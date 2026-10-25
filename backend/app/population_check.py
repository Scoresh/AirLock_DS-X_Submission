"""Trusted local Researcher bridge adapter. No browser-supplied counts are accepted."""
import hashlib
import json
import os
import logging
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class PopulationError(RuntimeError):
    pass


LOG = logging.getLogger("uvicorn.error.population_check")
QUERY_TIMEOUT_SECONDS = 55  # Same per-comparison deadline as jiff/party.js.
BUSY_WAIT_SECONDS = 90


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


def call(path: str, payload=None, timeout: int = 65) -> dict:
    url = os.getenv("JIFF_BRIDGE_URL", "http://127.0.0.1:9112").rstrip("/")
    parsed = urlparse(url)
    token = os.getenv("JIFF_BRIDGE_TOKEN", "")
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1") or parsed.username or parsed.password or len(token) < 32:
        raise PopulationError("Configure a localhost JIFF bridge and JIFF_BRIDGE_TOKEN (32+ characters)")
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(url + path, data=data, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    # A busy reply guarantees that the bridge did not start this batch. Wait only
    # for those replies; never replay an interrupted computation automatically.
    busy_deadline = time.monotonic() + BUSY_WAIT_SECONDS
    reported_busy = False
    while True:
        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.load(response)
            if not isinstance(result, dict):
                raise ValueError("Expected bridge object")
            return result
        except HTTPError as exc:
            status = exc.code
            exc.close()
            if path == "/batch" and status == 409:
                if not reported_busy:
                    LOG.info("JIFF bridge busy; waiting for the active batch to finish")
                    reported_busy = True
                remaining = busy_deadline - time.monotonic()
                if remaining > 0:
                    time.sleep(min(1, remaining))
                    continue
                raise PopulationError("Another document is still being checked. Please try again shortly. Review remains paused.") from exc
            LOG.warning("JIFF bridge request failed: endpoint=%s http_status=%s", path, status)
            raise PopulationError("The private comparison could not finish. Please try again shortly. Review remains paused.") from exc
        except (OSError, ValueError) as exc:
            LOG.warning("JIFF bridge request failed: endpoint=%s error_type=%s", path, type(exc).__name__)
            raise PopulationError("The private comparison lost its connection or took too long. Please try again. Review remains paused.") from exc


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
    # The bridge runs one bounded MPC session per candidate, in sequence. A
    # single 65-second HTTP budget cannot cover a legitimate multi-person batch.
    timeout = QUERY_TIMEOUT_SECONDS * len(profiles) + 15
    started = time.monotonic()
    LOG.info("JIFF batch started: comparisons=%d budget_seconds=%d", len(profiles), timeout)
    result = call("/batch", {"profiles": profiles, "binding": binding, "fingerprint": digest(public)}, timeout=timeout)
    counts = result.get("counts")
    if result.get("binding") != binding or result.get("fingerprint") != digest(public) or result.get("population_id") != public["population_id"] or result.get("version") != public["version"] or not isinstance(counts, list) or len(counts) != len(profiles) or any(type(k) is not int or not 0 <= k <= public["row_count"] for k in counts):
        raise PopulationError("Invalid or stale JIFF response; review stays blocked")
    LOG.info("JIFF batch completed: comparisons=%d elapsed_seconds=%.1f", len(profiles), time.monotonic() - started)
    return counts


def verify_manifest(public: dict) -> None:
    current = call("/manifest")
    if current.get("fingerprint") != digest(public):
        raise PopulationError("JIFF population version changed; run the privacy check again")


def availability() -> dict:
    """Distinguish missing configuration from a busy/unreachable bridge."""
    try:
        public = manifest()
        if len(os.getenv("JIFF_BRIDGE_TOKEN", "")) < 32:
            raise PopulationError("Missing bridge configuration")
    except PopulationError:
        return {"available": False, "configured": False, "message": "JIFF is not enabled on this deployment. Use the local synthetic reference, or ask the service owner to start the JIFF demo services."}
    try:
        live = call("/manifest", timeout=3)
        if live.get("fingerprint") != digest(public):
            raise PopulationError("Manifest mismatch")
        return {"available": True, "configured": True, "population_id": public["population_id"],
                "population_version": str(public["version"])}
    except PopulationError:
        return {"available": False, "configured": True, "message": "JIFF is configured but temporarily unavailable. A count may be running. Wait briefly and choose Check availability again; review stays blocked until a fresh count succeeds."}
