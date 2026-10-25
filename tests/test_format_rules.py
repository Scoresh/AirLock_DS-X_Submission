"""Every planted format error in the demo thesis is found, and nothing else is flagged."""
from pathlib import Path

import pytest

from app import format_rules
from app.parse import parse_pdf

DEMO = Path(__file__).resolve().parents[1] / "samples" / "demo-thesis.pdf"
PLANTED = {"required-sections": [2], "roman-bottom-center": [3], "left-margin": [7],
           "number-position": [8], "font-size": [12], "font-consistency": [12]}


@pytest.fixture(scope="module")
def results():
    return {row["id"]: row for row in format_rules.checklist(parse_pdf(DEMO.read_bytes(), "t"))}


def test_twelve_rules_with_guide_pages(results):
    assert len(results) == 12
    assert all(4 <= row["guide_page"] <= 7 for row in results.values())


@pytest.mark.parametrize("rule_id", sorted(PLANTED))
def test_planted_error_is_found(results, rule_id):
    assert results[rule_id]["pages"] == PLANTED[rule_id]


def test_no_false_alarms(results):
    flagged = {rule_id for rule_id, row in results.items() if not row["passed"]}
    assert flagged == set(PLANTED)


def test_findings_cite_the_guide():
    findings = format_rules.run_all(parse_pdf(DEMO.read_bytes(), "t"))
    assert findings and all(f.criterion.startswith("BU guide p.") and f.source == "rule" for f in findings)
