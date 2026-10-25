"""CSV mode on the Faker fixture: tokens, generalization, risk report and the exact round trip."""
import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import csv_mode, scrub
from app.main import app


@pytest.fixture
def raw(fixture_population):
    return fixture_population.read_bytes()


@pytest.fixture(autouse=True)
def _cleanup_keys():
    before = set(scrub.KEYS_DIR.glob("*.json"))
    yield
    for path in set(scrub.KEYS_DIR.glob("*.json")) - before:
        path.unlink()


def test_round_trip_restores_the_exact_table(raw):
    original = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False)
    scrubbed, _ = csv_mode.scrub_table(raw, "rt")
    restored = csv_mode.restore_table(scrubbed, csv_mode.load_key("rt"))
    pd.testing.assert_frame_equal(restored, original)


def test_ids_are_tokens_and_none_remain(raw):
    original = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False)
    scrubbed, report = csv_mode.scrub_table(raw, "ids")
    assert scrubbed["ID"].str.fullmatch(r"\[ID_\d{5}\]").all()
    assert not set(original["ID"]) & set(scrubbed["ID"])
    assert {"name": "ID", "role": "direct identifier", "rule": None} in report["columns"]


def test_majors_become_fields_and_codes_are_removed(raw):
    scrubbed, _ = csv_mode.scrub_table(raw, "maj")
    majors = scrubbed["MAJfirst"][scrubbed["MAJfirst"] != ""]
    assert not majors.str.contains(":").any()


def test_rare_categories_become_other(raw, monkeypatch):
    monkeypatch.setitem(csv_mode.RULES["generalize"], "affiliation", {"rule": "rare_to_other", "min_count": 30})
    scrubbed, _ = csv_mode.scrub_table(raw, "rare")
    counts = scrubbed["affiliation"].value_counts()
    assert "Other" in counts and (counts.drop("Other") >= 30).all()


def test_generalization_does_not_increase_risk(raw):
    _, report = csv_mode.scrub_table(raw, "risk")
    before, after = report["k_before"]["bins"], report["k_after"]["bins"]
    assert after["k = 1"] <= before["k = 1"]
    assert sum(after.values()) == sum(before.values()) == report["rows"]


def test_endpoint_returns_report_and_scrubbed_download(raw):
    client = TestClient(app)
    r = client.post("/csv/scrub", files={"file": ("table.csv", raw, "text/csv")})
    assert r.status_code == 200
    body = r.json()
    download = client.get(body["download"])
    assert download.status_code == 200 and download.headers["content-type"].startswith("text/csv")
    original_ids = set(pd.read_csv(io.BytesIO(raw), dtype=str)["ID"])
    assert not any(i in download.text for i in original_ids)
