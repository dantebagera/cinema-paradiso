@echo off
cd /d "%~dp0"
echo Starting My Library Organizer...
echo Press Ctrl+C to stop the server
echo.
start "" "http://localhost:5000"
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe app.py
) else (
    python app.py
)
pause
