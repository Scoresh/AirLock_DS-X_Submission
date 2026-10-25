"""The privacy gate is enforced in the backend, and no direct identifier reaches the model request.

The network call (review._send) is replaced by a recorder, so these tests see exactly what
would leave the machine. Documents are uploaded as text; the people in them are fictional and
the participant details use the planted values of the Faker fixture.
"""
import json
import re

import pytest
from fastapi.testclient import TestClient

from app import review, scrub
from app.main import app

IDENTIFIERS = {
    "Maya Lindqvist": "PERSON", "mlindq@bu.edu": "EMAIL", "617-555-0142": "PHONE", "U12345678": "STUDENT_ID",
}
CONTACT = ("Interview scheduling was handled by Maya Lindqvist (mlindq@bu.edu, 617-555-0142, U12345678). "
           "Maya also transcribed the recordings.")
HIGH_RISK = ("Participant 3, a senior who identifies as Planted group A, is majoring in Planted Field: Alpha "
             "with a second major in Planted Field: Beta and transferred from another college.")
LOW_RISK = "Participant 5 is a first-year majoring in Planted Field: Epsilon who identifies as Planted group D."


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def model(monkeypatch):
    """Configure a model and record every outgoing request instead of sending it."""
    sent: list[dict] = []
    monkeypatch.setenv("LLM_BASE_URL", "http://model.invalid/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")

    def fake_send(base_url, api_key, payload):
        sent.append(payload)
        tokens = sorted(set(re.findall(r"\[[A-Z_]+_\d+\]", json.dumps(payload))))
        return json.dumps({"findings": [{"page": 1, "quote": None, "criterion": "Participants are described in aggregate",
                                         "issue": f"Consider removing {' '.join(tokens)} from the appendix",
                                         "severity": "warning"}]})

    monkeypatch.setattr(review, "_send", fake_send)
    return sent


def upload(client, text: str) -> str:
    r = client.post("/parse", files={"file": ("doc.txt", text.encode(), "text/plain")})
    assert r.status_code == 200, r.text
    doc = r.json()["doc_id"]
    assert client.post(f"/scrub/{doc}").status_code == 200
    return doc


def test_review_is_refused_while_the_gate_is_closed(client, model):
    doc = upload(client, f"{HIGH_RISK}\n\n{CONTACT}")
    score = client.post("/score", json={"doc_id": doc, "accepted": []}).json()
    assert score["gate_open"] is False
    r = client.post("/review", json={"doc_id": doc})
    assert r.status_code == 403
    assert model == [], "the model must not be contacted while the gate is closed"


def test_no_direct_identifier_reaches_the_model(client, model):
    doc = upload(client, f"{LOW_RISK}\n\n{CONTACT}")
    assert client.post("/score", json={"doc_id": doc, "accepted": []}).json()["gate_open"] is True
    r = client.post("/review", json={"doc_id": doc})
    assert r.status_code == 200 and r.json()["model_review"] == "sent"

    assert len(model) == 1
    outgoing = json.dumps(model[0])
    for value in list(IDENTIFIERS) + ["Maya", "Lindqvist"]:
        assert value not in outgoing, f"{value!r} leaked into the model request"
    assert not re.search(r"[\w.+-]+@[\w-]+\.\w+", outgoing), "an email address leaked"
    assert "[PERSON_01]" in outgoing and "[EMAIL_01]" in outgoing


def test_rewritten_details_are_what_the_model_receives(client, model):
    doc = upload(client, f"{HIGH_RISK}\n\n{CONTACT}")
    score = client.post("/score", json={"doc_id": doc, "accepted": []}).json()
    while not score["gate_open"]:
        fixes = [{"participant_id": p["id"], "field": s["field"]} for p in score["participants"] for s in p["suggestions"]]
        assert fixes, "gate closed but no suggestions left"
        score = client.post("/score", json={"doc_id": doc, "accepted": fixes}).json()
    assert client.post("/review", json={"doc_id": doc}).status_code == 200
    outgoing = json.dumps(model[0])
    assert "Planted Field: Alpha" not in outgoing and "Planted group A" not in outgoing


def test_tokens_in_model_feedback_are_restored_locally(client, model):
    doc = upload(client, f"{LOW_RISK}\n\n{CONTACT}")
    client.post("/score", json={"doc_id": doc, "accepted": []})
    findings = client.post("/review", json={"doc_id": doc}).json()["findings"]
    model_issue = next(f["issue"] for f in findings if f["source"] == "llm")
    assert "Maya Lindqvist" in model_issue and "mlindq@bu.edu" in model_issue
    assert "[PERSON_01]" not in model_issue


def test_unconfigured_model_sends_nothing(client, monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    calls = []
    monkeypatch.setattr(review, "_send", lambda *a: calls.append(a))
    doc = upload(client, f"{LOW_RISK}\n\n{CONTACT}")
    client.post("/score", json={"doc_id": doc, "accepted": []})
    assert client.post("/review", json={"doc_id": doc}).json()["model_review"] == "not_configured"
    assert calls == []


@pytest.fixture(autouse=True)
def _remove_key_files():
    """Delete only the token key files these tests create."""
    before = set(scrub.KEYS_DIR.glob("*.json"))
    yield
    for path in set(scrub.KEYS_DIR.glob("*.json")) - before:
        path.unlink()
