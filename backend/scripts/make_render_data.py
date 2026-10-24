"""Write data/NSSE-synthetic-render.txt: a small copy of the data for a Render secret file.

Only the columns risk.py reads, with identical rows merged into one row and a count "n"
(20,731 rows -> a few thousand), then gzip + base64 so it can be pasted as text. risk.py
reads this format directly and gives the same k-values. Do not commit the output.
Run from /backend:  python scripts/make_render_data.py
"""
import base64
import gzip
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data"
COLUMNS = ["Class", "affiliation", "MAJfirst", "MAJsecond", "MAJnum", "begincol"]

df = pd.read_csv(DATA / "NSSE-synthetic.csv", usecols=COLUMNS, dtype=str, keep_default_na=False)
counts = df.groupby(COLUMNS, dropna=False).size().reset_index(name="n")
text = base64.b64encode(gzip.compress(counts.to_csv(index=False).encode())).decode()
out = DATA / "NSSE-synthetic-render.txt"
out.write_text(text)
print(f"wrote {out}: {len(counts):,} combinations from {len(df):,} rows, {len(text):,} characters")
