"""k-values, risk levels, generalization and the privacy gate on the Faker fixture."""
import base64
import gzip

import pandas as pd
import pytest

from app import risk
from app.schemas import AcceptedFix, Evidence, Participant, ScrubbedPage, ScrubResult

UNIQUE = {"Class": "Senior", "affiliation": "Planted group A", "MAJfirst": "Planted Field: Alpha",
          "MAJsecond": "Planted Field: Beta", "begincol": "Started at another college"}
HIGH = {"Class": "First-year", "affiliation": "Planted group B", "MAJfirst": "Planted Field: Gamma"}
MEDIUM = {"Class": "Senior", "affiliation": "Planted group C", "MAJfirst": "Planted Field: Delta"}
LOW = {"Class": "First-year", "affiliation": "Planted group D", "MAJfirst": "Planted Field: Epsilon"}


@pytest.mark.parametrize("profile, expected", [(UNIQUE, 1), (HIGH, 3), (MEDIUM, 7), (LOW, 25)])
def test_k_counts_planted_groups(profile, expected):
    assert risk.k_value(profile) == expected


@pytest.mark.parametrize("k, level", [(0, "high"), (1, "high"), (4, "high"), (5, "medium"),
                                      (19, "medium"), (20, "low"), (500, "low")])
def test_risk_level_thresholds(k, level):
    assert risk.risk_level(k) == level


def test_coarsen_follows_config_ladder():
    assert risk.coarsen("MAJfirst", "Planted Field: Alpha") == ("MAJfirstfield", "Planted Field")
    assert risk.coarsen("MAJsecondfield", "Planted Field") == ("MAJnum", "Double major")
    assert risk.coarsen("affiliation", "Planted group A") == (risk.OMIT, None)


def test_generalizing_raises_k():
    profile = dict(UNIQUE)
    before = risk.k_value(profile)
    field, value = risk.coarsen("affiliation", profile.pop("affiliation"))
    assert field == risk.OMIT
    assert risk.k_value(profile) >= before


def _doc(*participants: tuple[str, dict]) -> ScrubResult:
    return ScrubResult(
        doc_id="t",
        scrubbed_pages=[ScrubbedPage(page=1, text="test")],
        direct_identifiers=[],
        participants=[Participant(id=pid, pages=[1], attributes=attrs, evidence=[Evidence(page=1, quote="q")])
                      for pid, attrs in participants],
    )


def test_gate_blocks_while_any_participant_has_k_below_5():
    doc = _doc(("PARTICIPANT_01", HIGH), ("PARTICIPANT_02", LOW))
    result = risk.score(doc, [])
    assert [p.risk for p in result.participants] == ["high", "low"]
    assert result.gate_open is False


def test_gate_opens_with_only_medium_and_low():
    result = risk.score(_doc(("PARTICIPANT_01", MEDIUM), ("PARTICIPANT_02", LOW)), [])
    assert result.gate_open is True


def test_accepted_fixes_are_applied_and_rescored():
    doc = _doc(("PARTICIPANT_01", HIGH))
    fixes = [AcceptedFix(participant_id="PARTICIPANT_01", field="affiliation")]
    after = risk.score(doc, fixes).participants[0]
    assert "affiliation" not in after.attributes
    assert after.k >= 3


def test_compressed_aggregated_file_gives_same_k(tmp_path, monkeypatch, fixture_population):
    cols = ["Class", "affiliation", "MAJfirst", "MAJsecond", "MAJnum", "begincol"]
    raw = pd.read_csv(fixture_population, usecols=cols, dtype=str, keep_default_na=False)
    agg = raw.groupby(cols).size().reset_index(name="n").to_csv(index=False).encode()
    small = tmp_path / "small.txt"
    small.write_bytes(base64.b64encode(gzip.compress(agg)))
    expected = [risk.k_value(p) for p in (UNIQUE, HIGH, MEDIUM, LOW)]
    monkeypatch.setattr(risk, "DATA_FILE", small)
    risk.population.cache_clear()
    assert [risk.k_value(p) for p in (UNIQUE, HIGH, MEDIUM, LOW)] == expected
