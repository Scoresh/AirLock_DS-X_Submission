"""Dataset-wide re-identification risk: writes docs/RISK_REPORT.md and two charts in docs/img/.

Aggregates only. For every respondent, k is the size of their equivalence class: the number of
respondents who share the same values on the chosen quasi-identifiers (a missing value counts
as its own value). We report
  1. a uniqueness curve: the share of respondents with k = 1 and k < 5 as details are added;
  2. the k distribution (k = 1, 2-4, 5-19, 20+) at each generalization level of risk_config.json.

Run from /backend:  python scripts/risk_report.py
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import risk  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
IMG = DOCS / "img"
BINS = [("k = 1 (unique)", 1, 1), ("k = 2-4 (high)", 2, 4), ("k = 5-19 (medium)", 5, 19), ("k >= 20 (low)", 20, None)]

PINE, BRICK, OCHRE, GREEN, INK = "#294D43", "#9A3A2C", "#7D5A10", "#2F6145", "#282C29"


def class_sizes(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """k for every respondent on the given columns."""
    key = df[cols].fillna("(none)").astype(str)
    return key.groupby(cols)[cols[0]].transform("size")


def distribution(k: pd.Series) -> dict[str, int]:
    return {name: int(((k >= lo) & ((k <= hi) if hi else True)).sum()) for name, lo, hi in BINS}


def population_with_extras() -> pd.DataFrame:
    """Scored quasi-identifiers plus two that a thesis rarely mentions, for the curve only."""
    df = risk.population().copy()
    raw = pd.read_csv(risk.DATA_FILE, na_values=["#NULL!", " ", "-9"], low_memory=False,
                      usecols=["Year", "program"])
    df["Year"], df["program"] = raw["Year"].astype(str), raw["program"]
    return df


CURVE = [
    ("Class year", ["Class"]),
    ("+ affiliation", ["Class", "affiliation"]),
    ("+ major", ["Class", "affiliation", "MAJfirst"]),
    ("+ second major", ["Class", "affiliation", "MAJfirst", "MAJsecond"]),
    ("+ transfer history", ["Class", "affiliation", "MAJfirst", "MAJsecond", "begincol"]),
    ("+ survey year", ["Class", "affiliation", "MAJfirst", "MAJsecond", "begincol", "Year"]),
    ("+ program", ["Class", "affiliation", "MAJfirst", "MAJsecond", "begincol", "Year", "program"]),
]

LEVELS = [
    ("0. Exact details", ["Class", "affiliation", "MAJfirst", "MAJsecond", "begincol"]),
    ("1. Major -> field", ["Class", "affiliation", "MAJfirstfield", "MAJsecond", "begincol"]),
    ("2. + second major -> field", ["Class", "affiliation", "MAJfirstfield", "MAJsecondfield", "begincol"]),
    ("3. + second major -> 'double major'", ["Class", "affiliation", "MAJfirstfield", "MAJnum", "begincol"]),
    ("4. + affiliation omitted", ["Class", "MAJfirstfield", "MAJnum", "begincol"]),
    ("5. + transfer history omitted", ["Class", "MAJfirstfield", "MAJnum"]),
]


def main() -> None:
    df = population_with_extras()
    n = len(df)
    IMG.mkdir(parents=True, exist_ok=True)

    curve = []
    for label, cols in CURVE:
        k = class_sizes(df, cols)
        curve.append((label, (k == 1).mean(), (k < 5).mean(), int(k.median())))

    levels = []
    for label, cols in LEVELS:
        levels.append((label, distribution(class_sizes(df, cols))))

    # Chart 1: uniqueness curve
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=160)
    xs = range(len(curve))
    ax.plot(xs, [c[1] * 100 for c in curve], marker="o", color=BRICK, lw=2, label="unique (k = 1)")
    ax.plot(xs, [c[2] * 100 for c in curve], marker="s", color=OCHRE, lw=2, label="high risk (k < 5)")
    ax.set_xticks(list(xs), [c[0] for c in curve], rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("% of 20,731 respondents")
    ax.set_ylim(0, 100)
    ax.set_title("Each ordinary detail makes more respondents unique", fontsize=11, color=INK)
    for x, c in zip(xs, curve):
        ax.annotate(f"{c[1]:.0%}", (x, c[1] * 100), textcoords="offset points", xytext=(0, 7),
                    ha="center", fontsize=8, color=BRICK)
    ax.grid(axis="y", alpha=.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(IMG / "uniqueness_curve.png")
    plt.close(fig)

    # Chart 2: k distribution per generalization level (stacked)
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=160)
    colors = [BRICK, "#C9826F", OCHRE, GREEN]
    left = [0] * len(levels)
    for (name, _, _), color in zip(BINS, colors):
        vals = [lv[1][name] / n * 100 for lv in levels]
        ax.barh([lv[0] for lv in levels], vals, left=left, color=color, label=name)
        left = [a + b for a, b in zip(left, vals)]
    ax.invert_yaxis()
    ax.set_xlabel("% of respondents")
    ax.set_xlim(0, 100)
    ax.set_title("Generalization moves respondents out of the high-risk bands", fontsize=11, color=INK)
    ax.legend(frameon=False, fontsize=8, ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.32))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(IMG / "k_distribution.png")
    plt.close(fig)

    lines = [
        "# Re-identification risk in the NSSE synthetic data",
        "",
        f"Generated by `backend/scripts/risk_report.py` from aggregates over all {n:,} respondents. "
        "For each respondent, **k** is how many respondents share exactly the same values on the chosen "
        "details (a missing value counts as its own value). k = 1 means the description fits one person.",
        "",
        "## 1. Uniqueness grows quickly as ordinary details are added",
        "",
        "![Uniqueness curve](img/uniqueness_curve.png)",
        "",
        "| Details used | Unique (k = 1) | High risk (k < 5) | Median k |",
        "|---|---|---|---|",
    ]
    lines += [f"| {label} | {u:.1%} | {h:.1%} | {med:,} |" for label, u, h, med in curve]
    lines += [
        "",
        "Survey year and program are not scored by the engine (a thesis rarely states them), "
        "but they show how quickly risk compounds when they are.",
        "",
        "## 2. k distribution before and after generalization",
        "",
        "Each level applies one more rule from `backend/app/risk_config.json` to every respondent.",
        "",
        "![k distribution](img/k_distribution.png)",
        "",
        "| Level | " + " | ".join(name for name, _, _ in BINS) + " |",
        "|---|" + "---|" * len(BINS),
    ]
    for label, dist in levels:
        lines.append(f"| {label} | " + " | ".join(f"{dist[name]:,} ({dist[name] / n:.1%})" for name, _, _ in BINS) + " |")
    lines += [
        "",
        "## How to read this",
        "",
        "- The data is synthetic and fictional by design (invented majors, lemur species standing in for an "
        "identity group), so these are estimates of how identifying such details are, not counts of real students.",
        "- The privacy gate blocks a document while any described participant has k < 5 "
        "(high: 1-4, medium: 5-19, low: 20+).",
        "- Generalization trades specificity for safety: each step in section 2 is a sentence the author "
        "would have to write less precisely.",
    ]
    (DOCS / "RISK_REPORT.md").write_text("\n".join(lines) + "\n")
    print(f"wrote docs/RISK_REPORT.md and 2 charts for {n:,} respondents")
    for label, u, h, med in curve:
        print(f"  {label:<22} unique {u:6.1%}  k<5 {h:6.1%}  median k {med:,}")
    for label, dist in levels:
        print(f"  {label:<38} " + "  ".join(f"{name.split(' (')[0]}: {dist[name] / n:5.1%}" for name, _, _ in BINS))


if __name__ == "__main__":
    main()
