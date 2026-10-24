@echo off
REM Push all changes to GitHub
setlocal

REM Build commit message: use argument if provided, else timestamp
set "MSG=%~1"
if "%MSG%"=="" set "MSG=Update %DATE% %TIME%"

echo Staging all changes...
git add -A
if errorlevel 1 goto :error

echo Committing...
git commit -m "%MSG%"
REM commit returns error if nothing to commit; continue to push anyway

echo Pushing to origin...
git push origin HEAD
if errorlevel 1 goto :error

echo.
echo Done.
goto :eof

:error
echo.
echo ERROR: a git command failed.
exit /b 1
