# Fix spaCy tokenizer OverflowError by pinning preshed==3.0.9

**Files changed:**
- backend/requirements.txt
- backend/.venv (rebuilt on Python 3.12.10)

The `/scrub` path crashed with `OverflowError: Python int too large to convert to C ssize_t`, raised from `spacy/tokenizer.pyx:239` (`del self._specials[k]`) inside `Tokenizer._flush_specials`. I reproduced it with a blank `English()` tokenizer and no model, which ruled out the model, numpy, murmurhash/cymem, and the Python minor version (it failed on both 3.13 and 3.12). Reading `preshed/maps.pxd` showed `key_t` is `uint64_t`, and the published `preshed` 3.0.11–3.0.14 wheels were built with a Cython that converts uint64 keys through a signed `Py_ssize_t`, overflowing for keys >= 2**63. Pinning `preshed==3.0.9` (the last wheel with a correct unsigned conversion) fixes it; `spacy.load("en_core_web_sm")` and the project's `scrub._analyzer()` Presidio path now load and tag entities correctly. Along the way the venv was rebuilt on Python 3.12.10 and dependencies reinstalled from prebuilt wheels. Verified with the blank-tokenizer repro, full model NER, `pip check` (no broken requirements), the Presidio analyze call, and a live uvicorn boot returning HTTP 200 on `/docs`. Added an explanatory comment in requirements.txt warning not to bump preshed without re-testing the model load, and cleaned up the stale `.venv_old_*` folder.
