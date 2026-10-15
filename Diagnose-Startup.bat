@echo off
setlocal
cd /d "%~dp0"
echo Purple Dragon AI Agent - Read-only Startup Diagnostics
echo Local diagnostics may show paths and raw startup errors. Review before sharing.
if exist "logs\setup.log" echo Dependency setup log: logs\setup.log
if not exist ".venv\Scripts\python.exe" (
    echo Desktop environment is missing. Run Run-PurpleDragonAI.bat first.
    if exist "logs\startup-error.log" type "logs\startup-error.log"
    pause
    exit /b 1
)
".venv\Scripts\python.exe" runtime_version.py
if errorlevel 1 goto finished
".venv\Scripts\python.exe" runtime_check.py
:finished
pause
