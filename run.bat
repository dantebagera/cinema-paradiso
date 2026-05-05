@echo off
cd /d "%~dp0"
echo Starting My Library Organizer...
echo Press Ctrl+C to stop the server
echo.
start "" "http://localhost:5000"
python app.py
pause
