@echo off
setlocal
cd /d "%~dp0"
call Select-Python.bat
if errorlevel 1 goto failed
echo Purple Dragon AI Agent v2.0.0 - Source Verification
%PD_PYTHON% verify_source.py
if errorlevel 1 goto failed
%PD_PYTHON% release_check.py
if errorlevel 1 goto failed
echo Source verification PASSED. No installer or EXE was built.
echo Run Verify-Windows.bat for actual GUI checks on this PC.
pause
exit /b 0
:failed
echo Source verification FAILED. Read the selected interpreter and error above.
pause
exit /b 1
