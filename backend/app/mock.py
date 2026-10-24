"""Load the example JSON in /mock so every stub works before the real code exists."""
import json
from pathlib import Path

MOCK_DIR = Path(__file__).resolve().parents[2] / "mock"


def load(name: str) -> dict:
    return json.loads((MOCK_DIR / f"{name}.json").read_text())
