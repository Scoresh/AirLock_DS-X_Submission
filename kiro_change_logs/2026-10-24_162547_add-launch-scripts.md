# Add launch scripts for every runnable component

**Files changed:**
- scripts/setup.bat
- scripts/run-backend.bat
- scripts/run-rubric-cli.bat
- scripts/run-rubric-test.bat
- scripts/set-llm-env.bat
- scripts/README.md
- .env.example

Surveyed the whole directory and generated Windows `.bat` launchers for every runnable part of Stranger Mode. `setup.bat` creates `backend\.venv`, installs `requirements.txt` plus `pymupdf`, and verifies `libdump\pandoc.exe`. `run-backend.bat` starts the FastAPI/uvicorn server (UI + docs). `run-rubric-cli.bat` runs `python -m rubric_parsing` on a file argument, and `run-rubric-test.bat` launches the interactive file-dialog test. `set-llm-env.bat` interactively writes a git-ignored `.env` with the OpenAI-compatible LLM settings (defaults to local Ollama; the API key is only stored locally, never hardcoded). Every run script activates the venv if present and auto-loads `.env`. Added `.env.example` as a template and `scripts/README.md` documenting the scripts and a typical first-run order. Verified the CLI launcher's usage path, argument passing (quoted path with PyMuPDF PDF extraction), and `.env` loading all work; the pipeline correctly reaches the LLM call step. The matching schema/mock contracts were not touched, so no contract change was involved.
