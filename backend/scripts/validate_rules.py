"""Write docs/RULES_CHECKLIST.md and docs/VALIDATION.md for the local format rules.

VALIDATION.md runs every rule on samples/demo-thesis.pdf and compares what was found with what
was planted (scripts/make_demo_thesis.py), so missed errors and false alarms are both visible.
Run from /backend:  python scripts/validate_rules.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import format_rules  # noqa: E402
from app.parse import parse_pdf  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "samples" / "demo-thesis.pdf"

HOW = {
    "left-margin": "Distance from the left edge to the leftmost text block (page number excluded) is at least 1.5 in.",
    "right-margin": "Distance from the rightmost text block to the right edge is at least 1 in.",
    "top-margin": "Distance from the top edge to the first text block is at least 1.5 in.",
    "bottom-margin": "Distance from the last text block to the bottom edge is at least 1 in.",
    "font-size": "The font with the most characters on the page is 12 pt; no font with 20+ characters is below 10 pt.",
    "no-calibri": "No text span on the page uses a font whose name contains \"Calibri\".",
    "font-consistency": "Each page's main font and size matches the most common one in the document.",
    "number-not-left": "The printed page number is not in the left third of the page.",
    "roman-bottom-center": "Pages numbered with lower-case Roman numerals have them at the bottom center.",
    "title-unnumbered": "The first page has no printed page number.",
    "number-position": "All Arabic-numbered pages use the same position, and it is one the guide allows.",
    "required-sections": "Pages starting with Abstract, Table of Contents and Bibliography/References exist, abstract before contents.",
}

# What make_demo_thesis.py plants: rule id -> pages (PDF page numbers).
PLANTED = {
    "required-sections": [2],     # no abstract page
    "roman-bottom-center": [3],   # "iii" at bottom right
    "left-margin": [7],           # 0.75 in
    "number-position": [8],       # "5" at top right
    "font-size": [12],            # Helvetica 11
    "font-consistency": [12],     # Helvetica 11
}


def main() -> None:
    rows = format_rules.checklist(parse_pdf(DEMO.read_bytes(), "validate"))

    check = ["# Local format rules (BU thesis guide)", "",
             "Checked by code in `backend/app/format_rules.py`, with no model. Page numbers refer to "
             "the *BU Guide for Writers of Theses and Dissertations* provided by the organizers.", "",
             "| Rule | Guide page | How it is checked |", "|---|---|---|"]
    check += [f"| {r['title']} (`{r['id']}`) | p.{r['guide_page']} | {HOW[r['id']]} |" for r in rows]
    check += ["", "Not yet checked by code: double spacing (guide p.4), page-number distance from the edge "
              "(p.6), and the order of every optional preliminary page (p.7)."]
    (ROOT / "docs" / "RULES_CHECKLIST.md").write_text("\n".join(check) + "\n")

    found_all = missed_all = false_all = 0
    val = ["# Validation on the demo thesis", "",
           "`samples/demo-thesis.pdf` (12 pages) has format errors planted on purpose. "
           "Each rule ran on it; PDF page numbers below.", "",
           "| Rule | Planted on | Found on | Result |", "|---|---|---|---|"]
    for r in rows:
        planted, found = set(PLANTED.get(r["id"], [])), set(r["pages"])
        hit, missed, extra = planted & found, planted - found, found - planted
        found_all, missed_all, false_all = found_all + len(hit), missed_all + len(missed), false_all + len(extra)
        result = ("correct" if not missed and not extra else
                  ", ".join(filter(None, [missed and f"missed {sorted(missed)}", extra and f"false alarm {sorted(extra)}"])))
        val.append(f"| {r['title']} | {sorted(planted) or '-'} | {sorted(found) or '-'} | {result} |")
    val += ["", f"**{found_all} of {found_all + missed_all} planted errors found, {false_all} false alarms.**", "",
            "Regenerate with `python scripts/validate_rules.py` after changing a rule."]
    (ROOT / "docs" / "VALIDATION.md").write_text("\n".join(val) + "\n")
    print(f"{len(rows)} rules; planted errors found {found_all}/{found_all + missed_all}; false alarms {false_all}")


if __name__ == "__main__":
    main()
