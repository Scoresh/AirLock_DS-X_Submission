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
# A name: capitalized words (accents allowed), with middle initials and particles like "de" or "van".
_WORD = r"[A-ZÀ-ÖØ-Þ][a-zß-öø-ÿ'’-]+"
_PARTICLE = r"(?:de|del|della|da|di|du|dos|van|von|der|den|la|le|bin|ibn|al)"
NAME_SHAPE = re.compile(rf"{_WORD}(?: (?:{_WORD}|[A-Z]\.|{_PARTICLE}))*")
NAME_BEFORE = re.compile(rf"({_WORD}) $")  # a capitalized word directly before a detected name
TITLES = {"professor", "prof", "dr", "mr", "mrs", "ms", "mx", "instructor", "student", "advisor",
          "supervisor", "author", "authors", "dean", "chair", "lab", "ta", "by", "for", "dear"}
# Words that make a capitalized phrase a heading or document part, never a person.
STRUCTURE_WORDS = {
    "appendix", "figure", "fig", "table", "chapter", "section", "part", "step", "equation", "eq",
    "cover", "page", "title", "abstract", "introduction", "conclusion", "conclusions", "summary",
    "references", "bibliography", "contents", "acknowledgments", "acknowledgements", "methods",
    "results", "discussion", "procedure", "objective", "objectives", "rubric", "criteria", "points",
    "lab", "prelab", "report", "assignment", "question", "problem", "exercise",
}
# Words after which a detected name has ended ("Elena Marchetti Second Reader").
ROLE_WORDS = {"reader", "readers", "committee", "member", "advisor", "adviser", "chair", "supervisor",
              "instructor", "professor", "student", "approved", "first", "second", "third"}
# Phrases with these words are places or organisations, not people ("Mugar Memorial Library").
ORG_WORDS = {"library", "hall", "university", "college", "school", "department", "institute", "center",
             "centre", "building", "laboratory", "museum", "foundation", "program", "office", "board"}
MULTISPACE = re.compile(r"[ \t]{2,}")  # justified PDF text puts several spaces between words
LOWERCASE_WORD = re.compile(r"\b[a-zß-öø-ÿ][a-zß-öø-ÿ'’-]{2,}\b")
# "Lab Section 4A" or "Section: 04" on one line; not "see section 2" or a heading followed by "0.2".
SECTION = re.compile(r"\b(?:(?:lab|lecture|discussion|recitation) section[ \t]*[:#]?|section[ \t]*[:#])[ \t]*"
                     r"([A-Z]?\d{1,3}[A-Z]?)\b(?![.,]\d)", re.I)

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


class SetupError(RuntimeError):
    """A local dependency is missing; scrubbing must stop rather than silently miss names."""


SETUP_HINT = "In backend/: pip install -r requirements.txt, then python -m spacy download en_core_web_sm"


@lru_cache(maxsize=1)
def _analyzer():
    """Presidio with the small spaCy model. Raises SetupError if either is missing."""
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
    except ImportError as err:
        raise SetupError(f"Name detection (Presidio) is not installed. {SETUP_HINT}") from err
    try:
        provider = NlpEngineProvider(nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        })
        return AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])
    except Exception as err:  # spaCy raises OSError for a missing model; Presidio may wrap it
        detail = f"{type(err).__name__}: {err}"[:300]  # the real cause, not just "missing"
        raise SetupError(f"The spaCy model en_core_web_sm could not be loaded ({detail}). {SETUP_HINT}") from err


def setup_status() -> dict:
    """What the UI shows before upload, so a broken install is visible instead of silent."""
    issues = []
    try:
        _analyzer()
    except SetupError as err:
        issues.append(str(err))
    if not risk.DATA_FILE.exists():
        issues.append("The reference data is missing: put the organizers' NSSE-synthetic.csv in data/ (ask Selina).")
    return {"ready": not issues, "issues": issues}


def _trim_name(name: str) -> str:
    """Cut a detected name at the first heading or role word; '' if it is not a name at all."""
    words = name.split(" ")
    if any(w.lower() in ORG_WORDS for w in words):
        return ""
    for i, w in enumerate(words):
        if w.lower().rstrip(".:,") in STRUCTURE_WORDS | ROLE_WORDS:
            return " ".join(words[:i])  # "" for "Appendix B. Interview Logistics"
    return name


def _looks_like_name(name: str, lowercase_words: set[str]) -> bool:
    words = [w for w in name.split(" ") if not re.fullmatch(rf"[A-Z]\.|{_PARTICLE}", w)]
    # Equipment and headings ("Digital Multimeter") also appear lowercase in the body; real names don't.
    return not all(w.lower() in lowercase_words for w in words if len(w) > 2)


def _person_spans(text: str, lowercase_words: set[str]) -> list[tuple[int, int]]:
    analyzer = _analyzer()
    vocab = risk.vocabulary()
    known = _known(text, vocab["majors"] + vocab["affiliations"])  # "Wayfinding: Studio" is not a person
    spans = []
    for r in analyzer.analyze(text=text, language="en", entities=["PERSON"], score_threshold=0.6):
        start, end = r.start, r.end
        if any(start < e and s < end for s, e, _ in known):
            continue
        if not NAME_SHAPE.fullmatch(text[start:end]) or text[start:end].lower() in _not_names():
            continue  # drops spaCy noise like "Appendix B. Scheduling" or an affiliation like "Indri"
        trimmed = _trim_name(text[start:end]).rstrip(" .")
        if not trimmed:
            continue
        end = start + len(trimmed)
        if PARTICIPANT.fullmatch(text[start:end]) or not _looks_like_name(text[start:end], lowercase_words):
            continue
        # spaCy sometimes drops a first name: "Yago Martínez de Fuenmayor" -> "Martínez de Fuenmayor".
        while (m := NAME_BEFORE.search(text, 0, start)) and m.group(1).lower() not in TITLES:
            start = m.start(1)
        spans.append((start, end))
    return spans


class _Tokenizer:
    """Same original text -> same token across the whole document."""

    def __init__(self) -> None:
        self.key: dict[str, str] = {}
        self.by_value: dict[tuple[str, str], str] = {}
        self.counts: dict[str, int] = {}

    def knows_part(self, word: str) -> bool:
        return any(k == "PERSON" and word in known.split() for k, known in self.by_value)

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


def _tokenize_page(text: str, tok: _Tokenizer, lowercase_words: set[str]) -> tuple[str, list[tuple[str, str]]]:
    spans: list[tuple[int, int, str]] = []
    for kind, pattern in [("EMAIL", EMAIL), ("PHONE", PHONE), ("STUDENT_ID", BU_ID)]:
        spans += [(m.start(), m.end(), kind) for m in pattern.finditer(text)]
    # "LAB Section: 04" -> "LAB Section: [SECTION_01]"; with a class roster it narrows to a few people.
    spans += [(m.start(1), m.end(1), "SECTION") for m in SECTION.finditer(text)]
    taken = lambda s, e: any(s < e2 and s2 < e for s2, e2, _ in spans)  # noqa: E731
    spans += [(s, e, "PERSON") for s, e in _person_spans(text, lowercase_words) if not taken(s, e)]
    spans += [(m.start(), m.end(), "PARTICIPANT") for m in PARTICIPANT.finditer(text) if not taken(m.start(), m.end())]

    # Assign tokens in reading order (so "Maya Lindqvist" claims a token before "Maya"),
    # then replace from the end so earlier offsets stay valid.
    full_names_first = sorted(spans, key=lambda s: (s[2] != "PERSON" or " " not in text[s[0]:s[1]], s[0]))
    tokens = {}
    for start, end, kind in full_names_first:
        value = text[start:end]
        if kind == "PARTICIPANT":
            tokens[start] = f"[PARTICIPANT_{int(PARTICIPANT.fullmatch(value).group(1)):02d}]"
        elif kind == "PERSON" and " " not in value and not tok.knows_part(value):
            continue  # a lone capitalized word ("Banana") counts only as part of a name already found
        else:
            tokens[start] = tok.token(kind, value)
    spans = [s for s in spans if s[0] in tokens]
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
    lowercase_words = set(LOWERCASE_WORD.findall(" ".join(p.text for p in parsed.pages)))
    for page in parsed.pages:
        # PDF text breaks lines mid-sentence; join them so rules and rewrites see whole phrases.
        text = MULTISPACE.sub(" ", LINE_BREAK.sub(" ", page.text))
        text, found = _tokenize_page(text, tok, lowercase_words)
        pages.append(ScrubbedPage(page=page.page, text=text))
        identifiers += [DirectIdentifier(token=t, type=kind, page=page.page) for t, kind in found]

    # Second pass: a name found anywhere is replaced everywhere, including all-caps title pages
    # ("JORDAN WHITFIELD") and places where the model missed it.
    names = sorted(((v, t) for t, v in tok.key.items() if t.startswith("[PERSON_") and " " in v),
                   key=lambda vt: len(vt[0]), reverse=True)
    for i, page in enumerate(pages):
        text = page.text
        for value, token in names:
            pattern = re.compile(r"\b" + r"\s+".join(map(re.escape, value.split())) + r"\b", re.I)
            text, n = pattern.subn(token, text)
            if n:
                identifiers.append(DirectIdentifier(token=token, type="PERSON", page=page.page))
        pages[i] = ScrubbedPage(page=page.page, text=text)

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
