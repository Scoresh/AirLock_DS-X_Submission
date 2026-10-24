import sys, json, traceback
sys.path.insert(0, "backend")

from app import scrub, risk, format_rules, review, store
from app.parse import parse_pdf

PDF = r"C:\Users\score\Downloads\ECE 401 PreLab 4.pdf"

def main():
    data = open(PDF, "rb").read()
    print(f"read {len(data)} bytes")

    parsed = parse_pdf(data, "smoke")
    print(f"[parse] OK: {len(parsed.pages)} pages")
    for p in parsed.pages[:2]:
        print(f"  p{p.page}: {len(p.text)} chars, margins L={p.layout.margins_in.left} fonts={len(p.layout.fonts)}")

    scrubbed = scrub.scrub(parsed)
    print(f"[scrub] OK: {len(scrubbed.direct_identifiers)} identifiers, {len(scrubbed.participants)} participants")
    for pt in scrubbed.participants:
        print(f"  {pt.id}: attrs={pt.attributes}")

    scored = risk.score(scrubbed, [])
    print(f"[score] OK: gate_open={scored.gate_open}")
    for sp in scored.participants:
        print(f"  {sp.id}: k={sp.k} risk={sp.risk} suggestions={len(sp.suggestions)}")

    sent = risk.rewrite(scrubbed, [])
    print(f"[rewrite] OK: {len(sent.scrubbed_pages)} pages")

    findings = format_rules.run_all(parsed)
    print(f"[format_rules] OK: {len(findings)} rule findings")

    llm = review.llm_review(sent, None)
    findings += review.restore(llm, "smoke")
    print(f"[review] OK: {len(findings)} total findings")
    print("\nALL STAGES PASSED")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
