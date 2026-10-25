"""Scrub a CSV from the command line and print only aggregates.

Writes data/scrubbed-<name>.csv (git-ignored) and the key file keys/csv-<id>.json.
Run from /backend:  python scripts/scrub_csv.py ../data/NSSE-synthetic.csv
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import csv_mode  # noqa: E402

src = Path(sys.argv[1])
scrubbed, report = csv_mode.scrub_table(src.read_bytes(), src.stem.lower().replace(" ", "-"))
out = Path(__file__).resolve().parents[2] / "data" / f"scrubbed-{src.stem}.csv"
scrubbed.to_csv(out, index=False)
roles = {}
for c in report["columns"]:
    roles.setdefault(c["role"], []).append(c["name"])
print(f"{report['rows']:,} rows -> {out.name}")
for role, cols in roles.items():
    shown = cols if len(cols) <= 8 else cols[:8] + [f"... {len(cols) - 8} more"]
    print(f"  {role}: {', '.join(shown)}")
n = report["rows"]
for label in ("k_before", "k_after"):
    bins = report[label]["bins"]
    print(f"  {label}: " + "  ".join(f"{k}: {v / n:.1%}" for k, v in bins.items()))
