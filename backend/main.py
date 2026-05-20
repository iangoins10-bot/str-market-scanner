import sys, os, json, datetime, asyncio, re
from html.parser import HTMLParser
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright
import httpx

from scraper import scrape_url, build_redfin_url, run_scan

# ── State abbreviation → URL slug ──────────────────────────────────────────
STATE_SLUGS = {
    'AL':'alabama','AK':'alaska','AZ':'arizona','AR':'arkansas','CA':'california',
    'CO':'colorado','CT':'connecticut','DE':'delaware','FL':'florida','GA':'georgia',
    'HI':'hawaii','ID':'idaho','IL':'illinois','IN':'indiana','IA':'iowa',
    'KS':'kansas','KY':'kentucky','LA':'louisiana','ME':'maine','MD':'maryland',
    'MA':'massachusetts','MI':'michigan','MN':'minnesota','MS':'mississippi',
    'MO':'missouri','MT':'montana','NE':'nebraska','NV':'nevada','NH':'new-hampshire',
    'NJ':'new-jersey','NM':'new-mexico','NY':'new-york','NC':'north-carolina',
    'ND':'north-dakota','OH':'ohio','OK':'oklahoma','OR':'oregon','PA':'pennsylvania',
    'RI':'rhode-island','SC':'south-carolina','SD':'south-dakota','TN':'tennessee',
    'TX':'texas','UT':'utah','VT':'vermont','VA':'virginia','WA':'washington',
    'WV':'west-virginia','WI':'wisconsin','WY':'wyoming','DC':'washington-dc',
}

# ── In-memory regulations cache (24-hour TTL) ───────────────────────────────
_reg_cache: dict = {}
_REG_TTL = 86_400   # seconds

class _TextExtractor(HTMLParser):
    """Strip HTML tags, collapse whitespace."""
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'nav', 'footer', 'header'):
            self._skip = True
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav', 'footer', 'header'):
            self._skip = False
        if tag in ('p','li','div','h1','h2','h3','h4','td','tr'):
            self.parts.append('\n')
    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)
    def get_text(self):
        return re.sub(r'\n{3,}', '\n\n', ''.join(self.parts)).strip()

def _parse_reg_html(html: str, source_url: str) -> dict:
    p = _TextExtractor()
    p.feed(html)
    text = p.get_text()

    # Operating status
    status = 'unknown'
    tl = text.lower()
    if 'str is banned'    in tl or 'strs are banned'    in tl or 'prohibited'  in tl: status = 'banned'
    elif 'unregulated'    in tl or 'no specific regulation' in tl:                    status = 'unregulated'
    elif 'allowed'        in tl or 'permitted'           in tl:                       status = 'allowed'
    elif 'restricted'     in tl:                                                       status = 'restricted'

    # Permit required
    permit = None
    if re.search(r'permit\s+(?:is\s+)?required', tl):   permit = True
    elif re.search(r'no\s+permit\s+required', tl):       permit = False

    # Fee – grab first dollar amount near "fee" or "license"
    fee = None
    m = re.search(r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:per\s+\w+)?(?:[^\n]*(?:fee|license|permit))?', text, re.I)
    if m: fee = m.group(0).split('\n')[0].strip()[:80]

    # Tax rate
    tax = None
    m = re.search(r'(\d+(?:\.\d+)?)\s*%[^\n]*(?:tax|lodging|occupancy)', text, re.I)
    if not m:
        m = re.search(r'(?:tax|lodging)[^\n]*?(\d+(?:\.\d+)?)\s*%', text, re.I)
    if m: tax = m.group(0).strip()[:80]

    # Occupancy limit
    occ = None
    m = re.search(r'(?:occupancy[^\n]{0,60}?(\d+)\s*(?:person|guest|people))', text, re.I)
    if m: occ = m.group(0).strip()[:120]

    # Owner-occupied
    owner_occ = None
    if 'owner-occupied' in tl or 'owner occupied' in tl:
        owner_occ = True

    # Extract up to 6 bullet-style rules (lines starting with known keywords)
    rule_kws   = ('permit','license','registr','tax','zoning','occupancy','noise',
                  'parking','responsible','insurance','inspection','renew','cap','limit',
                  'ban','prohibit','allow','restrict','hosted','owner-occupied','investor')
    skip_pats  = (' | ', 'how to obtain', 'short-term rental regulations in ',
                  'are airbnbs', 'are short-term rentals', 'regulations.comparent')
    rules = []
    for line in text.splitlines():
        ls = line.strip()
        ll = ls.lower()
        if len(ls) < 30: continue
        if any(sp in ll for sp in skip_pats): continue
        if any(kw in ll for kw in rule_kws):
            rules.append(ls[:160])
        if len(rules) >= 6:
            break

    return {
        'status':    status,
        'permit':    permit,
        'fee':       fee,
        'tax':       tax,
        'occupancy': occ,
        'ownerOcc':  owner_occ,
        'rules':     rules,
        'sourceUrl': source_url,
        'cached':    False,
    }

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "results.json")

# ── Shared Playwright browser (launched once, reused for every request) ──
# This avoids the 3-5 second per-request Chromium startup overhead.
_playwright_instance = None
_browser             = None
_scrape_sem          = None   # limits concurrent scrapes to avoid RAM/rate-limit blowup

@asynccontextmanager
async def lifespan(app):
    global _playwright_instance, _browser, _scrape_sem
    _scrape_sem = asyncio.Semaphore(4)   # max 4 markets scraping simultaneously
    _playwright_instance = await async_playwright().start()
    _browser = await _playwright_instance.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    )
    print("[startup] Playwright browser ready")
    yield
    print("[shutdown] Closing browser…")
    await _browser.close()
    await _playwright_instance.stop()

def save_results(results):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump({
            "last_run": datetime.datetime.now().isoformat(),
            "count": len(results),
            "listings": results,
        }, f)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Serve the frontend
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/results")
def get_results():
    if not os.path.exists(DATA_FILE):
        return {"last_run": None, "count": 0, "listings": []}
    with open(DATA_FILE) as f:
        return json.load(f)


@app.post("/api/scan")
async def trigger_scan():
    results = await run_scan()
    save_results(results)
    return {"status": "ok", "count": len(results), "listings": results}


@app.get("/api/redfin")
async def redfin_search(
    location:   str   = Query(...),
    min_price:  int   = Query(150000),
    max_price:  int   = Query(650000),
    min_beds:   int   = Query(2),
    max_beds:   int   = Query(6),
    min_baths:  float = Query(1.0),
    max_dom:    int   = Query(30),
    min_sqft:   int   = Query(0),
    max_sqft:   int   = Query(0),
    pool:       bool  = Query(False),
    min_yield:  float = Query(0.0),
    keywords:   str   = Query(""),
    home_types: str   = Query("1,2,3"),
):
    parts       = location.split(",")
    market_name = parts[0].strip()
    state       = parts[1].strip() if len(parts) > 1 else ""

    criteria = {
        "min_price":  min_price,
        "max_price":  max_price,
        "min_beds":   min_beds,
        "max_beds":   max_beds,
        "min_baths":  min_baths,
        "max_dom":    max_dom,
        "min_sqft":   min_sqft,
        "max_sqft":   max_sqft if max_sqft > 0 else 999999,
        "keywords":   keywords,
        "home_types": home_types,
    }

    url = build_redfin_url(market_name, state, criteria, pool=pool, home_types=home_types)
    print(f"[redfin] {market_name}: {url}")

    try:
        # Semaphore ensures at most 4 Redfin pages open simultaneously
        async with _scrape_sem:
            results = await scrape_url(
                _browser, url, market_name, state, criteria,
                require_pool=pool,
                min_yield=min_yield,
            )
        return results

    except Exception as e:
        print(f"[redfin] ERROR {market_name}: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/regulations")
async def get_regulations(city: str = Query(...), state: str = Query(...)):
    state_slug = STATE_SLUGS.get(state.upper(), state.lower().replace(' ', '-'))
    city_slug  = re.sub(r"['. ]", lambda m: '' if m.group() in ("'", '.') else '-', city.lower())
    source_url = f"https://regulations.comparent.com/regulations/{state_slug}/{city_slug}/"
    cache_key  = (city_slug, state_slug)
    now        = datetime.datetime.now().timestamp()

    if cache_key in _reg_cache:
        entry = _reg_cache[cache_key]
        if now - entry['ts'] < _REG_TTL:
            data = dict(entry['data']); data['cached'] = True
            return data

    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            resp = await client.get(source_url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/124.0.0.0 Safari/537.36'
            })
        if resp.status_code == 404:
            return {'status': 'not_found', 'sourceUrl': source_url}
        if resp.status_code != 200:
            return JSONResponse(status_code=502, content={'error': f'HTTP {resp.status_code}', 'sourceUrl': source_url})

        data = _parse_reg_html(resp.text, source_url)
        _reg_cache[cache_key] = {'data': data, 'ts': now}
        print(f"[regs] {city}, {state} → {data['status']}")
        return data

    except Exception as e:
        print(f"[regs] ERROR {city}, {state}: {e}")
        return JSONResponse(status_code=500, content={'error': str(e), 'sourceUrl': source_url})
