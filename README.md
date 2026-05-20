# STR Market Scanner

Scrapes Redfin daily across your selected STR markets, filters to active listings only, and serves results to a local dashboard.

## Requirements

- Python 3.9+
- Internet connection

## Setup & Run

### Windows
1. Move the `STR_Scanner` folder to your Desktop
2. Double-click `START.bat`
3. The dashboard opens automatically in your browser

### Mac
1. Move the `STR_Scanner` folder to your Desktop
2. Open Terminal, run:
   ```
   chmod +x ~/Desktop/STR_Scanner/START.sh
   ~/Desktop/STR_Scanner/START.sh
   ```
3. The dashboard opens automatically in your browser

## How it works

1. `START.bat` / `START.sh` installs dependencies and launches the FastAPI backend on port 8000
2. The frontend (`frontend/index.html`) connects to the backend automatically
3. Click **Run Scan Now** in the dashboard to trigger an immediate scan
4. The backend also runs a scan automatically every day at 6:00 AM
5. Results are saved to `data/results.json` and persist between sessions

## Markets (default)

- Divide, CO
- Sedona, AZ
- Gatlinburg, TN
- Blue Ridge, GA
- West Palm Beach, FL

Add/remove markets from the dashboard UI — changes take effect on the next scan.

## Criteria (default)

| Filter | Value |
|--------|-------|
| Price | $150k – $600k |
| Beds | 2 – 6 |
| Baths | 1+ |
| Max DOM | 30 days |
| Min yield | 8% (estimated) |
| Status | Active / for sale only |

Florida markets additionally filter by pool and HOA status.

## Notes

- Yield estimates are based on Airbnb occupancy assumptions (65%) and market nightly rates — they are estimates only, not underwritten projections
- Redfin occasionally blocks scrapers; if scans return 0 results, wait a few hours and retry
- Results are cached in `data/results.json` and shown in the dashboard even when the backend is not running
