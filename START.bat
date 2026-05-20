@echo off
title STR Scanner
color 0A
echo.
echo  ============================================
echo   STR Market Scanner — Starting up...
echo  ============================================
echo.

cd /d "%~dp0"

echo [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found. Install from python.org then re-run.
    pause
    exit /b 1
)

echo [2/3] Installing dependencies...
pip install -r backend\requirements.txt -q
playwright install chromium >nul 2>&1

echo [3/3] Starting backend...
echo.
echo  Backend:  http://localhost:8000
echo  Frontend: Open frontend\index.html in your browser
echo.
echo  Press Ctrl+C to stop.
echo.

start "" "frontend\index.html"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
