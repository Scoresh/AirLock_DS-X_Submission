<#
.SYNOPSIS
    AirLock - run the backend server on Windows (PowerShell).

.DESCRIPTION
    Creates/uses a local virtual environment, installs dependencies, downloads
    the spaCy model if needed, then launches the FastAPI app with uvicorn.

.EXAMPLE
    # From any directory:
    powershell -ExecutionPolicy Bypass -File backend\scripts\run-server.ps1
#>

$ErrorActionPreference = "Stop"

# --- Resolve paths relative to this script, so it runs from anywhere ---------
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$VenvDir    = Join-Path $BackendDir ".venv"
$VenvPy     = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $BackendDir "requirements.txt"

Write-Host "[AirLock] Backend directory: $BackendDir"

# --- Pick a Python interpreter to build the venv with ------------------------
# Prefer 3.13 (README note: 3.14 lacks a prebuilt pydantic-core wheel).
function Get-BootstrapPython {
    foreach ($candidate in @(
        @{ Exe = "py";     Args = @("-3.13") },
        @{ Exe = "py";     Args = @("-3")    },
        @{ Exe = "python"; Args = @()        }
    )) {
        $cmd = Get-Command $candidate.Exe -ErrorAction SilentlyContinue
        if ($cmd) {
            try {
                & $candidate.Exe @($candidate.Args + "--version") *> $null
                if ($LASTEXITCODE -eq 0) { return $candidate }
            } catch { }
        }
    }
    return $null
}

# --- Create the virtual environment if it is missing -------------------------
if (-not (Test-Path $VenvPy)) {
    $bootstrap = Get-BootstrapPython
    if (-not $bootstrap) {
        Write-Error "No Python found. Install Python 3.13 from https://www.python.org/downloads/"
        exit 1
    }
    Write-Host "[AirLock] Creating virtual environment with: $($bootstrap.Exe) $($bootstrap.Args -join ' ')"
    & $bootstrap.Exe @($bootstrap.Args + @("-m", "venv", $VenvDir))
    if ($LASTEXITCODE -ne 0) { Write-Error "venv creation failed."; exit 1 }
} else {
    Write-Host "[AirLock] Using existing virtual environment."
}

# --- Install / update dependencies -------------------------------------------
Write-Host "[AirLock] Installing dependencies from requirements.txt ..."
& $VenvPy -m pip install --upgrade pip | Out-Null
& $VenvPy -m pip install -r $Requirements
if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed."; exit 1 }

# --- Ensure the spaCy English model is present -------------------------------
& $VenvPy -c "import spacy; spacy.load('en_core_web_sm')" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[AirLock] Downloading spaCy model en_core_web_sm ..."
    & $VenvPy -m spacy download en_core_web_sm
    if ($LASTEXITCODE -ne 0) { Write-Error "spaCy model download failed."; exit 1 }
}

# --- Launch the server -------------------------------------------------------
Write-Host ""
Write-Host "[AirLock] Starting server at http://127.0.0.1:8000  (docs: /docs)"
Write-Host "[AirLock] Press Ctrl+C to stop."
Write-Host ""
Push-Location $BackendDir
try {
    & $VenvPy -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
} finally {
    Pop-Location
}
