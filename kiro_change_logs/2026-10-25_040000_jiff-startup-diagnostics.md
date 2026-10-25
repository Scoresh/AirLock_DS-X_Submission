# Preserve startup readiness diagnostics

**Files changed:** `backend/scripts/run_jiff_demo.py`, `tests/test_jiff_startup.py`, `docs/JIFF_INTEGRATION.md`.

Replaced the fixed 100-attempt startup loop with a monotonic-clock deadline, configurable through `JIFF_STARTUP_TIMEOUT` or `--startup-timeout` and defaulting to 180 seconds. Startup progress and timeout errors now retain the backend's actual setup issue instead of reporting only a generic readiness failure. Premature process exits identify the affected service and exit code, including failures after initial startup. Added regression tests for a cold start beyond the old roughly twenty-second loop, setup-cause preservation and named process failures. These changes improve diagnosis and cold-start tolerance; the specific remote deployment cause still requires its full service logs.
