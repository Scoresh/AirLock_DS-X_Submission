@echo off
REM ============================================================================
REM AirLock - run the backend server on Windows (cmd.exe)
REM
REM Creates/uses a local virtual environment, installs dependencies, downloads
REM the spaCy model if needed, then launches the FastAPI app with uvicorn.
REM
REM Usage (double-click, or from any directory):
REM     backend\scripts\run-server.bat
REM ============================================================================
setlocal enabledelayedexpansion

REM --- Resolve paths relative to this script, so it runs from anywhere -------
REM %~dp0 = directory of this .bat (backend\scripts\). BACKEND is its parent.
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.." || (echo Could not enter backend directory. & exit /b 1)
set "BACKEND_DIR=%CD%"

set "VENV_DIR=%BACKEND_DIR%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

echo [AirLock] Backend directory: %BACKEND_DIR%

REM --- Pick a Python interpreter to build the venv with ---------------------
REM Prefer 3.13 (README note: 3.14 lacks a prebuilt pydantic-core wheel).
set "BOOTSTRAP_PY="
py -3.13 --version >nul 2>&1 && set "BOOTSTRAP_PY=py -3.13"
if not defined BOOTSTRAP_PY (
    py -3 --version >nul 2>&1 && set "BOOTSTRAP_PY=py -3"
)
if not defined BOOTSTRAP_PY (
    python --version >nul 2>&1 && set "BOOTSTRAP_PY=python"
)

REM --- Create the virtual environment if it is missing ----------------------
if not exist "%VENV_PY%" (
    if not defined BOOTSTRAP_PY (
        echo [ERROR] No Python found. Install Python 3.13 from https://www.python.org/downloads/
        popd & exit /b 1
    )
    echo [AirLock] Creating virtual environment with: %BOOTSTRAP_PY%
    %BOOTSTRAP_PY% -m venv "%VENV_DIR%" || (echo [ERROR] venv creation failed. & popd & exit /b 1)
) else (
    echo [AirLock] Using existing virtual environment.
)

REM --- Install / update dependencies ----------------------------------------
echo [AirLock] Installing dependencies from requirements.txt ...
"%VENV_PY%" -m pip install --upgrade pip >nul
"%VENV_PY%" -m pip install -r "%BACKEND_DIR%\requirements.txt" || (echo [ERROR] pip install failed. & popd & exit /b 1)

REM --- Ensure the spaCy English model is present ----------------------------
"%VENV_PY%" -c "import spacy; spacy.load('en_core_web_sm')" >nul 2>&1
if errorlevel 1 (
    echo [AirLock] Downloading spaCy model en_core_web_sm ...
    "%VENV_PY%" -m spacy download en_core_web_sm || (echo [ERROR] spaCy model download failed. & popd & exit /b 1)
)

REM --- Launch the server ----------------------------------------------------
echo.
echo [AirLock] Starting server at http://127.0.0.1:8000  (docs: /docs)
echo [AirLock] Press Ctrl+C to stop.
echo.
"%VENV_PY%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

popd
endlocal
