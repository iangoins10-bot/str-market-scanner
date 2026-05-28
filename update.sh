#!/bin/bash
# Copy latest HTML to frontend, commit, and push to GitHub
cp /Users/iangoins/Downloads/str_market_scanner_v3.html /Users/iangoins/Downloads/STR_Scanner/frontend/index.html
cd /Users/iangoins/Downloads/STR_Scanner
git add -A
git commit -m "Update scanner $(date '+%Y-%m-%d %H:%M')"
git push origin main
echo "✅ Deployed to GitHub — Railway will auto-redeploy in ~2 minutes"
