@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run Run-PurpleDragonAI.bat once to prepare the new release first.
    pause
    exit /b 1
)
echo Close Purple Dragon AI Agent before importing previous settings.
echo This imports configuration and retains the existing workspace location.
echo It does not copy old application files or dependencies.
".venv\Scripts\python.exe" migrate_settings.py
set "PD_AI_UPGRADE_EXIT=%errorlevel%"
pause
exit /b %PD_AI_UPGRADE_EXIT%
