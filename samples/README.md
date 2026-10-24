# Demo thesis (demo day)

`demo-thesis.pdf` is a 12-page fictional sociology thesis, "Night Shift". It is what **Open sample document** loads.
Rebuild it with `cd backend && python scripts/make_demo_thesis.py`.

| Where | Planted | Expected |
|---|---|---|
| p.1 title, p.2 acknowledgments, p.12 appendix | Author (in capitals on the title page), advisor, two committee members, an assistant; two emails, a phone number, a BU ID; "Discussion Section 04" (p.5) | All replaced with tokens; names in References and "Mugar Memorial Library" are left alone |
| p.6 Participants | Six participants from real rows of the organizers' data | P3, P4, P7, P9 high (k = 1); P2 medium (k = 9); P5 low (k = 331). One "Apply all" opens the gate with P3 still medium (k = 7) |
| after p.1 | No abstract page | Format finding |
| p.7 | Left margin 0.75 in | Format finding with a highlighted strip |
| p.8 | Page number top-right | Format finding |
| p.12 | Helvetica 11 instead of Times 12 | Format finding |

Demo line for P4: they identify with the largest group (Ring-tailed lemur), yet their double major alone makes them unique.

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
