# Add testing_superduper.py interactive rubric-parsing test

**Files changed:**
- testing_superduper.py

Created a single-file interactive test that opens a native Windows file dialog (tkinter filedialog) so the user can select one or more rubric files, then runs each through the `rubric_parsing` pipeline (pandoc -> LLM -> validated JSON). For every file it prints the resulting `{"rubric": [...]}` JSON, writes it next to the source as `<name>.rubric.json`, and reports how many criteria were extracted. It inserts the repo root on `sys.path` so `rubric_parsing` imports when run from the project root, warns early if `LLM_BASE_URL`/`LLM_MODEL` are unset, and handles file/pandoc/LLM-config/parse errors with clear messages and a non-zero exit on failure. The script was byte-compiled and its imports (including tkinter) verified without launching the GUI, since the user supplies the input rubrics interactively. Note the package is named `rubric_parsing` (not "rubric_changes"); the test wires to the existing package.
