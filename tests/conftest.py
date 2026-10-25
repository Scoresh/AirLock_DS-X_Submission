"""Point the risk engine at the Faker fixture instead of the real data for every test."""
from pathlib import Path

import pytest

from app import risk, scrub

FIXTURE = Path(__file__).parent / "fixtures" / "nsse_fixture.csv"


def _clear_caches() -> None:
    risk.population.cache_clear()
    risk.vocabulary.cache_clear()
    scrub._not_names.cache_clear()


@pytest.fixture(autouse=True)
def fixture_population(monkeypatch):
    monkeypatch.setattr(risk, "DATA_FILE", FIXTURE)
    _clear_caches()
    yield FIXTURE
    _clear_caches()
