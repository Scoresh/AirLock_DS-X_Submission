# Add coordination rules and shared resource references to all four pipeline agents

**Files changed:**
- .kiro/agents/rubric-review.json
- .kiro/agents/risk-engine.json
- .kiro/agents/local-scrubbing.json
- .kiro/agents/frontend-heatmap.json

Added an identical "Coordination rules (shared by all agents)" clause to the end of each agent's `prompt` so every owner follows the same interoperability contract: do not change `backend/app/schemas.py` without telling the team, update the matching `mock/*.json` in the same commit as any contract change, treat the privacy gate check in `main.py` as the single source of truth that must never be bypassed, and have each stage read the prior stage's output from `store.DocState` by `doc_id` and return the exact shape defined in `schemas.py`. Also extended each agent's `resources` array with `file://backend/app/schemas.py`, `file://mock/*.json`, and `file://backend/requirements.txt` so the shared data contracts, mock examples, and library/pin list are always in context. This was done to make the four development-time agents build in parallel against one stable contract without breaking each other. The fifth agent (`ds-x-hackathon.json`) was intentionally left unchanged since it is the logging agent, not a pipeline owner. All four edited files were validated as parseable JSON.
