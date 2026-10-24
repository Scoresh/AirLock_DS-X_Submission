"""k-value scoring, generalization suggestions, privacy gate.  Owner: Selina.

Reference population: the organizers' NSSE synthetic data, data/NSSE-synthetic.csv
(20,731 made-up respondents across six survey years; git-ignored, ask Selina for the file).
It is a fictional world: majors like "Clockmaking: Theory" and lemur species standing in
for an identity group. Each row is one respondent and there are no weights, so

    k = number of respondents matching every detail of a participant's description.

Quasi-identifiers and how each can be made vaguer (OMIT = drop the detail):
    MAJfirst        "Clockmaking: Theory"  -> MAJfirstfield "Clockmaking" -> OMIT
    MAJsecond       second major           -> MAJsecondfield              -> MAJnum "Double major"
    affiliation     lemur species          -> OMIT
    begincol        transferred in         -> OMIT
    Class           first-year / senior    (kept: already coarse)
"""
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .schemas import AcceptedFix, Risk, ScoredParticipant, ScoreResult, ScrubbedPage, ScrubResult, Suggestion

HIGH_MAX_K = 4     # 1-4 blocks sending
MEDIUM_MAX_K = 19  # 5-19 warns

# The data stays out of git. First match wins: NSSE_DATA_FILE, the repo's data/ folder,
# then Render's secret-file mount (add a secret file named NSSE-synthetic.csv).
_CANDIDATES = [os.getenv("NSSE_DATA_FILE"),
               Path(__file__).resolve().parents[2] / "data" / "NSSE-synthetic.csv",
               "/etc/secrets/NSSE-synthetic.csv"]
DATA_FILE = next((Path(p) for p in _CANDIDATES if p and Path(p).exists()), Path(_CANDIDATES[1]))

OMIT = ""
LADDER = {
    "MAJfirst": "MAJfirstfield",
    "MAJfirstfield": OMIT,
    "MAJsecond": "MAJsecondfield",
    "MAJsecondfield": "MAJnum",
    "affiliation": OMIT,
    "begincol": OMIT,
}
OMITTED_TEXT = {"MAJfirstfield": "[major omitted]", "affiliation": "[affiliation omitted]",
                "begincol": "[transfer history omitted]"}
CLASS_LABEL = {"FY": "First-year", "SR": "Senior", "Other": "Other"}
TRANSFERRED = "Started at another college"
DOUBLE_MAJOR = "Double major"


def risk_level(k: int) -> Risk:
    if k <= HIGH_MAX_K:
        return "high"
    if k <= MEDIUM_MAX_K:
        return "medium"
    return "low"


def _field_of(major: pd.Series) -> pd.Series:
    return major.str.split(":").str[0].str.strip()


@lru_cache(maxsize=1)
def population() -> pd.DataFrame:
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"put the organizers' NSSE-synthetic.csv in {DATA_FILE.parent}")
    raw = pd.read_csv(DATA_FILE, na_values=["#NULL!", " ", "-9"], low_memory=False,
                      usecols=["Class", "affiliation", "MAJfirst", "MAJsecond", "MAJnum", "begincol"])
    return pd.DataFrame({
        "Class": raw["Class"].map(CLASS_LABEL),
        "affiliation": raw["affiliation"],
        "MAJfirst": raw["MAJfirst"],
        "MAJfirstfield": _field_of(raw["MAJfirst"]),
        "MAJsecond": raw["MAJsecond"],
        "MAJsecondfield": _field_of(raw["MAJsecond"]),
        "MAJnum": raw["MAJnum"].map({1: "Single major", 2: DOUBLE_MAJOR}),
        "begincol": raw["begincol"].map({0: "Started here", 1: TRANSFERRED}),
    })


@lru_cache(maxsize=1)
def vocabulary() -> dict[str, list[str]]:
    """Values the text rules can recognise, longest first so "Tea Sciences: Policy" beats "Tea Sciences"."""
    df = population()
    by_length = lambda values: sorted(set(values.dropna()), key=len, reverse=True)  # noqa: E731
    return {
        "majors": by_length(pd.concat([df["MAJfirst"], df["MAJsecond"]])),
        "affiliations": by_length(df["affiliation"]),
    }


def coarsen(field: str, value: str) -> tuple[str, str | None]:
    """One step up the ladder: (new field, new value); new field OMIT drops the detail."""
    new_field = LADDER[field]
    if new_field in ("MAJfirstfield", "MAJsecondfield"):
        return new_field, value.split(":")[0].strip()
    if new_field == "MAJnum":
        return new_field, DOUBLE_MAJOR
    return OMIT, None


def k_value(profile: dict[str, str]) -> int:
    df = population()
    mask = pd.Series(True, index=df.index)
    for field, value in profile.items():
        mask &= df[field] == value
    return int(mask.sum())


def phrase(field: str, new_field: str, value: str | None) -> str:
    """How the vaguer detail reads in the rewritten sentence."""
    if new_field == OMIT:
        return OMITTED_TEXT[field]
    if new_field == "MAJnum":
        return "another field"
    return value


def _generalize(profile: dict[str, str], mentions: dict[str, str], field: str) -> list[tuple[str, str]]:
    """Apply one ladder step in place; return the text replacements it implies."""
    new_field, new_value = coarsen(field, profile.pop(field))
    if new_field != OMIT:
        profile[new_field] = new_value
    rewrites = []
    if field in mentions:
        old_text, new_text = mentions.pop(field), phrase(field, new_field, new_value)
        rewrites.append((old_text, new_text))
        if new_field != OMIT:
            mentions[new_field] = new_text
    return rewrites


def _replay(scrubbed: ScrubResult, accepted: list[AcceptedFix]):
    """Current profile, mentions and text rewrites per participant after all accepted fixes."""
    state = {}
    for p in scrubbed.participants:
        profile = {f: str(v) for f, v in p.attributes.items()}
        mentions = dict(p.mentions)
        rewrites: list[tuple[str, str]] = []
        for fix in accepted:
            if fix.participant_id == p.id and fix.field in profile and fix.field in LADDER:
                rewrites += _generalize(profile, mentions, fix.field)
        state[p.id] = (profile, mentions, rewrites)
    return state


def score(scrubbed: ScrubResult, accepted: list[AcceptedFix]) -> ScoreResult:
    replays = _replay(scrubbed, accepted)
    participants = []
    for p in scrubbed.participants:
        profile, mentions, _ = replays[p.id]
        k = k_value(profile)
        suggestions = []
        for field in [f for f in profile if f in LADDER]:
            trial = dict(profile)
            new_field, new_value = coarsen(field, trial.pop(field))
            if new_field != OMIT:
                trial[new_field] = new_value
            suggestions.append(Suggestion(
                field=field,
                from_=profile[field],
                to=new_value if new_field != OMIT else "omitted",
                new_field=new_field,
                new_k=k_value(trial),
            ))
        suggestions.sort(key=lambda s: s.new_k, reverse=True)
        participants.append(ScoredParticipant(
            id=p.id,
            k=k,
            risk=risk_level(k),
            attributes=profile,
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
