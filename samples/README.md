# Test thesis

`test-thesis.pdf` is a 4-page test document. Rebuild it (and `mock/parse.json`) with:

    cd backend && python scripts/make_test_pdf.py

## Planted privacy problems

| Where | What | Expected |
|---|---|---|
| p.2 | Participant 3: 19-year-old sophomore, ethnic studies, from Iceland, campus housing | k = 1, high; after 2 "accept all" clicks k = 74 |
| p.2 | Participant 5: senior, economics, off campus | k = 69, low (control) |
| p.2 | Participant 7: 20-year-old sophomore, biomedical engineering, from Sweden, campus housing | k = 1, high; then 2, then 32 |
| p.2 | Participant 9: 19-year-old first-year, physics, campus housing, varsity athlete | k = 1, high; then 20 |
| p.4 | Maya Lindqvist, mlindq@bu.edu, 617-555-0142 | all become tokens; "Maya" alone reuses the same token |

Participants are real rows of the fallback population, so k is never 0.

## Planted formatting problems (for format_rules.py and the LLM review)

| Where | What |
|---|---|
| after p.1 | No abstract page |
| p.3 | Left margin 0.75 in (should be at least 1.5 in) |
| p.3 | Page number at top-right; other pages use bottom-center |
| p.4 | Font switches from Times-Roman 12 to Helvetica 11 |

## Writing more participants

Use this sentence shape so the rules catch every detail:

> Participant N, a 19-year-old sophomore majoring in ethnic studies from Iceland, lives in campus housing.

Pick people from `data/population-synthetic.csv` so their k starts at 1 or more.
