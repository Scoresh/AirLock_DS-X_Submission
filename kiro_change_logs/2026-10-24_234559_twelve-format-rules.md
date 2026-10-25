# Twelve format rules from the BU thesis guide, validated on the demo thesis

**Files changed:**
- `backend/app/format_rules.py`, `backend/scripts/validate_rules.py` (new), `docs/RULES_CHECKLIST.md` (new), `docs/VALIDATION.md` (new)
- `backend/scripts/make_demo_thesis.py`, `samples/demo-thesis.pdf`, `samples/README.md`, `tests/test_format_rules.py` (new)

The local rules grew from 4 to 12, each citing the page of the BU guide it comes from: left, right, top and bottom margins (p.5), 12-point body text and nothing below 10 point (p.4), avoid Calibri and keep one font (p.5), no page number on the left, Roman numerals at bottom center, an unnumbered title page and one Arabic page-number position (p.6), and abstract, table of contents and bibliography present and in order (p.7). The demo thesis used a 1-inch top margin, which the guide forbids, so it is regenerated with 1.5 inches and gains one planted error (a Roman numeral at bottom right). On the demo thesis all 6 planted errors are found with no false alarms; privacy results are unchanged. 31 tests pass.
