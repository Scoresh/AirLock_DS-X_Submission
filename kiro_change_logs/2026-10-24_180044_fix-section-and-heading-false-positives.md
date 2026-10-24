# Stop tokenizing rubric headings and item numbers

**Files changed:**
- `backend/app/scrub.py`

On a grading rubric PDF, the table header "Points Criteria Section" followed by "0.2" on the next line was read as a course section ("Section 0"), and spaCy's "Cover Page" was tokenized as a person. Course sections now only match on one line, when preceded by Lab, Lecture, Discussion or Recitation or followed by a colon or #, and never when the number continues as a decimal ("Section 3.1"); "see section 2" is no longer replaced. The list of words that mark a heading rather than a person now includes cover, page, title, abstract, rubric, criteria, points, methods, results and similar document words. Result: the rubric PDF has nothing replaced, the ECE 401 lab report still has its four names and "LAB Section: 04" replaced, and the test thesis is unchanged.
