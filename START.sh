#!/bin/bash
echo ""
echo " ============================================"
echo "  STR Market Scanner — Starting up..."
echo " ============================================"
echo ""

cd "$(dirname "$0")"

echo "[1/3] Checking Python..."
if ! command -v python3 &>/dev/null; then
    echo " ERROR: Python3 not found. Install from python.org then re-run."
    exit 1
fi

echo "[2/3] Installing dependencies..."
pip3 install -r backend/requirements.txt -q
playwright install chromium 2>/dev/null

echo "[3/3] Starting backend..."
echo ""
echo " Backend:  http://localhost:8000"
echo " Frontend: Opening in browser..."
echo ""
echo " Press Ctrl+C to stop."
echo ""

open frontend/index.html 2>/dev/null || xdg-open frontend/index.html 2>/dev/null &

python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
