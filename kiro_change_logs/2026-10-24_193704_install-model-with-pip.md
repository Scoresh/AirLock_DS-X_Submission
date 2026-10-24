# Install the spaCy model with pip and find Render's secret data file automatically

**Files changed:**
- `backend/requirements.txt`, `backend/app/risk.py`, `render.yaml`, `README.md`

Setups kept failing the new setup check because the spaCy model needed a separate `python -m spacy download` step that was easy to miss, especially when a Render service was created by hand with only `pip install -r requirements.txt`. The model is now listed in requirements.txt as a direct wheel link, so one pip install brings it in. risk.py now looks for the data in `NSSE_DATA_FILE`, then `data/NSSE-synthetic.csv`, then Render's secret-file mount `/etc/secrets/NSSE-synthetic.csv`, so on Render adding the secret file is enough. Checked: pip resolves the requirements and the local setup still reports ready.
