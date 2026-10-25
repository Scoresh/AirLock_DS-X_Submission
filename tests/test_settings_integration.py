"""The settings page (settings.py) drives both model consumers: /review and /rubric-check.

Network calls are replaced: review._send and rubric_check.chat_json are recorders, so nothing
leaves the machine. People in the uploaded text are fictional.
"""
import json
import os

import pytest
from fastapi.testclient import TestClient

from app import review, rubric_check, scrub
from app.main import app

CONTACT = "Interview scheduling was handled by Danny Sab (ds1612@usnh.edu)."
LOW_RISK = "Participant 5 is a first-year majoring in Planted Field: Epsilon who identifies as Planted group D."
RUBRIC = {"rubric": [{"parameter_title": "Acknowledges helpers", "description": "Thanks the people who helped"}]}


@pytest.fixture
def client(monkeypatch):
    for var in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_API_STYLE"):
        monkeypatch.delenv(var, raising=False)
    c = TestClient(app)
    yield c
    c.delete("/settings")


@pytest.fixture(autouse=True)
def _cleanup_keys():
    before = set(scrub.KEYS_DIR.glob("*.json"))
    yield
    for path in set(scrub.KEYS_DIR.glob("*.json")) - before:
        path.unlink()


def gate_open_doc(client) -> str:
    doc = client.post("/parse", files={"file": ("d.txt", f"{LOW_RISK}\n\n{CONTACT}".encode(), "text/plain")}).json()["doc_id"]
    client.post(f"/scrub/{doc}")
    assert client.post("/score", json={"doc_id": doc, "accepted": []}).json()["gate_open"] is True
    return doc


def use_local_model(client):
    r = client.put("/settings", json={"provider": "custom", "model": "test-model", "base_url": "http://model.invalid/v1"})
    assert r.status_code == 200, r.text


def test_providers_list_has_no_secrets(client):
    body = client.get("/settings/providers").json()
    assert {p["id"] if "id" in p else p.get("key") for p in body["providers"]} or body["providers"]
    assert "api_key" not in json.dumps(body).lower().replace("has_api_key", "")


def test_saved_settings_reach_status_and_review(client, monkeypatch):
    sent = []
    monkeypatch.setattr(review, "_send", lambda base, key, payload: sent.append((base, payload)) or '{"findings": []}')
    use_local_model(client)
    assert client.get("/status").json()["model"]["model"] == "test-model"
    doc = gate_open_doc(client)
    r = client.post("/review", json={"doc_id": doc}).json()
    assert r["model_review"] == "sent" and r["model"] == "test-model"
    assert sent and sent[0][0] == "http://model.invalid/v1"
    assert "Maya Lindqvist" not in json.dumps(sent[0][1])


def test_format_only_review_sends_nothing(client, monkeypatch):
    calls = []
    monkeypatch.setattr(review, "_send", lambda *a: calls.append(a))
    use_local_model(client)
    doc = gate_open_doc(client)
    r = client.post("/review", json={"doc_id": doc, "format_only": True}).json()
    assert r["model_review"] == "not_configured" and calls == []


def test_rubric_check_restores_tokens_in_comments(client, monkeypatch):
    seen = []

    def fake_chat(cfg, system, user):
        seen.append(user)
        return json.dumps({"results": [{"parameter_title": "Acknowledges helpers", "fulfilled": True,
                                        "comment": "Thanks [PERSON_01] for scheduling."}]})

    monkeypatch.setattr(rubric_check, "chat_json", fake_chat)
    use_local_model(client)
    doc = gate_open_doc(client)
    r = client.post(f"/rubric-check/{doc}", json=RUBRIC).json()
    assert r["model_review"] == "sent"
    assert "Maya Lindqvist" not in seen[0], "the original name must not reach the model"
    assert r["results"][0]["comment"] == "Thanks Maya Lindqvist for scheduling."


def test_rubric_check_reports_a_failed_request(client, monkeypatch):
    def failing(cfg, system, user):
        raise rubric_check.LLMRequestError("could not reach LLM")

    monkeypatch.setattr(rubric_check, "chat_json", failing)
    use_local_model(client)
    doc = gate_open_doc(client)
    r = client.post(f"/rubric-check/{doc}", json=RUBRIC)
    assert r.status_code == 200
    assert r.json()["model_review"] == "failed" and "could not reach LLM" in r.json()["model_error"]


def test_clearing_settings_stops_all_sending(client, monkeypatch):
    calls = []
    monkeypatch.setattr(review, "_send", lambda *a: calls.append(a))
    use_local_model(client)
    client.delete("/settings")
    assert not os.getenv("LLM_BASE_URL")
    doc = gate_open_doc(client)
    assert client.post("/review", json={"doc_id": doc}).json()["model_review"] == "not_configured"
    assert calls == []
