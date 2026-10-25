"""CSV mode: scrub a whole data table locally.  Owner: Selina.

Columns are treated according to the "csv" section of risk_config.json:
  - direct identifiers (ID, name, email...) become tokens such as [ID_00042];
  - quasi-identifiers are generalized (major -> field, rare categories -> "Other", date -> year,
    redundant codes suppressed);
  - everything else is kept.
The key file (keys/csv-<id>.json) holds the tokens and the original value of every generalized
cell, so restore_table() gives back the exact original table. It never leaves the machine.
The risk report compares the k distribution on the scored quasi-identifiers before and after.
"""
import io
import json
import re

import pandas as pd

from .risk import CONFIG
from .scrub import KEYS_DIR

RULES = CONFIG["csv"]
BINS = [("k = 1", 1, 1), ("k = 2-4", 2, 4), ("k = 5-19", 5, 19), ("k >= 20", 20, None)]
MISSING = {"", " ", "#NULL!", "-9"}
YEAR = re.compile(r"(19|20)\d{2}")


def classify(columns: list[str]) -> dict[str, str]:
    direct = {c.lower() for c in RULES["direct_identifiers"]}
    roles = {}
    for col in columns:
        if col.lower() in direct:
            roles[col] = "direct identifier"
        elif col in RULES["generalize"]:
            roles[col] = "quasi-identifier"
        elif col in RULES["risk_columns"]:
            roles[col] = "quasi-identifier (kept)"
        else:
            roles[col] = "kept"
    return roles


def k_distribution(df: pd.DataFrame) -> dict:
    cols = [c for c in RULES["risk_columns"] if c in df.columns]
    if not cols:
        return {"columns": [], "bins": {}}
    k = df[cols].groupby(cols)[cols[0]].transform("size")
    bins = {name: int(((k >= lo) & ((k <= hi) if hi else True)).sum()) for name, lo, hi in BINS}
    return {"columns": cols, "bins": bins}


def _generalize(col: pd.Series, spec: dict) -> pd.Series:
    present = ~col.isin(MISSING)
    rule = spec["rule"]
    if rule == "text_before_colon":
        return col.where(~present, col.str.split(":").str[0].str.strip())
    if rule == "suppress":
        return col.where(~present, "")
    if rule == "rare_to_other":
        counts = col[present].value_counts()
        rare = set(counts[counts < spec["min_count"]].index)
        return col.where(~col.isin(rare), "Other")
    if rule == "date_to_year":
        return col.where(~present, col.str.extract(YEAR, expand=False).fillna(""))
    raise ValueError(f"unknown CSV rule {rule!r}")


def scrub_table(raw: bytes, table_id: str) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False)
    roles = classify(list(df.columns))
    before = k_distribution(df)

    out = df.copy()
    key: dict = {"tokens": {}, "generalized": {}}
    for col, role in roles.items():
        if role == "direct identifier":
            tag = re.sub(r"[^A-Z0-9]", "_", col.upper())
            values = [v for v in out[col].unique() if v not in MISSING]
            mapping = {v: f"[{tag}_{i:05d}]" for i, v in enumerate(values, start=1)}
            key["tokens"].update({t: v for v, t in mapping.items()})
            out[col] = out[col].map(lambda v: mapping.get(v, v))
        elif role == "quasi-identifier":
            out[col] = _generalize(out[col], RULES["generalize"][col])
            key["generalized"][col] = df[col].tolist()

    KEYS_DIR.mkdir(exist_ok=True)
    (KEYS_DIR / f"csv-{table_id}.json").write_text(json.dumps(key))
    report = {
        "table_id": table_id,
        "rows": len(df),
        "columns": [{"name": c, "role": r, "rule": RULES["generalize"].get(c, {}).get("rule")} for c, r in roles.items()],
        "k_before": before,
        "k_after": k_distribution(out),
    }
    return out, report


def restore_table(scrubbed: pd.DataFrame, key: dict) -> pd.DataFrame:
    """Undo scrub_table with its key file: tokens back to values, generalized cells back to originals."""
    out = scrubbed.copy()
    tokens = key["tokens"]
    for col in out.columns:
        if out[col].isin(tokens).any():
            out[col] = out[col].map(lambda v: tokens.get(v, v))
    for col, original in key["generalized"].items():
        out[col] = original
    return out


def load_key(table_id: str) -> dict:
    return json.loads((KEYS_DIR / f"csv-{table_id}.json").read_text())
