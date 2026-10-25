# Rewrite rubric panel copy to describe the grading system

**Files changed:**
- `frontend/app.js`

Replaced the instructional "load the JSON produced by the rubric parser" copy in `renderRubricPanel()` with wording that describes how the rubric grading system functions. The no-rubric intro now explains that the system turns a grading rubric into a checklist, lists each criterion in a table, has the configured model mark fulfilment with a comment, flags criteria it cannot judge, and sends only tokenized gate-approved text. The error-state intro got a matching one-line description, and the controls hint and empty-state hint were updated to describe parsing a rubric into criteria and checking the document, removing the stale "load a saved JSON file" references left over after the JSON button was removed. No logic changed. Node is not installed here, so the edit was verified by review.
