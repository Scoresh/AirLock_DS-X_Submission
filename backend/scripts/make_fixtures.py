"""Write tests/fixtures/nsse_fixture.csv: fake respondents with the NSSE column layout.

Values come from Faker with a fixed seed, never from the real data. Four groups are planted
so tests know the exact k-values:
    PLANTED_UNIQUE  1 respondent     PLANTED_HIGH    3 respondents
    PLANTED_MEDIUM  7 respondents    PLANTED_LOW    25 respondents
Run from /backend:  python scripts/make_fixtures.py
"""
import random
from pathlib import Path

import pandas as pd
from faker import Faker

OUT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "nsse_fixture.csv"
SEED = 401
N_BACKGROUND = 400

fake = Faker()
Faker.seed(SEED)
rng = random.Random(SEED)

FIELDS = [fake.unique.word().title() + " Studies" for _ in range(6)]
TRACKS = ["Theory", "Methods", "Practice", "Systems"]
MAJORS = [f"{f}: {t}" for f in FIELDS for t in TRACKS]
AFFILIATIONS = [fake.unique.color_name() + " group" for _ in range(5)]

# Planted profiles use values that never appear in the random background.
PLANTED = {
    "PLANTED_UNIQUE": (1, {"Class": "SR", "affiliation": "Planted group A", "MAJfirst": "Planted Field: Alpha",
                           "MAJsecond": "Planted Field: Beta", "MAJnum": 2, "begincol": 1}),
    "PLANTED_HIGH": (3, {"Class": "FY", "affiliation": "Planted group B", "MAJfirst": "Planted Field: Gamma",
                         "MAJsecond": "-9", "MAJnum": 1, "begincol": 0}),
    "PLANTED_MEDIUM": (7, {"Class": "SR", "affiliation": "Planted group C", "MAJfirst": "Planted Field: Delta",
                           "MAJsecond": "-9", "MAJnum": 1, "begincol": 0}),
    "PLANTED_LOW": (25, {"Class": "FY", "affiliation": "Planted group D", "MAJfirst": "Planted Field: Epsilon",
                         "MAJsecond": "-9", "MAJnum": 1, "begincol": 0}),
}


def background_row(i: int) -> dict:
    double = rng.random() < 0.15
    return {
        "ID": 100000 + i,
        "Year": rng.choice([2014, 2016, 2018, 2020, 2022, 2024]),
        "Class": rng.choice(["FY", "SR", "Other"]),
        "program": fake.lexify("???").upper(),
        "First Time First Year": rng.choice(["Y", "N"]),
        "affiliation": rng.choice(AFFILIATIONS),
        "MAJnum": 2 if double else 1,
        "MAJfirst": rng.choice(MAJORS),
        "MAJsecond": rng.choice(MAJORS) if double else "-9",
        "begincol": rng.choice([0, 0, 0, 1]),
    }


def main() -> None:
    rows = [background_row(i) for i in range(N_BACKGROUND)]
    for name, (count, profile) in PLANTED.items():
        for j in range(count):
            rows.append({"ID": 900000 + len(rows), "Year": 2024, "program": "TST",
                         "First Time First Year": "Y" if profile["Class"] == "FY" else "N", **profile})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"wrote {OUT} ({len(rows)} fake respondents)")


if __name__ == "__main__":
    main()
