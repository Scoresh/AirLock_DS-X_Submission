# Remove a committed virtual environment and scope the preshed pin to Windows

**Files changed:**
- `backend/.venv_old_20261024_180010/` (2,977 files, untracked), `uvicorn.err.log`, `uvicorn.out.log`, `_uv.err.log`, `_uv.out.log` (untracked)
- `.gitignore`, `backend/requirements.txt`

A backup of a Windows virtual environment and four server logs had been committed to main, adding about 650,000 lines and 20 MB DLLs to the repository. They are removed from git (not from anyone's disk) and `.venv*/` and `*.log` are now ignored, except the Kiro audit log. The `preshed==3.0.9` pin fixes the spaCy OverflowError on Windows but has no prebuilt wheel for macOS with Python 3.13, so it would have broken installs on Mac; it now applies only on Windows. Verified on the merged main: requirements install, setup reports ready, and the demo thesis runs end to end (10 identifiers, six participants, gate opens after Apply all, four local rule findings).
