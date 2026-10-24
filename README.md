# Stranger Mode

Scrub a document on your own machine, check who in it could be re-identified, and only then send it to an LLM for rubric review.

Scrubbing and risk scoring are real; PDF parsing and rubric review still return the example data in `/mock`. Replace one stub at a time with real code. As long as your function returns the same shape, nobody else's code breaks.

## Tech stack

Everything runs locally unless marked otherwise.

| Layer | Tech |
|---|---|
| Backend / API | Python 3.13, FastAPI, Uvicorn, Pydantic (data contracts) |
| Name detection | Microsoft Presidio + spaCy `en_core_web_sm` (small local NLP model, not an LLM) |
| Emails, phones, BU IDs | Regex |
| Participant profiles | Rule-based extraction (patterns like "19-year-old", "majoring in…", "from…") |
| Re-identification risk | pandas: k = number of matching students in the population |
| Reference population | NSSE codebook fields; fallback synthetic data generated with numpy (organizers' NSSE data once we have access) |
| Generalization | NSSE's own coarser fields (age → age band, country → region → "international", major → major group) + fixed rewrite phrases |
| Token storage | Local JSON key file in `keys/`, git-ignored, never sent anywhere |
| PDF | PyMuPDF (test PDF built; parsing in progress) |
| Frontend | Plain HTML + JavaScript test page (heatmap, side-by-side view) |
| Rubric review | Configurable LLM endpoint (in progress). The only network call, and it receives only tokenized, gate-approved text |
| Dev tools | Kiro, Git, GitHub |

## Run it

Use Python 3.13 (3.14 has no prebuilt pydantic-core wheel yet).

```bash
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python scripts/make_population.py
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 for the UI, http://127.0.0.1:8000/docs to try each endpoint. The test thesis is `samples/test-thesis.pdf`; see `samples/README.md` for what it should produce.

## Pipeline

| Step | Endpoint | File | Owner |
|---|---|---|---|
| 1. Parse PDF into pages + layout | `POST /parse` | `parse.py` | Aedyn + Florian |
| 2. Tokenize names/emails/IDs, extract participant profiles | `POST /scrub/{doc_id}` | `scrub.py` | Selina |
| 3. k-value, suggestions, privacy gate | `POST /score` | `risk.py` | Selina |
| 4a. Formatting rules (code, no LLM) | inside `/review` | `format_rules.py` | Aedyn + Florian |
| 4b. LLM rubric review + token restore | `POST /review` | `review.py` | Dan |
| Side-by-side "what the LLM saw" | `GET /llm-view/{doc_id}` | `main.py` | Dan |
| API glue, integration | | `main.py` | Dan |
| UI | | `frontend/index.html` | TBD |

`/review` returns 403 while the gate is closed.

## Data contracts

Defined in `backend/app/schemas.py`, with examples in `mock/`:

- `parse.json` — pages with text, margins, fonts, page-number position
- `scrub.json` — scrubbed text, direct identifiers (tokens only), participants with NSSE attributes
- `score.json` — k, risk level, generalization suggestions, `gate_open`
- `review.json` — findings with page, quoted rubric criterion, and `source: rule | llm`

**Change a contract only after telling the team**, and update the mock file in the same commit.

## Privacy rules for the code

- The token key (`token -> original`) is written only to `keys/<doc_id>.json`. It is git-ignored and never returned by the API.
- `review.py` receives only `ScrubResult`. Never pass original page text to the LLM.
- No external API calls anywhere except the configured LLM endpoint in `review.py`.

## NSSE fields we score on

From the NSSE 2026 US codebook (`docs/`). Check which ones the organizers' synthetic data actually has.

| Detail | Exact | Coarser |
|---|---|---|
| Age | `IRage` | `IRagecol` |
| Country | `country22` | `countrycol22` → `internat26` |
| Major | `MAJfirstcode` | `MAJfirstcol` |
| Class | `class` | |
| Sex | `IRsex19` | |
| Housing | `living18` | |
| Athlete / Greek / first-gen | `athlete`, `gr_all24`, `firstgen` | |

k = sum of `WEIGHT2` over matching rows (`WEIGHT2` scales respondents up to the school's population).

Risk: k 1–4 high (blocks), 5–19 medium (warns), 20+ low.

## Team workflow

- Work on a branch (`feature/<what>`), open a PR to `main`. Don't push to `main` directly.
- After every code change, add a summary to `kiro_change_logs/` (see `.kiro/steering/change-logging.md`).
