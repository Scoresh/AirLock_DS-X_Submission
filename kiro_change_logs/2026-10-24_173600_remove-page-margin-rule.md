# Remove the page margin formatting rule

**Files changed:**
- backend/app/format_rules.py

Removed the left-margin check (`check_left_margin`) and its `MIN_LEFT_MARGIN_IN` constant from the code-based formatting rules. It was the only rule in `RULES`, so `RULES` is now an empty list and `run_all()` returns no rule findings; the function signature and `source="rule"` contract are unchanged, and the `/review` endpoint still runs `run_all()` safely (it just contributes nothing until new rules are added). Updated the module docstring to drop margins from the candidate list and left a comment explaining how to register future rules. Verified the backend imports cleanly, `run_all` returns `[]`, and after restarting the server `POST /review` on the mock document now returns 0 findings (previously it emitted the left-margin finding). No data contract or other module changed.
