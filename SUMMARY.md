# StrangerThesis — Summary

StrangerThesis is a local-first privacy firewall for documents you plan to submit online (theses, papers, grant applications, assignments). It scrubs identifying details on your own machine first, checks who in the document could be re-identified, and only lets the text leave your computer once that risk is acceptable.

## How it works

The pipeline runs in two stages separated by a privacy gate.

### Stage 1 — Local privacy check (everything runs on your machine)

- Parse the document (PDF) into pages with text and layout.
- Tokenize direct identifiers — names, emails, phone numbers, BU IDs — using Microsoft Presidio, spaCy, and regex. The mapping from token back to the original is saved only to a local key file that never leaves your machine.
- Build participant profiles by extracting attributes (e.g., "19-year-old," major, where they're from).
- Score re-identification risk against a reference population (the organizers' NSSE synthetic data of ~20,731 fictional respondents). The risk is a k-value: how many respondents share the same combination of details.
  - k 1–4 = high risk: the gate blocks sending.
  - k 5–19 = medium: warns, user decides.
  - k 20+ = low: passes.
- Suggest generalizations to lower risk (e.g., a specific major → its broader field → omitted).

### The privacy gate

Nothing crosses the network while anyone in the document is high-risk. Only tokenized, gate-approved text is ever allowed out.

### Stage 2 — Review (scrubbed text only)

- Measurable formatting checks (margins, fonts, page numbering) run as local code — no network needed.
- The only outbound network call sends just the tokenized, gate-approved text to a user-configured LLM endpoint. Tokens are then restored locally so results map back to the real names on your machine.
- A side-by-side view lets you see exactly "what the LLM saw."

## Core guarantees

- Every step except that one LLM call runs locally.
- The token key file never leaves your machine.
- No external API calls anywhere in the scrubbing/profiling path.

## Tech stack

Python 3.13 + FastAPI on the backend, Presidio/spaCy/regex for detection, pandas for risk scoring, PyMuPDF for PDFs, and a plain HTML/JS frontend with a heatmap and side-by-side view.

Every step is real: PDF parsing, scrubbing, risk scoring, the twelve local format rules, CSV mode, and the model review and rubric check through the endpoint chosen in Settings. Without a configured model, only the local checks run and nothing is sent. `/mock` holds example data for each contract.
