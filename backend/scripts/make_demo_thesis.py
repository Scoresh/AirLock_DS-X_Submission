"""Build the demo-day thesis: a 12-page undergraduate thesis with planted privacy and format problems.

Writes samples/demo-thesis.pdf (served by GET /sample). Everything in it is fictional.

Planted privacy problems
  Title page, acknowledgments, appendix B: names of the author, advisor, committee and an assistant;
    an email, a phone number, a BU ID and a discussion section number.
  Methods (p. 3): six participants described with details from real rows of the organizers'
    NSSE synthetic data, so their k-values come from the data:
      P2  senior, Golden bamboo lemur, Clockmaking: Theory                       k = 9   medium
      P3  senior, Gray mouse lemur, double major, transfer student               k = 1   high
      P4  first-year, Ring-tailed lemur (largest group), double major            k = 1   high
      P5  first-year, Ring-tailed lemur, Tea Sciences: Policy                    k = 331 low
      P7  first-year, Diademed sifaka, Lighthouse Engineering: Methods           k = 1   high
      P9  senior, Aye-aye, Wayfinding: Studio, transfer student                  k = 1   high

Planted format problems
  No abstract page; left margin 0.75 in on p. 4; page number top-right on p. 5;
  Appendix B set in Helvetica 11 instead of Times 12.

Run from /backend:  python scripts/make_demo_thesis.py
"""
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = ROOT / "samples" / "demo-thesis.pdf"

PT = 72
W, H = 8.5 * PT, 11 * PT
NORMAL = {"top": 1.0, "bottom": 1.0, "left": 1.5, "right": 1.0}

TITLE_PAGE = """NIGHT SHIFT:
HOW UNDERGRADUATES CHOOSE WHERE TO STUDY AFTER DARK


by

JORDAN WHITFIELD


A thesis submitted in partial fulfillment
of the requirements for the degree of
Bachelor of Arts with Honors in Sociology


Boston University
College of Arts and Sciences
2026


Approved by

First Reader: Professor Elena Marchetti
Second Reader: Dr. Samuel Okafor"""

PAGES = [
    {
        "heading": "Acknowledgments",
        "label": "ii",
        "body": [
            "This thesis would not exist without the patience of my advisor, Professor Elena Marchetti, "
            "who read every draft and asked the questions I was avoiding. Dr. Samuel Okafor and Dr. Priya "
            "Raman served on my committee and shaped the design of the interview study.",
            "I am grateful to the six students who gave up an evening to talk with me about where and why "
            "they study late at night. Their candour is the substance of this work. I also thank Maya "
            "Lindqvist, who scheduled and transcribed the interviews, and the staff of the Mugar Memorial "
            "Library, who answered many questions about building hours.",
            "Any remaining errors are my own.",
        ],
    },
    {
        "heading": "Table of Contents",
        "label": "iii",
        "body": [
            "Acknowledgments . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . ii\n"
            "Chapter 1. Introduction . . . . . . . . . . . . . . . . . . . . . . . . . . 1\n"
            "Chapter 2. Methods . . . . . . . . . . . . . . . . . . . . . . . . . . . . 2\n"
            "Chapter 3. Findings . . . . . . . . . . . . . . . . . . . . . . . . . . . 4\n"
            "Chapter 4. Discussion . . . . . . . . . . . . . . . . . . . . . . . . . . 6\n"
            "References . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 7\n"
            "Appendix A. Interview Protocol . . . . . . . . . . . . . . . . . . . . . 8\n"
            "Appendix B. Recruitment and Logistics . . . . . . . . . . . . . . . . . 9",
        ],
    },
    {
        "heading": "Chapter 1. Introduction",
        "label": "1",
        "body": [
            "Universities increasingly keep libraries, study lounges and residence hall common rooms open "
            "late into the night. Administrators justify the expense by pointing to demand, but little is "
            "known about which students use these spaces after dark, what they are looking for, and what "
            "they give up to get it.",
            "This thesis asks two questions. First, how do undergraduates choose where to study between "
            "10 PM and 2 AM? Second, how do those choices differ between first-year students, who are still "
            "learning the campus, and seniors, who have settled into routines?",
            "To answer them, I conducted semi-structured interviews with six undergraduates and combined "
            "their accounts with patterns from a large synthetic survey of student engagement. Because "
            "the interviews describe identifiable routines, the study also raises a methodological question "
            "that recurs in qualitative research: how much can a description reveal before it identifies "
            "the person it describes?",
        ],
    },
    {
        "heading": "Chapter 2. Methods",
        "label": "2",
        "body": [
            "Participants were recruited through an announcement in SO 301 Discussion Section 04 and through "
            "flyers in two residence halls. Eligible students were enrolled undergraduates who reported "
            "studying on campus after 10 PM at least twice a week during the semester.",
            "Interviews lasted between 40 and 70 minutes and followed the protocol in Appendix A. They were "
            "audio-recorded with consent, transcribed, and coded in two rounds: an open round to identify "
            "recurring themes, and a focused round organised around space, safety and social presence.",
            "To situate the interviews, I compared each participant's academic profile with the organizers' "
            "NSSE synthetic data set, which contains 20,731 fictional respondents across six survey years. "
            "The comparison is descriptive; it is not used to generalise from six interviews to a population.",
        ],
    },
    {
        "heading": "2.1 Participants",
        "label": "3",
        "body": [
            "Six students took part. Each is described below so that readers can interpret the accounts "
            "in Chapter 3.",
            "Participant 2 is a senior majoring in Clockmaking: Theory who identifies as Golden bamboo lemur. "
            "Participant 3, a senior who identifies as Gray mouse lemur, is majoring in Clockmaking: Technology "
            "with a second major in Orchard Management: Technology and transferred from another college. "
            "Participant 4 is a first-year majoring in Puzzle Design: Design with a second major in Kite "
            "Studies: Foundations who identifies as Ring-tailed lemur. "
            "Participant 5 is a first-year majoring in Tea Sciences: Policy who identifies as Ring-tailed lemur. "
            "Participant 7 is a first-year majoring in Lighthouse Engineering: Methods who identifies as "
            "Diademed sifaka. "
            "Participant 9, a senior majoring in Wayfinding: Studio, identifies as Aye-aye and transferred "
            "from another college.",
            "Participant numbers follow the order in which interviews were scheduled; numbers 1, 6 and 8 "
            "belong to students who withdrew before their interview.",
        ],
    },
    {
        "heading": "Chapter 3. Findings",
        "label": "4",
        "margins": {"top": 1.0, "bottom": 1.0, "left": 0.75, "right": 1.0},  # planted: left margin
        "body": [
            "Three themes organise the findings: the search for quiet without isolation, the role of "
            "lighting and building access in feeling safe, and the way late-night study doubles as a "
            "social ritual.",
            "Quiet without isolation. Most participants wanted a space quiet enough to concentrate but "
            "occupied enough to feel accompanied. Participant 3 described the library basement as \"the "
            "only place that felt calm during exam weeks, because everyone there was in the same boat.\" "
            "Participant 5, by contrast, avoided the library entirely after midnight and preferred a "
            "residence hall lounge where friends drifted in and out.",
            "Light and access. Seniors talked about routes rather than rooms. Participant 9 timed study "
            "sessions around the last shuttle and chose spaces near well-lit entrances. First-year "
            "participants rarely mentioned safety until asked, which suggests that concern grows with "
            "experience of the campus at night.",
        ],
    },
    {
        "heading": "3.2 Study as a Social Ritual",
        "label": ("5", "top-right"),  # planted: page number moves
        "body": [
            "For several participants, studying late was less about productivity than about belonging. "
            "Participant 4 described a standing arrangement with classmates to \"claim the long table on "
            "the third floor\" every Tuesday and Thursday. Participant 7 said the walk back from the library "
            "was the part of the evening they looked forward to most.",
            "Participant 2 framed late study as a way of marking the end of the degree: \"I know where "
            "every outlet is. In a year none of this will be mine.\" These accounts suggest that "
            "institutions which close spaces early may remove a source of community as well as a place "
            "to work.",
        ],
    },
    {
        "heading": "Chapter 4. Discussion",
        "label": "6",
        "body": [
            "The interviews suggest that late-night study spaces serve three needs at once: concentration, "
            "safety and company. Students trade between them differently as they progress, and seniors in "
            "particular plan around access rather than atmosphere.",
            "The study has clear limits. Six interviews cannot represent a student body, and the synthetic "
            "survey data describe a fictional population. A further limitation became apparent during "
            "writing: describing participants in enough detail to interpret their accounts can make them "
            "recognisable. Future work should report participant characteristics in aggregate and test "
            "descriptions against population data before publication.",
        ],
    },
    {
        "heading": "References",
        "label": "7",
        "body": [
            "Kuh, G. D. (2001). Assessing what really matters to student learning: Inside the National "
            "Survey of Student Engagement. Change, 33(3), 10-17.",
            "Narayanan, A., & Shmatikov, V. (2008). Robust de-anonymization of large sparse datasets. "
            "In Proceedings of the IEEE Symposium on Security and Privacy (pp. 111-125).",
            "Rocher, L., Hendrickx, J. M., & de Montjoye, Y.-A. (2019). Estimating the success of "
            "re-identifications in incomplete datasets using generative models. Nature Communications, 10, 3069.",
            "Samarati, P. (2001). Protecting respondents' identities in microdata release. IEEE Transactions "
            "on Knowledge and Data Engineering, 13(6), 1010-1027.",
            "Sweeney, L. (2002). k-anonymity: A model for protecting privacy. International Journal of "
            "Uncertainty, Fuzziness and Knowledge-Based Systems, 10(5), 557-570.",
        ],
    },
    {
        "heading": "Appendix A. Interview Protocol",
        "label": "8",
        "body": [
            "1. Walk me through the last evening you studied on campus after 10 PM. Where did you go first?",
            "2. What made you choose that space over others you know?",
            "3. Have you ever left a space because it felt too empty, too crowded, or unsafe?",
            "4. How do you get back to where you live afterwards?",
            "5. Who, if anyone, do you usually study with at night?",
            "6. If the university closed that space at midnight, what would you do instead?",
        ],
    },
    {
        "heading": "Appendix B. Recruitment and Logistics",
        "label": "9",
        "font": ("helv", 11),  # planted: font switch
        "body": [
            "Recruitment announcements were posted with the permission of the instructor of SO 301. "
            "Interested students contacted the researcher, Jordan Whitfield, at jwhitfield@bu.edu "
            "(BU ID U48213907) and completed a short eligibility form.",
            "Interview scheduling and transcription were handled by Maya Lindqvist (mlindq@bu.edu, "
            "617-555-0142). Recordings were stored on an encrypted drive and deleted after transcription.",
            "Participants received a $20 bookstore gift card. The study was reviewed by the Boston "
            "University Institutional Review Board under protocol 6418X (exempt category 2).",
        ],
    },
]
# Also planted: there is no abstract page after the title page.


def _label(page: fitz.Page, label, font: str, size: float) -> None:
    text, where = label if isinstance(label, tuple) else (label, "bottom-center")
    if where == "top-right":
        page.insert_text(fitz.Point(W - 1.0 * PT - 10, 0.6 * PT), text, fontname=font, fontsize=size)
    else:
        page.insert_text(fitz.Point(W / 2 - 3 * len(text), H - 0.5 * PT), text, fontname=font, fontsize=size)


def _body_page(doc: fitz.Document, spec: dict) -> None:
    page = doc.new_page(width=W, height=H)
    m = spec.get("margins", NORMAL)
    font, size = spec.get("font", ("tiro", 12))
    bold = "hebo" if font == "helv" else "tibo"
    x0, x1 = m["left"] * PT, W - m["right"] * PT
    y = m["top"] * PT
    rest = page.insert_textbox(fitz.Rect(x0, y, x1, y + 40), spec["heading"], fontname=bold, fontsize=size + 2)
    assert rest >= 0, f"heading does not fit: {spec['heading']}"
    body = fitz.Rect(x0, y + 40, x1, H - m["bottom"] * PT)
    rest = page.insert_textbox(body, "\n\n".join(spec["body"]), fontname=font, fontsize=size,
                               lineheight=1.45, align=fitz.TEXT_ALIGN_JUSTIFY)
    assert rest >= 0, f"text does not fit on page: {spec['heading']} ({rest:.0f} pt over)"
    _label(page, spec["label"], font, size)


def build() -> None:
    doc = fitz.open()
    title = doc.new_page(width=W, height=H)
    rest = title.insert_textbox(fitz.Rect(1.5 * PT, 1.6 * PT, W - 1.0 * PT, H - 1.0 * PT), TITLE_PAGE,
                                fontname="tiro", fontsize=12, lineheight=1.35, align=fitz.TEXT_ALIGN_CENTER)
    assert rest >= 0, "title page does not fit"
    for spec in PAGES:
        _body_page(doc, spec)
    doc.set_metadata({"title": "Night Shift (StrangerThesis demo document)", "author": "StrangerThesis demo"})
    PDF_PATH.parent.mkdir(exist_ok=True)
    doc.save(PDF_PATH, garbage=3, deflate=True)
    print(f"wrote {PDF_PATH} ({len(doc)} pages)")


if __name__ == "__main__":
    build()
