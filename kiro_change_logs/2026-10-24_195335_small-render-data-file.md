# Make the Render data file small enough for a secret file

**Files changed:**
- `backend/app/risk.py`, `backend/scripts/make_render_data.py`, `render.yaml`

Render rejected the 1 MB secret file. `make_render_data.py` now merges identical rows into one row with a count `n` (20,731 rows become 4,678 combinations) and writes it gzip-compressed and base64-encoded as `data/NSSE-synthetic-render.txt`, about 28 KB of pasteable text. `risk.py` detects that format, uses `n` as the weight, and computes k as the sum of `n` over matching rows; the full CSV still works with a weight of 1 per row. Verified with the demo thesis that both files give identical k-values for every participant and every suggestion, before and after Apply all.
