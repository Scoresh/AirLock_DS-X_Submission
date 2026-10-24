"""Generate a fallback synthetic BU undergraduate population with NSSE column names.

Use this only until the organizers' NSSE-synthetic.csv is available; risk.py should
read either file the same way. Every row is one student, so WEIGHT2 = 1.0 and
k is simply the number of matching rows.

Proportions are rough approximations of a large private research university,
not real BU statistics. Say so in the UI and the pitch.

Run from /backend:
    python scripts/make_population.py            # writes ../data/population-synthetic.csv
    python scripts/make_population.py --check    # also prints k for the demo profiles
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

N_STUDENTS = 18_000
SEED = 2026
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# NSSE MAJfirstcol category -> (share of students, range of MAJfirstcode values)
MAJOR_CATEGORIES: dict[int, tuple[float, range]] = {
    1: (0.07, range(1, 16)),      # Arts and Humanities
    2: (0.11, range(16, 32)),     # Biological Sciences, Agriculture, Natural Resources
    3: (0.15, range(32, 42)),     # Physical Sciences, Mathematics, Computer Science
    4: (0.17, range(42, 53)),     # Social Sciences
    5: (0.17, range(53, 65)),     # Business
    6: (0.08, range(65, 73)),     # Communications, Media, Public Relations
    7: (0.02, range(73, 84)),     # Education
    8: (0.12, range(84, 98)),     # Engineering
    9: (0.08, range(98, 115)),    # Health Professions
    10: (0.01, range(115, 125)),  # Social Service Professions
    11: (0.02, range(125, 139)),  # All other
}
# Large majors get more weight inside their category; everything else weight 1.
POPULAR_MAJORS = {16: 6, 27: 5, 36: 12, 38: 4, 44: 8, 48: 4, 49: 5, 50: 8,
                  54: 8, 56: 6, 61: 4, 65: 5, 67: 3, 87: 5, 91: 3, 94: 4, 100: 5}

# country22 code -> (share of international students, countrycol22 region)
COUNTRIES: dict[int, tuple[float, int]] = {
    47: (0.42, 2),   # China
    109: (0.12, 2),  # India
    211: (0.08, 2),  # South Korea
    41: (0.05, 3),   # Canada
    227: (0.04, 2),  # Taiwan
    245: (0.03, 4),  # United Kingdom
    230: (0.03, 2),  # Thailand
    252: (0.03, 2),  # Vietnam
    110: (0.03, 2),  # Indonesia
    198: (0.03, 6),  # Saudi Arabia
    238: (0.03, 6),  # Turkey
    213: (0.02, 4),  # Spain
    106: (0.02, 2),  # Hong Kong
    203: (0.02, 2),  # Singapore
    209: (0.02, 1),  # South Africa
    224: (0.015, 4), # Sweden
    13: (0.015, 7),  # Australia
    9: (0.015, 5),   # Argentina
    108: (0.0015, 4),  # Iceland (very rare on purpose)
}

INTERNATIONAL_SHARE = 0.20
ATHLETE_SHARE = 0.03
FIRSTGEN_SHARE = 0.15
# class -> share living in campus housing (living18 = 1)
ON_CAMPUS_BY_CLASS = {1: 0.97, 2: 0.88, 3: 0.65, 4: 0.45}
# class -> (ages, probabilities) for traditional-age students
AGE_BY_CLASS = {
    1: ([17, 18, 19, 20], [0.03, 0.62, 0.32, 0.03]),
    2: ([18, 19, 20, 21], [0.03, 0.60, 0.33, 0.04]),
    3: ([19, 20, 21, 22], [0.04, 0.58, 0.33, 0.05]),
    4: ([20, 21, 22, 23], [0.05, 0.55, 0.33, 0.07]),
}
OLDER_STUDENT_SHARE = 0.02


def age_category(age: int) -> int:
    """NSSE IRagecol: 19 or younger=1, 20-23=2, 24-29=3, 30-39=4, 40-55=5, over 55=6."""
    for code, upper in enumerate([19, 23, 29, 39, 55], start=1):
        if age <= upper:
            return code
    return 6


def make_population(n: int = N_STUDENTS, seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    cls = rng.choice([1, 2, 3, 4], size=n, p=[0.26, 0.25, 0.25, 0.24])

    age = np.empty(n, dtype=int)
    for c, (ages, probs) in AGE_BY_CLASS.items():
        rows = cls == c
        age[rows] = rng.choice(ages, size=rows.sum(), p=probs)
    older = rng.random(n) < OLDER_STUDENT_SHARE
    age[older] = rng.integers(24, 45, size=older.sum())

    cat_codes = list(MAJOR_CATEGORIES)
    cat_shares = np.array([MAJOR_CATEGORIES[c][0] for c in cat_codes])
    major_col = rng.choice(cat_codes, size=n, p=cat_shares / cat_shares.sum())
    major_code = np.empty(n, dtype=int)
    for cat, (_, codes) in MAJOR_CATEGORIES.items():
        rows = major_col == cat
        weights = np.array([POPULAR_MAJORS.get(m, 1) for m in codes], dtype=float)
        major_code[rows] = rng.choice(list(codes), size=rows.sum(), p=weights / weights.sum())

    internat = (rng.random(n) < INTERNATIONAL_SHARE).astype(int)
    country = np.full(n, -9)
    region = np.full(n, -9)
    country_codes = list(COUNTRIES)
    country_shares = np.array([COUNTRIES[c][0] for c in country_codes])
    intl = internat == 1
    country[intl] = rng.choice(country_codes, size=intl.sum(),
                               p=country_shares / country_shares.sum())
    region[intl] = [COUNTRIES[c][1] for c in country[intl]]

    on_campus = rng.random(n) < np.vectorize(ON_CAMPUS_BY_CLASS.get)(cls)
    living = np.where(on_campus, 1, rng.choice([3, 4], size=n, p=[0.7, 0.3]))
    greek_house = (~on_campus) & (rng.random(n) < 0.03)
    living[greek_house] = 2

    return pd.DataFrame({
        "studentid": np.arange(1, n + 1),
        "class": cls,
        "IRage": age,
        "IRagecol": [age_category(a) for a in age],
        "IRsex19": rng.choice([0, 1, 2], size=n, p=[0.60, 0.39, 0.01]),
        "MAJfirstcode": major_code,
        "MAJfirstcol": major_col,
        "internat": internat,
        "country22": country,
        "countrycol22": region,
        "living18": living,
        "athlete": (rng.random(n) < ATHLETE_SHARE).astype(int),
        "firstgen": (rng.random(n) < FIRSTGEN_SHARE).astype(int),
        "WEIGHT2": 1.0,
    })


def k_value(df: pd.DataFrame, profile: dict[str, int]) -> float:
    rows = df
    for field, value in profile.items():
        rows = rows[rows[field] == value]
    return rows["WEIGHT2"].sum()


# Each step replaces one exact field with its coarser NSSE field (None = drop the field).
GENERALIZATION_STEPS = [
    ("country22", "countrycol22"),
    ("MAJfirstcode", "MAJfirstcol"),
    ("IRage", "IRagecol"),
    ("countrycol22", "internat"),
]
DEMO_FIELDS = ["class", "IRage", "MAJfirstcode", "country22", "living18"]


def demo_ladder(df: pd.DataFrame) -> list[tuple[str, dict[str, int]]]:
    """Take a real Icelandic student from the population and generalize step by step.

    The trap thesis should describe this student, so the starting k is at least 1.
    """
    student = df[df.country22 == 108].iloc[0]
    profile = {f: int(student[f]) for f in DEMO_FIELDS}
    ladder = [(f"student {int(student.studentid)}: exact profile", dict(profile))]
    for exact, coarse in GENERALIZATION_STEPS:
        profile.pop(exact)
        profile[coarse] = int(student[coarse])
        ladder.append((f"  -> {exact} becomes {coarse}", dict(profile)))
    return ladder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="print k for the demo profiles")
    args = parser.parse_args()

    df = make_population()
    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / "population-synthetic.csv"
    df.to_csv(out, index=False)
    print(f"wrote {len(df):,} students to {out}")

    if args.check:
        for label, profile in demo_ladder(df):
            print(f"k = {k_value(df, profile):>6.0f}   {label}   {profile}")
        print(json.dumps({"icelandic_students": int((df.country22 == 108).sum()),
                          "astronomy_majors": int((df.MAJfirstcode == 33).sum())}))


if __name__ == "__main__":
    main()
