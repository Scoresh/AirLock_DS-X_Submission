# README, computed test results, risk by group, and ethics

**Files changed:**
- `README.md` (rewritten), `docs/ETHICS.md` (new), `docs/TEST_RESULTS.md` (new), `backend/scripts/test_results.py` (new)
- `backend/scripts/risk_report.py`, `docs/RISK_REPORT.md` (section 3: risk by affiliation group)

The README now explains the pipeline step by step, the headline results with links, how to run the app on macOS and Windows with Python 3.13, how to configure the review model, and how to reproduce every analysis and test. test_results.py computes detection on the planted identifiers (13 of 13 replaced, none left visible, no false positives), participant scoring (6 of 6 correct), format rules, the CSV round trip and the test run. The risk report adds who carries the risk: the smallest affiliation group is unique 26.3% of the time against 11.2% for the largest. ETHICS.md covers data sourcing, privacy by design, that fairness finding, limitations and misuse. 37 tests pass.
