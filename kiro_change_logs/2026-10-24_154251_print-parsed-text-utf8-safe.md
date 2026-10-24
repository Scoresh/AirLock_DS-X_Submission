# Print extracted text and make console output UTF-8 safe in testing_superduper.py

**Files changed:**
- testing_superduper.py

Updated the interactive test so it now extracts the rubric text first (via `rubric_parsing.pandoc.to_markdown`, which routes PDFs to PyMuPDF) and prints it under an `--- extracted text (sent to LLM) ---` banner before the LLM step runs, so the user can see exactly what will be sent for parsing. Split `process()` into two clear stages (extract-and-print, then LLM-to-JSON) with separate error handling for each. Added a `safe_print` helper and reconfigured stdout/stderr to UTF-8 so characters like the bullet "▪" common in rubrics no longer crash the Windows cp1252 console. Routed all remaining prints through `safe_print`. Verified by compiling the file and running `process()` directly on a real PDF rubric: the extracted text printed correctly (bullets included) and the pipeline then stopped at the expected LLM-config step since no endpoint was set.
