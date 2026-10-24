# Add tech stack table and fix setup steps in README

**Files changed:**
- `README.md`

Added a tech stack table that says which tool does each job and that everything except the future rubric-review LLM call runs locally. Name detection is Presidio with spaCy's small local model, not an LLM. Updated the setup steps: use Python 3.13, because Python 3.14 has no prebuilt pydantic-core package and the install fails. Setup now also downloads the spaCy model and generates the fallback population. The intro now says which parts are real (scrub, risk) and which still return mock data (parse, review), and points to the test thesis in `samples/`.
