@echo off
setlocal
cd /d "%~dp0"
call Select-Python.bat
if errorlevel 1 goto finished
%PD_PYTHON% runtime_version.py
if errorlevel 1 goto finished
%PD_PYTHON% recover_settings.py
:finished
pause
