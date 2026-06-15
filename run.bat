@echo off
setlocal
cd /d "%~dp0"
echo Starting Cinema Paradiso...
echo Press Ctrl+C to stop the server
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        python -m venv .venv
    )
    if errorlevel 1 (
        echo Failed to create Python virtual environment. Install Python 3.10+ and try again.
        pause
        exit /b 1
    )
)

echo Installing Python dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install Python dependencies.
    pause
    exit /b 1
)

where npm.cmd >nul 2>nul
if errorlevel 1 (
    echo Node.js 18+ with npm is required to build the React frontend.
    echo Install Node.js, reopen this window, and run this file again.
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo Installing frontend dependencies...
    npm.cmd install
    if errorlevel 1 (
        echo Failed to install frontend dependencies.
        pause
        exit /b 1
    )
)

if not exist "dist\index.html" (
    echo Building React frontend...
    npm.cmd run build
    if errorlevel 1 (
        echo Failed to build React frontend.
        pause
        exit /b 1
    )
)

echo.
echo Launching Flask backend at http://localhost:5000 ...
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://localhost:5000'"
".venv\Scripts\python.exe" app.py
set APP_EXIT=%ERRORLEVEL%
if not "%APP_EXIT%"=="0" (
    echo Flask stopped with exit code %APP_EXIT%.
    pause
    exit /b %APP_EXIT%
)
pause
