@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run Run-PurpleDragonAI.bat once to install the desktop renderer first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" verify_source.py
if errorlevel 1 goto failed
".venv\Scripts\python.exe" release_check.py
if errorlevel 1 goto failed
".venv\Scripts\python.exe" verify_windows.py
if errorlevel 1 goto failed
echo.
echo Native bridge, task and viewport checks passed. Review windows-verification.json.
echo Also check text, Tab focus and the neon artwork on your Windows screen.
pause
exit /b 0
:failed
echo Verification failed. Review the output and windows-verification.json if created.
pause
exit /b 1
