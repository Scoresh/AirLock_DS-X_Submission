# StrangerThesis

**Anything you submit can be traced back to the people in it. StrangerThesis scrubs it on your machine first, then lets AI review it.**

Researchers and students increasingly paste drafts into AI tools and submit work to public repositories. Removing names is not enough: in the organizers' NSSE data, **14.9% of respondents are unique** on five ordinary details (class year, affiliation, major, second major, transfer history), and **52%** once survey year and program are added. StrangerThesis finds direct identifiers, measures re-identification risk with **k-anonymity** against a reference population, suggests rewrites until nobody is singled out, and only then lets the prepared text reach the review model the user chooses.

It answers two DS+X prompts: **Data Scrubbing / Tokenization Tool** and **ETD Formatting Compliance Checker**.

| Result | Where |
|---|---|
| Unique respondents fall from 14.9% to 0.0% after generalization; low-risk rises from 51.8% to 99.0% | [docs/RISK_REPORT.md](docs/RISK_REPORT.md) |
| Smallest affiliation group: 26.3% unique vs 11.2% in the largest | [docs/RISK_REPORT.md](docs/RISK_REPORT.md), [docs/ETHICS.md](docs/ETHICS.md) |
| 13 of 13 planted identifiers replaced, 0 false positives; 6 of 6 participants scored correctly | [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md) |
| 12 format rules from the BU guide; 6 of 6 planted format errors found, 0 false alarms | [docs/VALIDATION.md](docs/VALIDATION.md), [docs/RULES_CHECKLIST.md](docs/RULES_CHECKLIST.md) |
| 37 automated tests, including a leak test on the outgoing model request | `tests/` |

![Uniqueness curve](docs/img/uniqueness_curve.png)

## The pipeline

Every step runs on the user's machine except step 5, which sends only scrubbed, gate-approved text.

1. **Parse** (`backend/app/parse.py`). PyMuPDF reads each page: text, margins, fonts and the printed page number with its position.
2. **Scrub direct identifiers** (`backend/app/scrub.py`). Presidio with spaCy finds names; regex finds emails, phone numbers, BU IDs and course sections. Each becomes a token such as `[PERSON_01]`; the key file stays in `keys/`. A name found once is replaced everywhere, including all-caps title pages.
3. **Profile and score** (`backend/app/risk.py`, `backend/app/risk_config.json`). Rules extract each described participant's quasi-identifiers. **k** is the number of respondents in the reference data who match all of them. Risk: k 1-4 high, 5-19 medium, 20+ low.
4. **Privacy gate and generalization.** While any participant has k < 5 the backend refuses review. Suggested rewrites (major to field, details omitted) are applied to the sentence itself and re-scored.
5. **Review** (`backend/app/review.py`). The prepared text and rubric go to the configured OpenAI-compatible endpoint (TerrierGPT, a lab-approved model or local Ollama). Tokens in the feedback are restored locally.
6. **Format rules** (`backend/app/format_rules.py`). Twelve checks from the BU thesis guide, each citing its page.
7. **CSV mode** (`backend/app/csv_mode.py`). Scrub a whole data table: identifier columns become tokens, quasi-identifiers are generalized, and the risk report compares k before and after. The key file restores the exact table.

The web app (`frontend/`) shows the document, a page index colored by findings, the privacy check with per-suggestion rewrites, the gate, review annotations, and a side-by-side view of the original and exactly what the model receives.

## Run it

Use **Python 3.13** (pandas 2.2.3 has no wheel for 3.14). `requirements.txt` includes the spaCy model and pins `preshed` (3.0.14 crashes spaCy).

macOS / Linux, from `backend/`:

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ~/Downloads/NSSE-synthetic.csv ../data/NSSE-synthetic.csv   # the organizers' file, ask Selina
uvicorn app.main:app --reload
```

Windows PowerShell, from `backend\`:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item "$HOME\Downloads\NSSE-synthetic.csv" ..\data\NSSE-synthetic.csv
.venv\Scripts\python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 and click **Open sample document** for the demo thesis (`samples/demo-thesis.pdf`, described in `samples/README.md`). If anything required is missing, the page says what and how to fix it instead of running with partial checks.

**Review model (optional).** Set `LLM_BASE_URL` (for example `http://localhost:11434/v1` for Ollama), `LLM_MODEL` and, if needed, `LLM_API_KEY` before starting the server. Without them, only local rules run and nothing is sent.

## Reproduce the analysis and tests

From the repository root, with the backend environment active:

```bash
pip install -r backend/requirements-dev.txt
python -m pytest                              # 37 tests on a Faker fixture
python backend/scripts/profile_data.py         # docs/DATA_SCHEMA.md (aggregates only)
python backend/scripts/risk_report.py          # docs/RISK_REPORT.md and charts
python backend/scripts/validate_rules.py       # docs/RULES_CHECKLIST.md and docs/VALIDATION.md
python backend/scripts/test_results.py         # docs/TEST_RESULTS.md
python backend/scripts/scrub_csv.py data/NSSE-synthetic.csv   # CSV mode from the command line
```

## Data and privacy rules

- The organizers' NSSE synthetic data (20,731 fictional respondents) lives in `data/`, which is git-ignored. Scripts report aggregates only, with counts below 5 suppressed.
- Tests use a Faker fixture (`tests/fixtures/`) with the same columns; no real rows are copied into tests or docs.
- Token key files live in `keys/` (git-ignored) and are never returned by the API or sent anywhere.
- The only network call is `review._send`, and it only receives `ScrubResult` text after the gate opens. A test records every outgoing request and fails if a name, email, phone number or ID appears in it.
- Quasi-identifiers and generalization rules are configured in `backend/app/risk_config.json`, not in code.

## Documents

| File | Contents |
|---|---|
| [docs/DATA_SCHEMA.md](docs/DATA_SCHEMA.md) | Columns, types, null shares and privacy role of each |
| [docs/RISK_REPORT.md](docs/RISK_REPORT.md) | Uniqueness curve, k distribution before and after generalization, risk by group |
| [docs/RULES_CHECKLIST.md](docs/RULES_CHECKLIST.md) | Each format rule, its BU guide page and how it is checked |
| [docs/VALIDATION.md](docs/VALIDATION.md) | Format rules on the demo thesis: found vs planted |
| [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md) | Identifier detection, participants, round trip, test run |
| [docs/ETHICS.md](docs/ETHICS.md) | Data sourcing, privacy design, fairness, limitations, misuse |

## Team workflow

- Work on a branch (`feature/<what>`) and open a PR to `main`.
- After every code change, add a summary to `kiro_change_logs/` (see `.kiro/steering/change-logging.md`).
- Change a data contract in `backend/app/schemas.py` only after telling the team, and update `mock/` in the same commit.
