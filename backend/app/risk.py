"""k-value scoring, generalization suggestions, privacy gate.  Owner: Selina.

k = sum of WEIGHT2 over population rows matching every attribute of a participant
    (WEIGHT2 scales survey respondents up to the institution's population).

Population file, first one found in /data:
    NSSE-synthetic.csv       organizers' data, once we have access
    population-synthetic.csv fallback from scripts/make_population.py

Generalization ladder (exact field -> coarser NSSE field):
    IRage -> IRagecol
    country22 -> countrycol22 -> internat
    MAJfirstcode -> MAJfirstcol
"""
from functools import lru_cache
from pathlib import Path

import pandas as pd

from . import nsse_codes as codes
from .schemas import AcceptedFix, Risk, ScoredParticipant, ScoreResult, ScrubbedPage, ScrubResult, Suggestion

HIGH_MAX_K = 4     # 1-4 blocks sending
MEDIUM_MAX_K = 19  # 5-19 warns

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
POPULATION_FILES = ["NSSE-synthetic.csv", "population-synthetic.csv"]

LADDER = {
    "IRage": "IRagecol",
    "country22": "countrycol22",
    "countrycol22": "internat",
    "MAJfirstcode": "MAJfirstcol",
}

# Attribute label tables: field -> {code: label}. Fields not listed hold 0/1 or an int.
LABELS: dict[str, dict[int, str]] = {
    "IRagecol": codes.AGE_CATEGORY,
    "class": codes.CLASS,
    "MAJfirstcode": codes.MAJOR,
    "MAJfirstcol": codes.MAJOR_CATEGORY,
    "country22": codes.COUNTRY,
    "countrycol22": codes.REGION,
    "living18": codes.LIVING,
    "IRsex19": codes.SEX,
}

# How a coarser value reads in the rewritten sentence.
PHRASES: dict[str, dict[int, str]] = {
    "IRagecol": {1: "teenage", 2: "early-20s", 3: "mid-to-late-20s", 4: "30-something",
                 5: "middle-aged", 6: "older"},
    "MAJfirstcol": {1: "humanities", 2: "life sciences", 3: "physical sciences",
                    4: "social sciences", 5: "business", 6: "communications", 7: "education",
                    8: "engineering", 9: "health", 10: "social service", 11: "interdisciplinary"},
    "countrycol22": codes.REGION,
}
ABROAD = "abroad"


def risk_level(k: int) -> Risk:
    if k <= HIGH_MAX_K:
        return "high"
    if k <= MEDIUM_MAX_K:
        return "medium"
    return "low"


@lru_cache(maxsize=1)
def population() -> pd.DataFrame:
    for name in POPULATION_FILES:
        path = DATA_DIR / name
        if path.exists():
            df = pd.read_csv(path, low_memory=False)
            weight = next((c for c in df.columns if c.lower() == "weight2"), None)
            df["_w"] = df[weight] if weight else 1.0
            return df
    raise FileNotFoundError(f"no population file in {DATA_DIR}; run scripts/make_population.py")


@lru_cache(maxsize=1)
def region_of_country() -> dict[int, int]:
    df = population()
    known = df[(df.country22 > 0) & (df.countrycol22 > 0)]
    return known.groupby("country22").countrycol22.agg(lambda s: s.mode()[0]).to_dict()


def encode(field: str, value: str | int) -> int:
    """Attribute label (as stored in ScrubResult) -> NSSE code."""
    if field not in LABELS:
        return int(value)
    if isinstance(value, int):
        return value
    lookup = {label.lower(): code for code, label in LABELS[field].items()}
    return lookup[str(value).lower()]


def decode(field: str, code: int) -> str | int:
    return LABELS[field][code] if field in LABELS else code


def coarsen(field: str, code: int) -> int:
    new_field = LADDER[field]
    if new_field == "IRagecol":
        return codes.age_category(code)
    if new_field == "MAJfirstcol":
        return codes.major_category(code)
    if new_field == "countrycol22":
        return region_of_country().get(code, 8)  # 8 = unknown region
    return 1  # internat: they are an international student


def k_value(profile: dict[str, int]) -> int:
    df = population()
    mask = pd.Series(True, index=df.index)
    for field, code in profile.items():
        if field in df.columns:
            mask &= df[field] == code
    return int(round(df.loc[mask, "_w"].sum()))


def phrase(field: str, code: int) -> str:
    if field == "internat":
        return ABROAD
    return PHRASES.get(field, {}).get(code) or str(decode(field, code))


def _generalize(profile: dict[str, int], mentions: dict[str, str], field: str) -> list[tuple[str, str]]:
    """Apply one ladder step in place; return the text replacements it implies."""
    new_field = LADDER[field]
    new_code = coarsen(field, profile.pop(field))
    profile[new_field] = new_code
    rewrites = []
    if field in mentions:
        old_text, new_text = mentions.pop(field), phrase(new_field, new_code)
        rewrites.append((old_text, new_text))
        mentions[new_field] = new_text
    return rewrites


def _replay(scrubbed: ScrubResult, accepted: list[AcceptedFix]):
    """Current profile, mentions and text rewrites per participant after all accepted fixes."""
    state = {}
    for p in scrubbed.participants:
        profile = {f: encode(f, v) for f, v in p.attributes.items()}
        mentions = dict(p.mentions)
        rewrites: list[tuple[str, str]] = []
        for fix in accepted:
            if fix.participant_id == p.id and fix.field in profile and fix.field in LADDER:
                rewrites += _generalize(profile, mentions, fix.field)
        state[p.id] = (profile, mentions, rewrites)
    return state


def score(scrubbed: ScrubResult, accepted: list[AcceptedFix]) -> ScoreResult:
    participants = []
    for p in scrubbed.participants:
        profile, mentions, _ = _replay(scrubbed, accepted)[p.id]
        k = k_value(profile)
        suggestions = []
        for field in [f for f in profile if f in LADDER]:
            trial, trial_mentions = dict(profile), dict(mentions)
            _generalize(trial, trial_mentions, field)
            new_field = LADDER[field]
            suggestions.append(Suggestion(
                field=field,
                from_=str(decode(field, profile[field])),
                to=str(decode(new_field, trial[new_field])) if new_field != "internat" else "international student",
                new_field=new_field,
                new_k=k_value(trial),
            ))
        suggestions.sort(key=lambda s: s.new_k, reverse=True)
        participants.append(ScoredParticipant(
            id=p.id,
            k=k,
            risk=risk_level(k),
            attributes={f: decode(f, c) for f, c in profile.items()},
            suggestions=suggestions if risk_level(k) != "low" else [],
        ))
    return ScoreResult(
        doc_id=scrubbed.doc_id,
        participants=participants,
        gate_open=all(p.risk != "high" for p in participants),
    )


def rewrite(scrubbed: ScrubResult, accepted: list[AcceptedFix]) -> ScrubResult:
    """Scrubbed text with every accepted generalization applied: this is what the LLM sees."""
    replays = _replay(scrubbed, accepted)
    pages = []
    for page in scrubbed.scrubbed_pages:
        text = page.text
        for p in scrubbed.participants:
            if page.page in p.pages:
                for old, new in replays[p.id][2]:
                    text = text.replace(old, new)
        pages.append(ScrubbedPage(page=page.page, text=text))
    return scrubbed.model_copy(update={"scrubbed_pages": pages})
