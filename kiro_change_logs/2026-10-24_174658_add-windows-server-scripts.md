# Add Windows server run scripts

**Files changed:**
- backend/scripts/run-server.ps1 (new)
- backend/scripts/run-server.bat (new)

Added two Windows launcher scripts in the nested `backend/scripts/` folder so a Windows user can start the StrangerThesis backend without manual venv steps. `run-server.ps1` (PowerShell) and `run-server.bat` (cmd.exe) each resolve paths relative to the script so they run from any directory, create the `.venv` if missing (preferring Python 3.13 via the `py` launcher, since 3.14 lacks a prebuilt pydantic-core wheel), install `requirements.txt`, download the spaCy `en_core_web_sm` model only if it is not already present, then launch `uvicorn app.main:app --reload` on 127.0.0.1:8000. Everything stays local, consistent with the project's local-first privacy rule. Verified the existing venv imports FastAPI, uvicorn, spaCy, and the app cleanly, and confirmed the server boots and serves `/docs` with HTTP 200 before shutting it down.
