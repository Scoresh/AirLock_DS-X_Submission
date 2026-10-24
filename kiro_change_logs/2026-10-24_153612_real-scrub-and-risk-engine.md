# Replace scrub and risk stubs with the real local privacy check

**Files changed:**
- `backend/app/scrub.py`, `backend/app/risk.py`, `backend/app/nsse_codes.py` (new)
- `backend/app/main.py` (accepted fixes are cumulative; LLM and side-by-side view get rewritten text)
- `backend/app/schemas.py` (optional `Participant.mentions`), `mock/scrub.json`
- `backend/requirements.txt` (presidio-analyzer, spacy; then `python -m spacy download en_core_web_sm`)

`scrub.py` now tokenizes emails, phone numbers and BU IDs with regex and person names with Presidio (spaCy en_core_web_sm), reuses one token per person (a first name alone maps to the full name's token), and writes the token key only to `keys/<doc_id>.json`. Participant profiles are extracted from the scrubbed text, so evidence quotes never contain names; rules catch age ("19-year-old"), class, major ("majoring in ..."), country ("from ..."), housing, athlete status and sex. `risk.py` computes k as the sum of WEIGHT2 over matching rows of `data/NSSE-synthetic.csv`, or the fallback `population-synthetic.csv` if the real file is missing. Suggestions follow the NSSE ladder (IRage→IRagecol, country22→countrycol22→internat, MAJfirstcode→MAJfirstcol), each with its new k. Accepted fixes also rewrite the sentence itself ("from Iceland" → "from Europe" → "from abroad"), and that rewritten text is what `/review` sends to the LLM. In a test, a 19-year-old Icelandic ethnic-studies sophomore went k 1 → 4 → 74 over two "accept all" clicks, `/review` returned 403 until the gate opened, and `/llm-view` showed only tokens and vaguer wording. `Participant.mentions` is a new optional field (default empty), so existing code and mocks keep working.
