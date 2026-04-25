@echo off
setlocal

cd /d "%~dp0"

echo Opening Spotify desktop app...
start "" "spotify:"

echo Waiting for Spotify app to start...
timeout /t 3 /nobreak >nul

if not exist ".venv\Scripts\python.exe" (
    echo Python virtual environment not found at .venv\Scripts\python.exe
    echo Create the venv and install dependencies first.
    pause
    exit /b 1
)

echo Starting main.py...
".venv\Scripts\python.exe" main.py --mode desktop

endlocal
