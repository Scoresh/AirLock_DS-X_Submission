"""Write data/NSSE-synthetic-render.csv: only the columns risk.py reads (about 1 MB).

Paste its contents into Render as the secret file NSSE-synthetic.csv. Do not commit it.
Run from /backend:  python scripts/make_render_data.py
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data"
COLUMNS = ["Class", "affiliation", "MAJfirst", "MAJsecond", "MAJnum", "begincol"]

df = pd.read_csv(DATA / "NSSE-synthetic.csv", usecols=COLUMNS, dtype=str, keep_default_na=False)
out = DATA / "NSSE-synthetic-render.csv"
df.to_csv(out, index=False)
print(f"wrote {out} ({out.stat().st_size:,} bytes, {len(df):,} rows)")
