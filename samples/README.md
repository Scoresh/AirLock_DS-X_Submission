# Test thesis

`test-thesis.pdf` is a 4-page test document. Rebuild it (and `mock/parse.json`) with:

    cd backend && python scripts/make_test_pdf.py

## Planted privacy problems

| Where | What | Expected |
|---|---|---|
| p.2 | Participant 3: senior, Gray mouse lemur, double major (Clockmaking: Technology + Orchard Management: Technology), transfer student | k = 1, high; one "Apply all" → 7 (medium, gate opens); another → 1,234 |
| p.2 | Participant 5: first-year, Ring-tailed lemur, Tea Sciences: Policy | k = 331, low (control) |
| p.2 | Participant 7: first-year, Diademed sifaka, Lighthouse Engineering: Methods | k = 1, high; one "Apply all" → 150 |
| p.2 | Participant 9: senior, Aye-aye, Wayfinding: Studio, transfer student | k = 1, high; one "Apply all" → 176 |
| p.4 | Maya Lindqvist, mlindq@bu.edu, 617-555-0142 | all become tokens; "Maya" alone reuses the same token |

Participants are real rows of the organizers' NSSE synthetic data, so k is never 0.

## Planted formatting problems (for format_rules.py and the LLM review)

| Where | What |
|---|---|
| after p.1 | No abstract page |
| p.3 | Left margin 0.75 in (should be at least 1.5 in) |
| p.3 | Page number at top-right; other pages use bottom-center |
| p.4 | Font switches from Times-Roman 12 to Helvetica 11 |

## Writing more participants

Use this sentence shape so the rules catch every detail:

> Participant N, a senior who identifies as Aye-aye, is majoring in Wayfinding: Studio with a second major in Tea Sciences: Policy and transferred from another college.

Pick people from `data/NSSE-synthetic.csv` so their k starts at 1 or more.
