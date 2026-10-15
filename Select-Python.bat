@echo off
rem Called by source verification/recovery. Export only the selected command to caller.
set "PD_PYTHON="
if not exist ".venv\Scripts\python.exe" goto py_launcher
".venv\Scripts\python.exe" runtime_version.py >nul 2>nul
if errorlevel 1 goto py_launcher
set PD_PYTHON="%CD%\.venv\Scripts\python.exe"
exit /b 0
:py_launcher
where py >nul 2>nul
if errorlevel 1 goto plain_python
for %%V in (3.13 3.12 3.11 3.10) do (
    py -%%V runtime_version.py >nul 2>nul
    if not errorlevel 1 (
        set "PD_PYTHON=py -%%V"
        exit /b 0
    )
)
py -3 runtime_version.py >nul 2>nul
if errorlevel 1 goto plain_python
set "PD_PYTHON=py -3"
exit /b 0
:plain_python
where python >nul 2>nul
if errorlevel 1 goto missing
python runtime_version.py >nul 2>nul
if errorlevel 1 goto missing
set "PD_PYTHON=python"
exit /b 0
:missing
echo No compatible Python 3.10+ interpreter with the standard AST module was found.
echo Install Python 3.12 or 3.13, then run Run-PurpleDragonAI.bat.
exit /b 1
