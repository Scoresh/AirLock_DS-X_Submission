# Local format rules (BU thesis guide)

Checked by code in `backend/app/format_rules.py`, with no model. Page numbers refer to the *BU Guide for Writers of Theses and Dissertations* provided by the organizers.

| Rule | Guide page | How it is checked |
|---|---|---|
| Left margin at least 1.5 in (`left-margin`) | p.5 | Distance from the left edge to the leftmost text block (page number excluded) is at least 1.5 in. |
| Right margin at least 1 in (`right-margin`) | p.5 | Distance from the rightmost text block to the right edge is at least 1 in. |
| Top margin at least 1.5 in (`top-margin`) | p.5 | Distance from the top edge to the first text block is at least 1.5 in. |
| Bottom margin at least 1 in (`bottom-margin`) | p.5 | Distance from the last text block to the bottom edge is at least 1 in. |
| Body text 12 pt; nothing below 10 pt (`font-size`) | p.4 | The font with the most characters on the page is 12 pt; no font with 20+ characters is below 10 pt. |
| Avoid Calibri (`no-calibri`) | p.5 | No text span on the page uses a font whose name contains "Calibri". |
| One font and size throughout (`font-consistency`) | p.5 | Each page's main font and size matches the most common one in the document. |
| No page number on the left (`number-not-left`) | p.6 | The printed page number is not in the left third of the page. |
| Roman numerals at bottom center (`roman-bottom-center`) | p.6 | Pages numbered with lower-case Roman numerals have them at the bottom center. |
| Title page shows no number (`title-unnumbered`) | p.6 | The first page has no printed page number. |
| One page-number position for Arabic pages (`number-position`) | p.6 | All Arabic-numbered pages use the same position, and it is one the guide allows. |
| Abstract, table of contents, bibliography present and in order (`required-sections`) | p.7 | Pages starting with Abstract, Table of Contents and Bibliography/References exist, abstract before contents. |

Not yet checked by code: double spacing (guide p.4), page-number distance from the edge (p.6), and the order of every optional preliminary page (p.7).
