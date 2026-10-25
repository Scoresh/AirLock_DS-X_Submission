# Fix premature JIFF batch timeouts

**Files changed:**
- `backend/app/population_check.py`
- `backend/scripts/run_jiff_demo.py`
- `jiff/party.js`
- `jiff/bridge.js`
- `jiff/registrar.js`
- `frontend/app.js`
- `tests/test_population_integration.py`
- `tests/test_population_transport.py`

Reproduced the reported production error with a fictional three-participant PDF: the backend stopped waiting after 65.4 seconds while the bridge was still processing serial comparisons. The HTTP budget now covers the bounded 55-second MPC deadline for every candidate plus transport overhead. Busy replies wait up to 90 seconds before giving a clear message, and interrupted computations are never automatically replayed. The UI shows elapsed comparison time, explains that larger checks can take minutes, and no longer suggests the sample document as the fix for every service error. Hosted subprocess diagnostics now reach Render directly, with operational error codes and comparison totals instead of profile values or count results. All 69 Python tests and eight real JIFF tests passed, covering long batches, bounded busy waits, no replay after failures, stale-result rejection, and the privacy gate; the sample also completed through the local browser.
