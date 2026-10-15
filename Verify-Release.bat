@echo off
setlocal
cd /d "%~dp0"
echo Purple Dragon AI Agent - Read-only Release Trust
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" release_check.py --trust
    goto finished
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 release_check.py --trust
    goto finished
)
where python >nul 2>nul
if not errorlevel 1 (
    python release_check.py --trust
    goto finished
)
echo Python 3.10 or newer is required. No packages were installed or settings changed.
pause
exit /b 1
:finished
set "PD_AI_VERIFY_EXIT=%errorlevel%"
pause
exit /b %PD_AI_VERIFY_EXIT%
