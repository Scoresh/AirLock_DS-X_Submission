# Show the real reason when the spaCy model fails to load

**Files changed:**
- `backend/app/scrub.py`

On the hosted demo the setup check reported "the spaCy model is missing" even though requirements.txt now installs it, because every failure while starting Presidio was reported as a missing model. The setup message now includes the exception type and message, so the page shows the actual cause.
