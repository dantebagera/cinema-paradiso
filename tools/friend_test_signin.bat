@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run run.bat first to create the Python environment, then try again.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" tools\friend_test_launcher.py --signin
pause
