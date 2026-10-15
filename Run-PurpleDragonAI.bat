@echo off
setlocal
cd /d "%~dp0"
set "PD_AI_PROJECT_DIR=%CD%"
set "PD_AI_ENV_PYTHON=%CD%\.venv\Scripts\python.exe"
if exist "%PD_AI_ENV_PYTHON%" (
    "%PD_AI_ENV_PYTHON%" -c "import sys; assert sys.version_info >= (3,10); import webview; import clr" >nul 2>nul
    if not errorlevel 1 goto launch
)
rem Prefer a known compatible installed interpreter; do not assume pythonw exists.
where py >nul 2>nul
if not errorlevel 1 (
    for %%V in (3.13 3.12 3.11 3.10) do (
        py -%%V -c "import sys; assert sys.version_info >= (3,10)" >nul 2>nul
        if not errorlevel 1 (
            set "PD_AI_PYTHON=py -%%V"
            goto setup
        )
    )
    py -3 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>nul
    if not errorlevel 1 (
        set "PD_AI_PYTHON=py -3"
        goto setup
    )
)
where python >nul 2>nul
if not errorlevel 1 (
    python -c "import sys; assert sys.version_info >= (3,10)" >nul 2>nul
    if not errorlevel 1 (
        set "PD_AI_PYTHON=python"
        goto setup
    )
)
echo A working Python 3.10 or newer is required.
echo Python 3.12 or 3.13 is recommended for this desktop renderer.
pause
exit /b 1
:setup
echo Preparing the Purple Dragon desktop renderer...
if not exist "logs" mkdir "logs"
if not exist "logs" goto setup_failed
echo Setup progress is saved to logs\setup.log
rem --clear is reached only when the private environment failed its import check.
rem This folder contains dependencies only; project settings and workspaces are separate.
%PD_AI_PYTHON% -m venv --clear .venv > "logs\setup.log" 2>&1
if errorlevel 1 goto setup_failed
"%PD_AI_ENV_PYTHON%" -m pip install --disable-pip-version-check -r requirements-desktop.txt >> "logs\setup.log" 2>&1
if errorlevel 1 goto setup_failed
"%PD_AI_ENV_PYTHON%" -c "import sys; assert sys.version_info >= (3,10); import webview; import clr" >nul 2>nul
if errorlevel 1 goto setup_failed
:launch
rem Use the verified console interpreter. Missing pythonw.exe cannot block startup.
where powershell >nul 2>nul
if errorlevel 1 goto visible_launch
powershell -NoProfile -NonInteractive -Command "try { Start-Process -FilePath $env:PD_AI_ENV_PYTHON -ArgumentList 'launcher.py' -WorkingDirectory $env:PD_AI_PROJECT_DIR -WindowStyle Hidden -ErrorAction Stop; exit 0 } catch { Write-Error $_; exit 1 }"
if errorlevel 1 goto visible_launch
exit /b 0
:visible_launch
rem If hidden launch is unavailable, keep errors visible and still start the app.
"%PD_AI_ENV_PYTHON%" launcher.py
set "PD_AI_EXIT=%errorlevel%"
if not "%PD_AI_EXIT%"=="0" pause
exit /b %PD_AI_EXIT%
:setup_failed
echo.
echo Desktop setup failed. Your configuration, workspace and recovery data were preserved.
if exist "logs\setup.log" type "logs\setup.log"
echo Check logs\setup.log, then run this file again.
pause
exit /b 1
