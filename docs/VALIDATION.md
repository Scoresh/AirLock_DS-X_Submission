# Validation on the demo thesis

`samples/demo-thesis.pdf` (12 pages) has format errors planted on purpose. Each rule ran on it; PDF page numbers below.

| Rule | Planted on | Found on | Result |
|---|---|---|---|
| Left margin at least 1.5 in | [7] | [7] | correct |
| Right margin at least 1 in | - | - | correct |
| Top margin at least 1.5 in | - | - | correct |
| Bottom margin at least 1 in | - | - | correct |
| Body text 12 pt; nothing below 10 pt | [12] | [12] | correct |
| Avoid Calibri | - | - | correct |
| One font and size throughout | [12] | [12] | correct |
| No page number on the left | - | - | correct |
| Roman numerals at bottom center | [3] | [3] | correct |
| Title page shows no number | - | - | correct |
| One page-number position for Arabic pages | [8] | [8] | correct |
| Abstract, table of contents, bibliography present and in order | [2] | [2] | correct |

**6 of 6 planted errors found, 0 false alarms.**

Regenerate with `python scripts/validate_rules.py` after changing a rule.
