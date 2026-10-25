# Risk rules in a config file, dataset-wide risk report, and tests

**Files changed:**
- `backend/app/risk_config.json` (new), `backend/app/risk.py`
- `backend/scripts/risk_report.py` (new), `docs/RISK_REPORT.md` (new), `docs/img/uniqueness_curve.png`, `docs/img/k_distribution.png` (new)
- `backend/scripts/make_fixtures.py` (new), `tests/fixtures/nsse_fixture.csv` (new, Faker), `tests/conftest.py`, `tests/test_risk.py` (new), `pytest.ini`, `backend/requirements-dev.txt` (new)

Quasi-identifiers, value labels and the generalization ladder moved from risk.py into risk_config.json; results on the demo thesis are unchanged. risk_report.py computes, for all 20,731 respondents, the share that is unique or high risk as details are added (class and affiliation 0%, plus major 1.5%, plus second major and transfer history 14.9% unique and 25% under k = 5) and the k distribution at each generalization level (unique falls from 14.9% to 0.0%; low risk rises from 51.8% to 99.0%), with two charts. Tests run on a Faker fixture with planted groups of 1, 3, 7 and 25 respondents and cover exact k-values, the thresholds, the ladder, the gate, applied fixes and the compressed Render data format; 17 pass.
