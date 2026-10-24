# StrangerThesis

Scrub a document on your own machine and check who in it could be re-identified.

Scrubbing and risk scoring are real; PDF parsing and rubric review still return the example data in `/mock`. Replace one stub at a time with real code. As long as your function returns the same shape, nobody else's code breaks.

## Running

### macOS

cd backend

#### 1. Create and activate a virtual environment

python3.12 -m venv .venv
source .venv/bin/activate

#### 2. Install dependencies

pip install --upgrade pip
pip install -r requirements.txt

#### 3. Download the local spaCy model (small NLP model, not an LLM)

python -m spacy download en_core_web_sm

#### 4. Add the organizers' reference data (ask Selina for the file)

cp ~/Downloads/NSSE-synthetic.csv ../data/NSSE-synthetic.csv

#### 5. Run the server
uvicorn app.main:app --reload

### Windows (PowerShell)

cd backend

#### 1. Create and activate a virtual environment

py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1

#### 2. Install dependencies

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

#### 3. Download the local spaCy model

python -m spacy download en_core_web_sm

#### 4. Add the organizers' reference data (ask Selina for the file)

Copy-Item "$HOME\Downloads\NSSE-synthetic.csv" ..\data\NSSE-synthetic.csv

#### 5. Run the server
uvicorn app.main:app --reload


## Tech stack

Everything runs locally unless marked otherwise.

| Layer | Tech |
|---|---|
| Backend / API | Python 3.13, FastAPI, Uvicorn, Pydantic (data contracts) |
| Name detection | Microsoft Presidio + spaCy `en_core_web_sm` (small local NLP model, not an LLM) |
| Emails, phones, BU IDs | Regex |
| Participant profiles | Rule-based extraction (patterns like "19-year-old", "majoring in…", "from…") |
| Re-identification risk | pandas: k = number of matching respondents in the reference data |
| Reference population | Organizers' NSSE synthetic data: 20,731 fictional respondents (git-ignored, ask Selina) |
| Generalization | Major → its field → omitted; second major → field → "another field"; affiliation and transfer history → omitted |
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
pip install -r requirements.txt   # includes the spaCy English model
cp ~/Downloads/NSSE-synthetic.csv ../data/NSSE-synthetic.csv   # the organizers' file
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

## What we score on

The organizers' NSSE synthetic data (`data/NSSE-synthetic.csv`, 20,731 respondents, 2014–2024) is fictional by design:
majors are invented ("Clockmaking: Technology") and lemur species stand in for an identity group.

| Detail | Column | Made vaguer to |
|---|---|---|
| Class year | `Class` | (kept) |
| Major | `MAJfirst` | its field (`Clockmaking`) → omitted |
| Second major | `MAJsecond` | its field → "another field" |
| Affiliation | `affiliation` | omitted |
| Transfer student | `begincol` | omitted |

There are no weights; each row is one respondent, so k = number of matching rows.
3,106 of the 4,610 combinations of these five details belong to exactly one respondent.

Risk: k 1–4 high (blocks), 5–19 medium (warns), 20+ low.

## Team workflow

- Work on a branch (`feature/<what>`), open a PR to `main`. Don't push to `main` directly.
- After every code change, add a summary to `kiro_change_logs/` (see `.kiro/steering/change-logging.md`).
