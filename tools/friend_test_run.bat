@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Creating this package's Python environment...
    py -3 -m venv .venv
    if errorlevel 1 python -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info >= (3,10)" >nul 2>nul
if errorlevel 1 (
    echo This Python environment is invalid. Ask Codex to recreate .venv in this copy.
    goto failed
)
".venv\Scripts\python.exe" -c "import flask, send2trash, pymediainfo, PIL, watchdog" >nul 2>nul
if errorlevel 1 (
    echo Installing CP Python dependencies. Internet is needed for this first setup.
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" tools\friend_test_launcher.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo Setup or launch failed. Give CODEX-HANDOVER.md to your Codex.
pause
exit /b 1
