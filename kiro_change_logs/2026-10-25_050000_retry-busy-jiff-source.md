# Retry a temporarily busy JIFF source

**Files changed:** `backend/app/population_check.py`, `frontend/{app.js,index.html}`, `tests/test_jiff_deployment.py`.

Live verification showed a short bridge probe can time out during another MPC batch, which incorrectly labeled configured JIFF as not enabled and left the user without a retry action. Availability now distinguishes missing configuration from temporary unavailability, keeps configured sources selectable, and offers an explicit Check availability again action. Setup checks show a checking state and preserve the backend's fail-closed review behavior. Added a regression covering busy-to-ready recovery without changing service configuration.
