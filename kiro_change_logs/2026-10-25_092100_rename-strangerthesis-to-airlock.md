# Rename StrangerThesis to AirLock across the repository

**Files changed:**
- `README.md`, `SUMMARY.md`
- `frontend/index.html`, `frontend/index.skeleton.html`, `frontend/app.js`, `frontend/styles.css`, `frontend/favicon.svg`
- `backend/app/main.py`, `backend/app/scrub.py`
- `backend/scripts/run_jiff_demo.py`, `backend/scripts/make_demo_thesis.py`, `backend/scripts/run-server.bat`, `backend/scripts/run-server.ps1`
- `tests/test_jiff_deployment.py`
- `jiff/public/index.html`, `jiff/package.json`
- `render.yaml`
- `.kiro/steering/project-conventions.md`, `.kiro/agents/frontend-heatmap.json`, `.kiro/agents/local-scrubbing.json`, `.kiro/agents/risk-engine.json`, `.kiro/agents/rubric-review.json`

Replaced every "StrangerThesis" reference with "AirLock" across source, frontend, docs, configs and scripts. Handled three casings consistently: the display wordmark `StrangerThesis` → `AirLock`, the all-caps JIFF banner `STRANGERTHESIS` → `AIRLOCK`, and lowercase identifiers (`strangerthesis-jiff-count` package name, the Render service name, and the JIFF temp-dir prefix) → `airlock`. Renamed the environment variables `STRANGERTHESIS_DEPLOYMENT_MODE` and `STRANGERTHESIS_KEYS_DIR` to `AIRLOCK_DEPLOYMENT_MODE` and `AIRLOCK_KEYS_DIR`, updating both their readers (`main.py`, `scrub.py`) and writers (`run_jiff_demo.py`, `test_jiff_deployment.py`) so they stay in sync. Left the three `kiro_change_logs/` files untouched because they are historical records. Verified all edited Python compiles and all edited JSON parses.
