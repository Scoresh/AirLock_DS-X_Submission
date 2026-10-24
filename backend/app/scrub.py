"""Direct identifiers -> tokens, and participant profiles.  Owner: Selina.

Runs fully locally. The token key (token -> original text) is saved to keys/<doc_id>.json
and never included in any API response or LLM request.

Direct identifiers: regex for emails, phone numbers and BU IDs (U + 8 digits); Presidio
(spaCy en_core_web_sm) for person names. Participant labels ("Participant 3", "P3")
become [PARTICIPANT_03]. Profiles come from rules over each sentence that mentions a
participant: class year, majors, affiliation and transfer history, matched against the
reference data's own vocabulary (see risk.py).
"""
import json
import re
from functools import lru_cache
from pathlib import Path

from . import risk
from .schemas import DirectIdentifier, Evidence, ParseResult, Participant, ScrubbedPage, ScrubResult

KEYS_DIR = Path(__file__).resolve().parents[2] / "keys"

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
PHONE = re.compile(r"(?<!\d)(?:\(\d{3}\)\s?|\d{3}[-.\s])\d{3}[-.\s]\d{4}(?!\d)")
BU_ID = re.compile(r"\bU\d{8}\b")
PARTICIPANT = re.compile(r"\b(?:Participant\s+|P)(\d{1,3})\b")
PARTICIPANT_TOKEN = re.compile(r"\[(PARTICIPANT_\d{2,3})\]")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
LINE_BREAK = re.compile(r"(?<!\n)\n(?!\n)")  # a single newline inside a paragraph
NAME_SHAPE = re.compile(r"[A-Z][a-z'’-]+(?: [A-Z][a-z'’-]+){0,3}")

CLASS_RE = re.compile(r"\b(first-year|freshman|senior)\b", re.I)
CLASS_LABEL = {"first-year": "First-year", "freshman": "First-year", "senior": "Senior"}
SECOND_MAJOR = re.compile(r"\b(?:second|double) major in\s+$", re.I)
TRANSFER = re.compile(r"\btransferred from another (?:college|university|school|institution)\b"
                      r"|\btransfer student\b|\bstarted (?:college )?elsewhere\b", re.I)


def _known(sentence: str, values: list[str]) -> list[tuple[int, int, str]]:
    """Every non-overlapping occurrence of a known value, longest values first."""
    found: list[tuple[int, int, str]] = []
    lower = sentence.lower()
    for value in values:
        start = lower.find(value.lower())
        while start >= 0:
            end = start + len(value)
            if not any(start < e and s < end for s, e, _ in found):
                found.append((start, end, value))
            start = lower.find(value.lower(), end)
    return sorted(found)


@lru_cache(maxsize=1)
def _not_names() -> set[str]:
    """Affiliations and majors from the reference data look like names to spaCy."""
    vocab = risk.vocabulary()
    return {v.lower() for v in vocab["affiliations"]} | {v.split(":")[0].strip().lower() for v in vocab["majors"]}


@lru_cache(maxsize=1)
def _analyzer():
    """Presidio with the small spaCy model; None if it is not installed."""
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
    except ImportError:
        return None
    provider = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
    })
    return AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])


def _person_spans(text: str) -> list[tuple[int, int]]:
    analyzer = _analyzer()
    if analyzer is None:
        return []
    vocab = risk.vocabulary()
    known = _known(text, vocab["majors"] + vocab["affiliations"])  # "Wayfinding: Studio" is not a person
    spans = []
    for r in analyzer.analyze(text=text, language="en", entities=["PERSON"], score_threshold=0.6):
        name = text[r.start:r.end]
        if any(r.start < e and s < r.end for s, e, _ in known):
            continue
        if not NAME_SHAPE.fullmatch(name) or name.lower() in _not_names():
            continue  # drops spaCy noise like "Appendix B. Scheduling" or an affiliation like "Indri"
        if PARTICIPANT.fullmatch(name):
            continue
        spans.append((r.start, r.end))
    return spans


class _Tokenizer:
    """Same original text -> same token across the whole document."""

    def __init__(self) -> None:
        self.key: dict[str, str] = {}
        self.by_value: dict[tuple[str, str], str] = {}
        self.counts: dict[str, int] = {}

    def token(self, kind: str, value: str) -> str:
        if kind == "PERSON":  # "Maya" or "Lindqvist" after "Maya Lindqvist" reuses its token
            for (k, known), tok in self.by_value.items():
                if k == "PERSON" and value in known.split():
                    return tok
        if (kind, value) not in self.by_value:
            self.counts[kind] = self.counts.get(kind, 0) + 1
            tok = f"[{kind}_{self.counts[kind]:02d}]"
            self.by_value[(kind, value)] = tok
            self.key[tok] = value
        return self.by_value[(kind, value)]


def _tokenize_page(text: str, tok: _Tokenizer) -> tuple[str, list[tuple[str, str]]]:
    spans: list[tuple[int, int, str]] = []
    for kind, pattern in [("EMAIL", EMAIL), ("PHONE", PHONE), ("STUDENT_ID", BU_ID)]:
        spans += [(m.start(), m.end(), kind) for m in pattern.finditer(text)]
    taken = lambda s, e: any(s < e2 and s2 < e for s2, e2, _ in spans)  # noqa: E731
    spans += [(s, e, "PERSON") for s, e in _person_spans(text) if not taken(s, e)]
    spans += [(m.start(), m.end(), "PARTICIPANT") for m in PARTICIPANT.finditer(text) if not taken(m.start(), m.end())]

    # Assign tokens in reading order (so "Maya Lindqvist" claims a token before "Maya"),
    # then replace from the end so earlier offsets stay valid.
    full_names_first = sorted(spans, key=lambda s: (s[2] != "PERSON" or " " not in text[s[0]:s[1]], s[0]))
    tokens = {}
    for start, end, kind in full_names_first:
        value = text[start:end]
        if kind == "PARTICIPANT":
            tokens[start] = f"[PARTICIPANT_{int(PARTICIPANT.fullmatch(value).group(1)):02d}]"
        else:
            tokens[start] = tok.token(kind, value)
    found = []
    for start, end, kind in sorted(spans, reverse=True):
        text = text[:start] + tokens[start] + text[end:]
        if kind != "PARTICIPANT":
            found.append((tokens[start], kind))
    return text, found[::-1]


def _profile(sentence: str) -> tuple[dict[str, str], dict[str, str]]:
    """Rule-based quasi-identifiers from one sentence: (attributes, mentions).

    Values use the reference data's own vocabulary (risk.vocabulary), so every
    recognised detail can be counted in the population.
    """
    vocab = risk.vocabulary()
    attrs: dict[str, str] = {}
    mentions: dict[str, str] = {}
    if m := CLASS_RE.search(sentence):
        attrs["Class"] = CLASS_LABEL[m.group(1).lower()]
    for start, end, value in _known(sentence, vocab["majors"]):
        field = "MAJsecond" if SECOND_MAJOR.search(sentence[:start]) else "MAJfirst"
        if field not in attrs:
            attrs[field] = value
            mentions[field] = sentence[start:end]
    if hits := _known(sentence, vocab["affiliations"]):
        start, end, value = hits[0]
        attrs["affiliation"] = value
        mentions["affiliation"] = sentence[start:end]
    if m := TRANSFER.search(sentence):
        attrs["begincol"] = risk.TRANSFERRED
        mentions["begincol"] = m.group(0)
    return attrs, mentions


def _participants(pages: list[ScrubbedPage]) -> list[Participant]:
    """Profiles from the scrubbed text, so evidence quotes never contain names."""
    found: dict[str, Participant] = {}
    for page in pages:
        for sentence in SENTENCE_END.split(page.text):
            ids = set(PARTICIPANT_TOKEN.findall(sentence))
            if len(ids) != 1:  # skip sentences that mention zero or several participants
                continue
            pid = ids.pop()
            attrs, mentions = _profile(sentence)
            if not attrs:
                continue
            p = found.setdefault(pid, Participant(id=pid, pages=[], attributes={}, evidence=[]))
            p.attributes |= attrs
            p.mentions |= mentions
            p.evidence.append(Evidence(page=page.page, quote=sentence.strip()))
            if page.page not in p.pages:
                p.pages.append(page.page)
    return sorted(found.values(), key=lambda p: p.id)


def scrub(parsed: ParseResult) -> ScrubResult:
    tok = _Tokenizer()
    pages, identifiers = [], []
    for page in parsed.pages:
        # PDF text breaks lines mid-sentence; join them so rules and rewrites see whole phrases.
        text, found = _tokenize_page(LINE_BREAK.sub(" ", page.text), tok)
        pages.append(ScrubbedPage(page=page.page, text=text))
        identifiers += [DirectIdentifier(token=t, type=kind, page=page.page) for t, kind in found]

    KEYS_DIR.mkdir(exist_ok=True)
    (KEYS_DIR / f"{parsed.doc_id}.json").write_text(json.dumps(tok.key, indent=2))
    return ScrubResult(
        doc_id=parsed.doc_id,
        scrubbed_pages=pages,
        direct_identifiers=identifiers,
        participants=_participants(pages),
    )


def load_key(doc_id: str) -> dict[str, str]:
    """Token -> original text, for local restore in review.py. Never send this anywhere."""
    path = KEYS_DIR / f"{doc_id}.json"
    return json.loads(path.read_text()) if path.exists() else {}
