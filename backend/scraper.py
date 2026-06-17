import asyncio
import json
import re
import random
from datetime import date, datetime
from urllib.parse import quote
from playwright.async_api import async_playwright
import httpx

# ── ZIP code lookup for known STR markets ──────────────────────
MARKET_ZIPS = {
    # Colorado
    "Divide":           "80814",
    "Westminster":      "80030",
    "Breckenridge":     "80424",
    "Telluride":        "81435",
    "Vail":             "81657",
    "Aspen":            "81611",
    "Steamboat Springs":"80487",
    "Estes Park":       "80517",
    "Durango":          "81301",
    "Crested Butte":    "81224",
    # Arizona
    "Sedona":           "86336",
    "Flagstaff":        "86001",
    "Scottsdale":       "85251",
    "Mesa":             "85201",
    "Tempe":            "85281",
    "Chandler":         "85225",
    "Gilbert":          "85234",
    "Tucson":           "85701",
    "Prescott":         "86301",
    # Tennessee
    "Gatlinburg":       "37738",
    "Pigeon Forge":     "37863",
    "Sevierville":      "37862",
    "Townsend":         "37882",
    "Cosby":            "37722",
    # Georgia
    "Blue Ridge":       "30513",
    "Helen":            "30545",
    "Dahlonega":        "30533",
    # Florida
    "West Palm Beach":  "33401",
    "Boynton Beach":    "33435",
    "Boca Raton":       "33432",
    "Delray Beach":     "33444",
    "Fort Lauderdale":  "33301",
    "Miami Beach":      "33139",
    "Destin":           "32541",
    "Panama City Beach":"32413",
    "Kissimmee":        "34741",
    "Naples":           "34102",
    "Sarasota":         "34236",
    "Gulf Shores":      "36542",
    "Cape Coral":       "33904",
    "Fort Myers":       "33901",
    "Clearwater":       "33755",
    "St. Pete Beach":   "33706",
    "St Pete Beach":    "33706",
    "Daytona Beach":    "32114",
    "St. Augustine":    "32080",
    "St Augustine":     "32080",
    "Marco Island":     "34145",
    "Anna Maria":       "34216",
    "Siesta Key":       "34242",
    "Key West":         "33040",
    "Orlando":          "32801",
    # North Carolina
    "Asheville":        "28801",
    "Boone":            "28607",
    "Brevard":          "28712",
    "Hendersonville":   "28792",
    "Bryson City":      "28713",
    "Cherokee":         "28719",
    "Cashiers":         "28717",
    "Highlands":        "28741",
    # Utah
    "Moab":             "84532",
    "Park City":        "84060",
    # California
    "Joshua Tree":      "92252",
    "Big Bear":         "92315",
    "South Lake Tahoe": "96150",
    "Mammoth Lakes":    "93546",
    "Palm Springs":     "92262",
    # Wyoming
    "Jackson":          "83001",
    # Montana
    "Whitefish":        "59937",
    # Oregon
    "Bend":             "97701",
    # New Mexico
    "Taos":             "87571",
    "Santa Fe":         "87501",
    # Texas
    "Austin":           "78701",
    "San Antonio":      "78201",
    "Fredericksburg":   "78624",
    "Wimberley":        "78676",
    "New Braunfels":    "78130",
    "South Padre Island":"78597",
    # Missouri
    "Branson":          "65616",
    # South Carolina
    "Hilton Head":      "29928",
    "Myrtle Beach":     "29577",
    # Alabama
    "Gulf Shores":      "36542",
    # Wisconsin
    "Sister Bay":       "54234",
    "Lake Geneva":      "53147",
    "Wisconsin Dells":  "53965",
    # Michigan
    "Traverse City":    "49684",
    "Petoskey":         "49770",
    # Virginia
    "Virginia Beach":   "23451",
    "Charlottesville":  "22902",
    "Luray":            "22835",
    # Washington
    "Leavenworth":      "98826",
    "Winthrop":         "98862",
    # Idaho
    "Coeur d'Alene":    "83814",
    "Coeur dAlene":     "83814",
    "McCall":           "83638",
    # Hawaii
    "Kihei":            "96753",
    "Lahaina":          "96761",
    "Kailua Kona":      "96740",
    "Hilo":             "96720",
    # Nevada
    "Las Vegas":        "89101",
    "Henderson":        "89002",
    # Georgia (extra)
    "Savannah":         "31401",
    "Tybee Island":     "31328",
    # Florida (extra)
    "Jacksonville Beach": "32250",
    "Bradenton":          "34205",
    "Fort Walton Beach":  "32548",
    "Cocoa Beach":        "32931",
    # Texas (extra)
    "Lake Travis":        "78734",
    "Richardson":         "75080",
    "Waco":               "76701",
    "Grand Prairie":      "75050",
    "Irving":             "75061",
    "Abilene":            "79601",
    "Amarillo":           "79101",
    # Arizona (extra)
    "Glendale":           "85301",
    # California (extra)
    "Oakhurst":           "93644",
    "Clear Lake":         "95422",
    # Michigan (extra)
    "Bellaire":           "49615",
    # Missouri (extra)
    "Lake of the Ozarks": "65049",
    # New York
    "Hunter":             "12442",
    "Windham":            "12496",
    "Lake Placid":        "12946",
    "Ellicottville":      "14731",
    # Colorado (extra)
    "Woodland Park":      "80863",
    "Cascade":            "80809",
    # Virginia (extra)
    "Wintergreen Resort": "22967",
    "Shenandoah":         "22849",
    # Ohio
    "Logan":              "43138",
    "Columbus":           "43215",
    "Cincinnati":         "45202",
    # Arkansas
    "Hot Springs":        "71901",
    # New Hampshire
    "Conway":             "03818",
    "Bartlett":           "03812",
    "Gilford":            "03249",
    # Pennsylvania
    "Pocono Mountains":   "18344",
    "Hershey":            "17033",
    # Maine
    "Newry":              "04261",
    "Bethel":             "04217",
    # Massachusetts
    "Great Barrington":   "01230",
    # North Carolina (extra)
    "Lake Norman":        "28031",
    # Kentucky
    "Red River Gorge":    "40376",
    # Indiana
    "Indianapolis":       "46201",
    "South Bend":         "46601",
    "Fort Wayne":         "46802",
    # Ohio extra
    "Akron":              "44308",
    # Illinois / Kansas
    "Peoria":             "61602",
    "Rockford":           "61101",
    "Wichita":            "67202",
    # Kentucky (NOO)
    "Stanton":            "40380",
    # Georgia (NOO)
    "Columbus GA":        "31901",
    # Michigan (NOO)
    "Hazel Park":         "48030",
    # Alaska
    "Fairbanks":          "99701",
    # Oklahoma
    "Broken Bow":         "74728",
    # North Carolina (NOO)
    "Beech Mountain":     "28604",
    "Sneads Ferry":       "28460",
    # Florida (NOO)
    "Davenport":          "33837",
    "Tampa":              "33602",
    # South Carolina / Alabama (NOO)
    "Spartanburg":        "29301",
    "Montgomery":         "36104",
    # Vermont
    "Jay":                "05859",
    # New Mexico (extra)
    "Angel Fire":         "87710",
    # Wisconsin (extra)
    "Baraboo":            "53913",
    # Added from market watchlist
    "Bonita Springs":     "34134",
    "Navarre":            "32566",
    "Tallahassee":        "32301",
    "Galveston":          "77550",
    "College Station":    "77840",
    "Shandaken":          "12480",
    "Jeffersonville":     "12748",
    "Wilmington":         "12997",
    "McHenry":            "21541",
    "Stowe":              "05672",
    "Muskegon":           "49440",
    "Pittsburgh":         "15222",
    "Brian Head":         "84719",
    "Bailey":             "80421",
    "Seaside":            "97138",
    "Newport":            "97365",
    "Bloomington":        "61701",
    "Charlotte":          "28202",
    "Tulsa":              "74103",
}

# Legacy hardcoded markets (kept for backwards-compat with /api/scan)
MARKETS = [
    {"name": "Divide",          "state": "CO", "zip": "80814", "pool_filter": False},
    {"name": "Sedona",          "state": "AZ", "zip": "86336", "pool_filter": True},
    {"name": "Gatlinburg",      "state": "TN", "zip": "37738", "pool_filter": False},
    {"name": "Blue Ridge",      "state": "GA", "zip": "30513", "pool_filter": False},
    {"name": "West Palm Beach", "state": "FL", "zip": "33401", "pool_filter": True},
]

POOL_STATES = {"FL", "TX", "AZ"}
HOA_STATES  = {"FL"}

CRITERIA = {
    "min_price": 150000,
    "max_price": 600000,
    "min_beds":  2,
    "min_baths": 1,
    "max_dom":   30,
    "min_yield_pct": 8.0,
}

# Realistic blended-season nightly rates (high + low / 2) for a typical STR
NIGHTLY_RATES = {1: 120, 2: 175, 3: 250, 4: 340, 5: 435, 6: 530}

# Pool premium: pools in warm STR markets push nightly rates up ~30 %
POOL_PREMIUM = 0.30

MARKET_MULT = {
    # Colorado mountain
    "Divide":1.20,"Breckenridge":1.40,"Telluride":1.45,"Vail":1.40,"Aspen":1.50,
    "Steamboat Springs":1.25,"Estes Park":1.20,"Crested Butte":1.30,"Durango":1.15,
    # Arizona
    "Sedona":1.40,"Flagstaff":1.10,"Scottsdale":1.30,"Mesa":1.10,
    "Tempe":1.05,"Chandler":1.05,"Gilbert":1.05,"Prescott":1.15,
    # Tennessee
    "Gatlinburg":1.30,"Pigeon Forge":1.30,"Sevierville":1.20,"Townsend":1.10,"Cosby":1.10,
    # Georgia
    "Blue Ridge":1.25,"Helen":1.10,"Dahlonega":1.10,"Savannah":1.15,"Tybee Island":1.20,
    # Florida
    "West Palm Beach":1.15,"Boynton Beach":1.10,"Boca Raton":1.15,"Delray Beach":1.15,
    "Fort Lauderdale":1.15,"Miami Beach":1.25,"Destin":1.30,"Panama City Beach":1.25,
    "Kissimmee":1.25,"Naples":1.25,"Sarasota":1.20,"Cape Coral":1.15,"Fort Myers":1.15,
    "Clearwater":1.15,"St. Pete Beach":1.20,"St Pete Beach":1.20,"Daytona Beach":1.10,
    "St. Augustine":1.20,"St Augustine":1.20,"Marco Island":1.30,"Anna Maria":1.35,
    "Siesta Key":1.35,"Key West":1.40,"Orlando":1.20,"Gulf Shores":1.20,
    # North Carolina
    "Asheville":1.20,"Boone":1.15,"Brevard":1.10,"Bryson City":1.15,
    "Cashiers":1.25,"Highlands":1.30,
    # Utah / Wyoming
    "Moab":1.30,"Park City":1.35,"Jackson":1.40,
    # California
    "Joshua Tree":1.30,"Big Bear":1.20,"South Lake Tahoe":1.25,
    "Mammoth Lakes":1.25,"Palm Springs":1.35,
    # Other
    "Whitefish":1.20,"Bend":1.15,"Taos":1.15,"Santa Fe":1.15,
    # Florida extra
    "Jacksonville Beach":1.15,"Bradenton":1.15,"Fort Walton Beach":1.20,"Cocoa Beach":1.15,
    # Texas extra
    "Lake Travis":1.20,"Richardson":1.05,"Waco":1.05,"Grand Prairie":1.05,
    "Irving":1.05,"Abilene":1.00,"Amarillo":1.00,
    # Arizona extra
    "Glendale":1.05,
    # California extra
    "Oakhurst":1.20,"Clear Lake":1.10,
    # Michigan extra
    "Bellaire":1.20,
    # Missouri extra
    "Lake of the Ozarks":1.20,
    # New York
    "Hunter":1.20,"Windham":1.20,"Lake Placid":1.25,"Ellicottville":1.20,
    # Colorado extra
    "Woodland Park":1.15,"Cascade":1.10,
    # Virginia extra
    "Wintergreen Resort":1.25,"Shenandoah":1.15,
    # Ohio
    "Logan":1.10,"Columbus":1.05,"Cincinnati":1.05,
    # Arkansas
    "Hot Springs":1.15,
    # New Hampshire
    "Conway":1.20,"Bartlett":1.15,"Gilford":1.20,
    # Pennsylvania
    "Pocono Mountains":1.20,"Hershey":1.10,
    # Maine
    "Newry":1.15,"Bethel":1.15,
    # Massachusetts
    "Great Barrington":1.20,
    # North Carolina extra
    "Lake Norman":1.15,
    # Kentucky
    "Red River Gorge":1.20,
    # Indiana
    "Indianapolis":1.05,"South Bend":1.05,
    # Vermont
    "Jay":1.20,
    # New Mexico extra
    "Angel Fire":1.20,
    # Wisconsin extra
    "Baraboo":1.15,
    # Texas cont.
    "Austin":1.20,"San Antonio":1.10,
    "Fredericksburg":1.20,"Wimberley":1.15,"New Braunfels":1.15,
    "South Padre Island":1.25,"Branson":1.10,"Hilton Head":1.25,"Myrtle Beach":1.20,
    "Lake Geneva":1.10,"Wisconsin Dells":1.15,"Traverse City":1.15,"Virginia Beach":1.15,"Luray":1.15,
    "Leavenworth":1.20,"Las Vegas":1.10,"Kihei":1.35,"Kailua Kona":1.30,
    "Westminster":0.85,
    # Markets added to fill missing multiplier gaps
    "Tucson":1.10,"Hendersonville":1.10,"Cherokee":1.10,
    "Winthrop":1.15,"McCall":1.20,"Charlottesville":1.10,
    "Sister Bay":1.15,"Petoskey":1.15,"Henderson":1.05,
    "Lahaina":1.35,"Hilo":1.15,"Coeur d'Alene":1.25,
    # NOO high-yield markets (2024-25 research)
    "Akron":1.10,"Fort Wayne":1.00,
    "Peoria":1.05,"Rockford":1.05,"Wichita":1.05,
    "Stanton":1.25,                      # Red River Gorge gateway
    "Columbus GA":1.10,
    "Hazel Park":1.05,
    "Fairbanks":1.15,
    "Broken Bow":1.35,                   # Beavers Bend cabin market
    "Beech Mountain":1.20,"Sneads Ferry":1.15,
    "Davenport":1.20,"Tampa":1.15,
    "Spartanburg":1.05,"Montgomery":1.05,
}

# Resources to block — we only need the API response, not images/fonts/CSS
_BLOCK_TYPES    = {"image", "font", "media", "stylesheet", "ping", "websocket"}
_BLOCK_DOMAINS  = [
    "google-analytics", "googlesyndication", "doubleclick",
    "facebook.com", "fbcdn.net", "amplitude.com", "segment.io",
    "mixpanel.com", "hotjar.com", "newrelic.com", "datadog",
]

async def _route_blocker(route):
    """Abort heavy/tracking resources — speeds up page load by 40-60%."""
    if route.request.resource_type in _BLOCK_TYPES:
        await route.abort()
        return
    if any(d in route.request.url for d in _BLOCK_DOMAINS):
        await route.abort()
        return
    await route.continue_()

# ── Stealth JS injected before every page load ─────────────────
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins',   {get: () => [1,2,3,4,5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
window.chrome = {runtime:{}, loadTimes:()=>{}, csi:()=>{}, app:{}};
try {
  const orig = window.navigator.permissions.query.bind(navigator.permissions);
  window.navigator.permissions.query = (p) =>
    p.name === 'notifications'
      ? Promise.resolve({state: Notification.permission})
      : orig(p);
} catch(e) {}
"""

def estimate_yield(price, beds, market="", has_pool=False):
    nightly = NIGHTLY_RATES.get(min(beds, 6), 250)
    mult    = MARKET_MULT.get(market, 1.0)
    if has_pool:
        mult *= (1 + POOL_PREMIUM)   # pools command ~30% premium on nightly rate
    annual  = nightly * mult * 365 * 0.65
    gross   = round(annual / price * 100, 1) if price > 0 else 0
    cap     = round(gross * 0.65, 1)
    return gross, cap, int(annual)

# Pre-built lowercase→zip map for O(1) case-insensitive lookups
_ZIPS_LOWER = {k.lower(): v for k, v in MARKET_ZIPS.items()}

def _zip_lookup(market_name):
    """Case-insensitive ZIP code lookup — O(1) via pre-built lowercase map."""
    return MARKET_ZIPS.get(market_name) or _ZIPS_LOWER.get(market_name.lower())

# ── Redfin region resolver ──────────────────────────────────────────────────
# A single ZIP only covers part of a city. Redfin's own search for "Sevierville,
# TN" spans every ZIP in the city — which is why a manual search shows far more
# listings than a one-ZIP scan. We resolve each market to Redfin's canonical
# city/county region (the same thing Redfin shows you) via its autocomplete API,
# so the scanner sees exactly what you see.
import os as _os
_REGION_CACHE: dict = {}
_REGION_CACHE_FILE = _os.path.join(
    _os.path.dirname(_os.path.abspath(__file__)), "..", "data", "region_cache.json"
)

def _load_region_cache():
    global _REGION_CACHE
    if _REGION_CACHE:
        return
    try:
        with open(_REGION_CACHE_FILE) as f:
            raw = json.load(f)
        _REGION_CACHE = {tuple(k.split("|", 1)): v for k, v in raw.items()}
    except Exception:
        _REGION_CACHE = {}

def _save_region_cache():
    try:
        _os.makedirs(_os.path.dirname(_REGION_CACHE_FILE), exist_ok=True)
        serial = {f"{k[0]}|{k[1]}": v for k, v in _REGION_CACHE.items()}
        with open(_REGION_CACHE_FILE, "w") as f:
            json.dump(serial, f, indent=2)
    except Exception as e:
        print(f"    [region] cache save failed: {e}")

def _pick_region(hrefs, state):
    """Choose the best region path from candidate hrefs/paths.
    Prefer whole-city, then county, then neighborhood, then any in-state.
    Returns a path like '/city/17180/TN/Sevierville' (domain stripped)."""
    st = (state or "").upper().strip()
    city_url = county_url = hood_url = any_url = None
    for u in hrefs or []:
        if not u:
            continue
        # strip domain → path
        if u.startswith("http"):
            u = "/" + u.split("/", 3)[-1] if u.count("/") >= 3 else u
        # skip non-region links (agents, schools, listings, etc.)
        if "/real-estate/agents" in u or "/school/" in u:
            continue
        in_state = (f"/{st}/" in u) if st else True
        if "/city/" in u and in_state and city_url is None:
            city_url = u
        elif "/county/" in u and in_state and county_url is None:
            county_url = u
        elif "/neighborhood/" in u and in_state and hood_url is None:
            hood_url = u
        elif any_url is None and in_state and any(
            seg in u for seg in ("/city/", "/county/", "/neighborhood/")
        ):
            any_url = u
    return city_url or county_url or hood_url or any_url

async def resolve_region_url(market_name, state, browser=None):
    """
    Return Redfin's canonical region path for a market, e.g.
    '/city/17180/TN/Sevierville', so we search the WHOLE city (all ZIPs) instead
    of one ZIP. Resolved by driving Redfin's real search box inside a Playwright
    page and reading the autocomplete dropdown's city link from the DOM — the raw
    autocomplete API is bot-blocked (403), but the genuine UI request is not.
    Cached to disk — each market resolved at most once, ever. None → use ZIP.
    """
    _load_region_cache()
    key = (market_name.lower().strip(), (state or "").upper().strip())
    if key in _REGION_CACHE:
        return _REGION_CACHE[key]
    if browser is None:
        return None   # cannot resolve without a browser; caller falls back to ZIP

    query = f"{market_name}, {state}" if state else market_name
    context = None
    try:
        context = await browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 800},
        )
        await context.add_init_script(STEALTH_JS)
        page = await context.new_page()
        # NOTE: do NOT block resources here — the search box needs the page's JS.
        await page.goto("https://www.redfin.com/", wait_until="domcontentloaded", timeout=25000)

        # Find and type into the search box; the autocomplete dropdown renders
        # region links (city/county/neighborhood) directly in the DOM.
        box = None
        for sel in ("input#search-box-input",
                    "input[data-rf-test-name='search-box-input']",
                    "input[name='searchInputBox']",
                    "input[type='search']"):
            try:
                if await page.query_selector(sel):
                    box = sel
                    break
            except Exception:
                pass
        if not box:
            raise RuntimeError("search box not found")

        await page.fill(box, query)
        # Wait for the dropdown to populate with /city/ links.
        hrefs = []
        for _ in range(20):  # up to ~5s
            await page.wait_for_timeout(250)
            hrefs = await page.evaluate(
                """() => Array.from(document.querySelectorAll('.item-row a[href]'))
                        .map(a => a.getAttribute('href'))
                        .filter(h => h && /\\/(city|county|neighborhood)\\/\\d+\\//.test(h))"""
            )
            if any("/city/" in h for h in hrefs):
                break

        best = _pick_region(hrefs, state)
        _REGION_CACHE[key] = best
        _save_region_cache()
        print(f"    [region] {market_name}, {state} → {best or 'no match (using ZIP)'}")
        return best
    except Exception as e:
        print(f"    [region] resolve failed {market_name}, {state}: {e}")
        _REGION_CACHE[key] = None
        _save_region_cache()
        return None
    finally:
        if context is not None:
            try: await context.close()
            except Exception: pass


def build_redfin_url(market_name, state, criteria, pool=False, home_types=None, region_url=None):
    """Build a Redfin filter URL for a given market and criteria."""
    zip_code = _zip_lookup(market_name)

    # Map frontend codes → Redfin property-type filter tokens
    # 1 = single-family/house  2 = condo  3 = townhouse / multi-family
    codes = set((home_types or criteria.get("home_types", "1")).split(","))
    rf_types = []
    if "1" in codes: rf_types.append("house")
    if "2" in codes: rf_types.append("condo")
    if "3" in codes: rf_types += ["townhouse", "multi-family"]
    prop_type_str = ",".join(rf_types) if rf_types else "house"

    filters = [f"property-type={prop_type_str}"]
    filters.append(f"min-price={criteria.get('min_price', 150000)}")
    # If max_price is unreasonably high (≥ 5M), omit the max-price filter entirely
    # so Redfin shows all prices rather than choking on an absurd upper bound.
    _max_price = criteria.get("max_price", 650000)
    if _max_price < 5_000_000:
        filters.append(f"max-price={_max_price}")
    filters.append(f"min-beds={criteria.get('min_beds', 2)}")
    if criteria.get("max_beds", 99) < 99:
        filters.append(f"max-beds={criteria['max_beds']}")
    if criteria.get("min_baths", 1) > 1:
        filters.append(f"min-baths={criteria['min_baths']}")
    max_dom = criteria.get("max_dom", 30)
    if max_dom < 90:
        filters.append(f"max-days-on-market={max_dom}")
    if pool:
        filters.append("amenities=pool")
    filters.append("status=active")

    filter_str = ",".join(filters)

    # Prefer Redfin's canonical city/county region (covers the WHOLE city, all
    # ZIPs) when we resolved one — this is the fix for "manual search shows more".
    if region_url and any(seg in region_url for seg in ("/city/", "/county/", "/neighborhood/")):
        base = region_url if region_url.startswith("http") else f"https://www.redfin.com{region_url}"
        return f"{base}/filter/{filter_str}"

    if zip_code:
        return f"https://www.redfin.com/zipcode/{zip_code}/filter/{filter_str}"
    else:
        city_slug = market_name.replace(" ", "-")
        return f"https://www.redfin.com/{state}/{city_slug}/filter/{filter_str}"

def parse_price(price_str):
    if not price_str:
        return None
    s = price_str.split("/")[0].strip()
    # Handle abbreviated: $1.2M, $850K
    m = re.search(r"\$([\d,]+\.?\d*)\s*([MmKk])", s)
    if m:
        num = float(m.group(1).replace(",", ""))
        suffix = m.group(2).upper()
        return int(num * (1_000_000 if suffix == "M" else 1_000))
    cleaned = re.sub(r"[^\d]", "", s)
    return int(cleaned) if cleaned else None

_WORD_NUMS = {
    "one":1,"two":2,"three":3,"four":4,"five":5,
    "six":6,"seven":7,"eight":8,"nine":9,"ten":10,
}

def parse_beds_baths(text):
    beds, baths = None, None

    # Digit form: "4 Beds", "3 bed", "4-bedroom"
    bed_match  = re.search(r"(\d+)\s*[-–]?\s*[Bb]ed", text)
    bath_match = re.search(r"(\d+\.?\d*)\s*[-–]?\s*[Bb]ath", text)

    if bed_match:
        beds = int(bed_match.group(1))
    else:
        # Written form: "four-bedroom", "three bedroom"
        wm = re.search(
            r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s*[-–]?\s*bed",
            text, re.IGNORECASE
        )
        if wm:
            beds = _WORD_NUMS.get(wm.group(1).lower())

    if bath_match:
        baths = float(bath_match.group(1))
    else:
        # Written form: "two and a half bath", "three bath"
        wm = re.search(
            r"\b(one|two|three|four|five|six)\s*(and\s*a\s*half\s*)?bath",
            text, re.IGNORECASE
        )
        if wm:
            n = _WORD_NUMS.get(wm.group(1).lower(), 1)
            baths = n + 0.5 if wm.group(2) else float(n)

    return beds, baths

def extract_address(text, lines):
    addr_pattern = re.search(
        r'\d+\s+[A-Z][a-zA-Z0-9\s]+(St|Rd|Dr|Ave|Ln|Blvd|Way|Ct|Trail|Hwy|Pl|Loop|Pike|Cir|Ter|Run|Pass|Pkwy|Cv|Pt|Xing)[,\.\s]',
        text
    )
    if addr_pattern:
        return addr_pattern.group(0).strip().rstrip(".,")
    for line in lines[:8]:
        if re.match(r"^\d+\s+\w", line) and len(line) < 80:
            if any(w in line for w in ["St","Rd","Dr","Ave","Ln","Blvd","Way","Ct","Trail","Hwy","Pl","Loop","Cir","Pkwy"]):
                return line
    return lines[0] if lines else "Unknown"

def check_pool(text):
    """
    Returns:
      True  — pool explicitly confirmed in text/HTML
      False — pool explicitly denied ("no pool", "pool table", etc.)
      None  — not mentioned / ambiguous (caller should trust Redfin's URL filter)
    """
    no_pool_kw = [
        r"\bno pool\b", r"\bwithout pool\b",
        r"\bcarpool\b", r"\bcar pool\b",
        r"\bpool table\b",   # billiards
        r"\bpool room\b",    # game room
        r"\bpool bath\b",    # bathroom, not swimming
    ]
    pool_kw = [
        r"\bswimming pool\b", r"\binground pool\b", r"\bin-ground pool\b",
        r"\babove.?ground pool\b", r"\bprivate pool\b", r"\bheated pool\b",
        r"\bsalt.?water pool\b", r"\bpool & spa\b", r"\bpool and spa\b",
        r"\bpool/spa\b", r"\bpool home\b", r"\bpool house\b",
        r"\bpool deck\b", r"\bpool cage\b", r"\bscreened.?pool\b",
        r"\bpool area\b", r"\bpool view\b", r"\bpebble.?tec\b",
        r"\bpool\b",  # broad — negatives above strip false positives
    ]
    text_lower = text.lower()
    for kw in no_pool_kw:
        if re.search(kw, text_lower):
            return False
    for kw in pool_kw:
        if re.search(kw, text_lower):
            return True
    return None  # not mentioned — ambiguous

def check_dom(text):
    """
    Parse days-on-market from Redfin card text.
    Only matches Redfin-specific DOM phrases to avoid false matches
    from listing description text (e.g. '30-day escrow', '7-day inspection').
    """
    # "NEW X HR(S) AGO" / "NEW X DAY(S) AGO" → listed very recently
    if re.search(r'\bNEW\b.*\b\d+\s*HR', text, re.IGNORECASE):
        return 0
    if re.search(r'\bNEW\s+LISTING\b|\bJUST\s+LISTED\b|\bLISTED\s+TODAY\b|\bNEW\s+TODAY\b', text, re.IGNORECASE):
        return 0

    # Redfin-specific phrases: "N days on Redfin", "N days on market", "listed N days ago"
    patterns = [
        r'(\d+)\s+days?\s+on\s+redfin',
        r'(\d+)\s+days?\s+on\s+(?:the\s+)?market',
        r'listed\s+(\d+)\s+days?\s+ago',
        r'(\d+)\s+days?\s+ago',
        r'on\s+redfin\s+(\d+)\s+days?',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return int(m.group(1))

    # Week / month phrasing from Redfin
    m = re.search(r'(\d+)\s+weeks?\s+on\s+(?:redfin|(?:the\s+)?market)', text, re.IGNORECASE)
    if m:
        return int(m.group(1)) * 7
    m = re.search(r'(\d+)\s+months?\s+on\s+(?:redfin|(?:the\s+)?market)', text, re.IGNORECASE)
    if m:
        return int(m.group(1)) * 30

    return None  # unknown — caller should treat as pass-through

def extract_dom(home):
    """
    Multi-strategy DOM extraction from a Redfin API home object.
    Tries field names first, then computes from listing date.
    """
    # Strategy 1: try all known field names Redfin uses
    for field in ("dom", "daysOnMarket", "numDaysOnMarket", "daysOnRedfin", "mlsDom"):
        raw = _val(home.get(field))
        if raw is not None:
            try:
                val = int(raw)
                if val >= 0:
                    return val
            except (TypeError, ValueError):
                pass

    # Strategy 2: compute from listing / first-listed date
    for field in ("listingAddedDate", "firstListedDate", "listDate", "addedOn"):
        date_raw = home.get(field)
        if not date_raw:
            continue
        try:
            if isinstance(date_raw, (int, float)):
                # Unix timestamp in milliseconds
                dt = datetime.fromtimestamp(date_raw / 1000).date()
            elif isinstance(date_raw, str):
                dt = datetime.strptime(date_raw[:10], "%Y-%m-%d").date()
            else:
                continue
            dom = (date.today() - dt).days
            if 0 <= dom <= 3650:
                return dom
        except (ValueError, TypeError, OSError):
            pass

    return None  # unknown DOM

def _val(field):
    """Safely unwrap Redfin's {value: X, level: Y} wrapper."""
    if field is None:
        return None
    if isinstance(field, dict):
        return field.get("value")
    return field

_STREET_SUFFIXES = (
    "st","street","rd","road","dr","drive","ln","lane","ave","avenue","way","ct",
    "court","cir","circle","blvd","boulevard","pl","place","ter","terrace","trl",
    "trail","trce","trace","pkwy","parkway","hwy","highway","loop","run","pass",
    "path","pt","point","cv","cove","row","walk","bnd","bend","xing","crossing",
)

def _normalize_addr(addr):
    """
    Clean a raw street address:
      • collapse repeated whitespace
      • remove an accidentally duplicated trailing street suffix
        ("2947 Patty View Way Way" → "2947 Patty View Way")
      • title-case ALL-CAPS addresses while leaving mixed case alone
    """
    if not addr:
        return addr
    a = re.sub(r"\s+", " ", str(addr)).strip()
    if not a:
        return a
    # Collapse an immediately duplicated final token if it's a street suffix
    toks = a.split(" ")
    if len(toks) >= 2 and toks[-1].lower() == toks[-2].lower() and toks[-1].lower().strip(".") in _STREET_SUFFIXES:
        toks = toks[:-1]
        a = " ".join(toks)
    # Title-case if the string is all uppercase (Redfin sometimes shouts addresses)
    if a.isupper():
        a = a.title()
    return a

def _stable_id(home, addr):
    """
    Build a STABLE listing identifier that does NOT change when the price changes.
    This is critical for price-drop tracking: if the id included the price, every
    price cut would look like a brand-new listing and the drop would never be
    detected. Prefer Redfin's real property/listing IDs; fall back to address only.
    """
    for id_field in ("listingId", "mlsId", "propertyId", "id"):
        v = _val(home.get(id_field)) if isinstance(home, dict) else None
        if v is None and isinstance(home, dict):
            v = home.get(id_field)
        if v:
            s = str(v).strip()
            if s and s not in ("null", "None", "0"):
                return f"rf{s}"
    # Fallback: address only (NEVER include price — see docstring)
    a = str(addr or "").strip().lower()
    if a:
        return f"a{abs(hash(a))}"
    return None

# Redfin's GIS API returns numeric OR string property type codes depending on
# the API version.  Numeric: 1=SFH, 2=Condo, 3=Townhouse, 4=Multi-family,
# 5=Land, 6=Other, 7=Mobile, 8=Co-op.  Always add both forms.
SINGLE_FAMILY_TYPES = {
    # String forms
    "SINGLE_FAMILY_RESIDENTIAL", "SINGLE_FAMILY", "RESIDENTIAL",
    "HOUSE", "CABIN", "FARM", "LAND", "MOBILE", "MANUFACTURED",
    "DETACHED", "SFR", "SFH",
    # Numeric forms (Redfin GIS API v1/v2)
    "1", "5", "6", "7",
}
CONDO_TYPES = {
    # String forms
    "CONDO", "CONDO_TOWNHOUSE", "CO_OP", "COOP",
    "CONDOMINIUM", "CONDOMINIMUM", "COOPERATIVE",
    # Numeric forms
    "2", "8",
}
TOWNHOUSE_TYPES = {
    # String forms
    "TOWNHOUSE", "TOWN_HOUSE", "TOWNHOME",
    "MULTI_FAMILY_RESIDENTIAL", "MULTI_FAMILY", "MULTIFAMILY",
    "DUPLEX", "TRIPLEX", "QUADRUPLEX",
    # Numeric forms
    "3", "4",
}

def _extract_prop_type(home):
    """Try every field name Redfin has used for property type."""
    for field in ("propertyType", "homeType", "type", "listingType", "propertyTypeName"):
        raw = home.get(field)
        if not raw:
            continue
        if isinstance(raw, dict):
            raw = raw.get("value") or raw.get("name") or ""
        val = str(raw).upper().strip()
        if val:
            return val
    return ""   # unknown

def _prop_type_allowed(prop_type, allowed_codes):
    """
    Return False if this property type is excluded by the active home-type codes.
    Uses a whitelist: when only code '1' (house) is active, reject anything
    that is positively identified as condo/townhouse — and also reject any
    *known* non-house type we haven't mapped yet.
    """
    only_houses = "2" not in allowed_codes and "3" not in allowed_codes

    if prop_type in CONDO_TYPES:
        return "2" in allowed_codes
    if prop_type in TOWNHOUSE_TYPES:
        return "3" in allowed_codes

    # If only houses are wanted and we have a *known* non-house type → reject
    if only_houses and prop_type and prop_type not in SINGLE_FAMILY_TYPES:
        return False

    return True   # unknown type or explicitly allowed


def _extract_lat_lng(home):
    """Pull listing coordinates from any of the shapes Redfin has used:
    latLong.value.{latitude,longitude}, latLong.{latitude,longitude},
    or flat lat/lng keys. Returns (lat, lng) or (None, None)."""
    lat = lng = None
    ll = home.get("latLong") or home.get("latLng")
    if isinstance(ll, dict):
        inner = ll.get("value") if isinstance(ll.get("value"), dict) else ll
        lat = inner.get("latitude",  inner.get("lat"))
        lng = inner.get("longitude", inner.get("lng"))
    if lat is None:
        lat = _val(home.get("lat")) or _val(home.get("latitude"))
    if lng is None:
        lng = _val(home.get("lng")) or _val(home.get("longitude"))
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None, None
    # Reject null-island and out-of-range junk
    if not (-90 <= lat <= 90 and -180 <= lng <= 180) or (lat == 0 and lng == 0):
        return None, None
    return lat, lng


def build_listing(home, market_name, state, criteria, require_pool, min_yield):
    """Convert a Redfin API home object into our listing dict. Returns None if filtered out."""
    min_price     = criteria.get("min_price", 0)
    max_price     = criteria.get("max_price", 9999999)
    min_beds      = criteria.get("min_beds",  1)
    min_baths     = criteria.get("min_baths", 1.0)
    max_dom       = criteria.get("max_dom",   30)
    min_sqft      = criteria.get("min_sqft",  0)
    max_sqft      = criteria.get("max_sqft",  999999)
    keywords      = [k.strip().lower() for k in criteria.get("keywords", "").split(",") if k.strip()]
    allowed_codes = set(criteria.get("home_types", "1,2,3").split(","))

    # ── Property type gate ────────────────────────────────────────
    # 1. Check the propertyType field if Redfin includes it
    prop_type = _extract_prop_type(home)
    if not _prop_type_allowed(prop_type, allowed_codes):
        return None

    # 2. Address-based + URL-based detection — condos have unit numbers.
    #    Be conservative: only reject addresses with clear multi-digit unit numbers
    #    (e.g. "Unit 4B", "Apt 202") not generic lot/house variants like "#1".
    only_houses = "2" not in allowed_codes and "3" not in allowed_codes
    if only_houses:
        full_addr = str(_val(home.get("address")) or "")
        if re.search(
            # Unit/Apt/Suite with 2+ char designator → clear multi-unit
            # #A1 / #2B style letter+digit → clear multi-unit
            # #12, #101 etc (2+ digits) → clear multi-unit
            # "Fl. 3" / "Floor 2" → clear multi-unit
            # NOT matched: "#1" alone (single digit) — valid SFH address like "123 Main St #1"
            r'\bUnit\s+\w{2,}|\bApt\.?\s+\w{2,}|\bSuite\s+\w{2,}'
            r'|#\s*[A-Z]\d|#\s*\d[A-Z]|#\s*\d{2,}'
            r'|\bFl\.?\s*\d{1,2}\b|\bFloor\s+\d{1,2}\b',
            full_addr, re.IGNORECASE
        ):
            return None
        # Check the listing URL slug for unambiguous condo indicators
        raw_link = str(_val(home.get("url")) or home.get("url") or "").lower()
        if re.search(r'/unit-\d{2,}|/apt-\d{2,}|/unit-[a-z]\d|/apt-[a-z]\d', raw_link):
            return None

    price = _val(home.get("price"))
    if not price:
        return None
    try:
        price = int(price)
    except (TypeError, ValueError):
        return None
    if not (min_price <= price <= max_price):
        return None

    beds  = home.get("beds")  or 0
    baths = home.get("baths") or 0
    try:
        beds  = int(beds)
        baths = float(baths)
    except (TypeError, ValueError):
        beds = baths = 0

    if beds < min_beds:
        return None
    if min_baths > 1 and baths > 0 and baths < min_baths:
        return None

    sqft_raw = _val(home.get("sqFt"))
    sqft = int(sqft_raw) if sqft_raw else 0
    if sqft and (sqft < min_sqft or sqft > max_sqft):
        return None

    dom = extract_dom(home)
    # None means DOM unknown. Redfin's URL filter already gated it, but for
    # tight filters (≤7 days) we reject unknown-DOM homes to prevent stale slip-throughs.
    if dom is not None and dom > max_dom:
        return None
    if dom is None and max_dom <= 7:
        return None

    # Address — Redfin gives "123 Main St, City, ST ZIP"
    addr_raw = _val(home.get("address")) or ""
    addr = addr_raw.split(",")[0].strip() if "," in addr_raw else addr_raw.strip()
    addr = _normalize_addr(addr)
    if not addr:
        addr = "Unknown"

    # Description / remarks for tag extraction
    remarks = home.get("listingRemarks") or ""

    # pool_status: True = confirmed, False = explicitly denied, None = not mentioned
    pool_status    = check_pool(remarks)
    pool_confirmed = pool_status is True

    # Hard-reject only when listing text explicitly denies a pool ("no pool", etc.)
    # For ambiguous cases (pool_status is None), trust Redfin's amenities=pool URL filter.
    if require_pool and pool_status is False:
        return None

    if keywords:
        hay = (addr + " " + remarks + " " + market_name).lower()
        if not all(k in hay for k in keywords):
            return None

    # Yield gets pool premium if text confirms it OR if the market required a pool
    gross_yield, cap_rate, airbnb_est = estimate_yield(price, beds or 2, market_name, has_pool=pool_confirmed or require_pool)
    if gross_yield < min_yield:
        return None

    # Tags
    tags = []
    if re.search(r"\bacre\b|\bacres\b|\bacreage\b", remarks, re.IGNORECASE):
        tags.append("acreage")
    if re.search(r"\bhot tub\b|\bjacuzzi\b", remarks, re.IGNORECASE):
        tags.append("hot tub")
    if re.search(r"\bcabin\b", remarks, re.IGNORECASE):
        tags.append("cabin")
    if re.search(r"\bmountain view\b|\bviews\b", remarks, re.IGNORECASE):
        tags.append("views")
    if re.search(r"\bcreek\b|\bwaterfront\b|\briver\b", remarks, re.IGNORECASE):
        tags.append("waterfront")

    # HOA
    hoa_raw = _val(home.get("hoa"))
    hoa_amt = int(hoa_raw) if hoa_raw and int(hoa_raw) > 0 else None
    has_hoa = hoa_amt is not None

    # Photo
    img_src = (
        home.get("thumbnailImageUrl")
        or (home.get("photoUrls") or [None])[0]
    )

    # Detail URL — try every field name Redfin has used across API versions
    url_candidates = [
        home.get("url"), home.get("propertyUrl"), home.get("detailUrl"),
        home.get("listingUrl"), home.get("link"), home.get("path"),
    ]
    raw_url = ""
    for candidate in url_candidates:
        v = _val(candidate) if candidate is not None else None
        if isinstance(v, dict):
            v = v.get("value") or v.get("path") or ""
        s = str(v or "").strip()
        if s and s not in ("null", "None"):
            raw_url = s
            break

    if raw_url.startswith("/"):
        full_url = f"https://www.redfin.com{raw_url}"
    elif raw_url.startswith("http"):
        full_url = raw_url
    else:
        # Fallback: use zip-based market search (same URL format as scan — guaranteed to work)
        zip_code = _zip_lookup(market_name)
        if zip_code:
            full_url = f"https://www.redfin.com/zipcode/{zip_code}/filter/property-type=house,condo,townhouse"
        else:
            slug = market_name.replace(" ", "-")
            full_url = f"https://www.redfin.com/{state}/{slug}/filter/property-type=house,condo,townhouse"

    lat, lng = _extract_lat_lng(home)

    return {
        "id":         _stable_id(home, addr) or abs(hash(addr)),
        "addr":       addr,
        "city":       market_name,
        "state":      state,
        "lat":        lat,
        "lng":        lng,
        "price":      price,
        "beds":       beds,
        "baths":      baths,
        "sqft":       sqft,
        "dom":        dom if dom is not None else -1,  # -1 = unknown
        "grossYield": gross_yield,
        "capRate":    cap_rate,
        "airbnbEst":  airbnb_est,
        "tags":       list(set(tags)),
        "isNew":      dom is not None and dom <= 1,
        "hasPool":      pool_confirmed,   # only True when explicitly detected in listing text
        "imgSrc":       img_src,
        "detailUrl":    full_url,
        "zestimate":    None,
        "hoa":          has_hoa,
        "hoaAmt":       hoa_amt,
        "propertyType": prop_type or "SINGLE_FAMILY_RESIDENTIAL",
        "source":       "redfin",
    }


async def scrape_url(browser, url, market_name, state, criteria, require_pool=False, min_yield=8.0):
    """
    Scrape Redfin by:
      1. Intercepting the /stingray/api/gis JSON responses (primary, most reliable)
      2. Falling back to DOM card parsing if interception yields nothing
    """
    listings    = []
    api_homes   = []
    print(f"  → Scraping {market_name}: {url}")

    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1440, "height": 900},
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "sec-ch-ua": '"Google Chrome";v="123", "Not:A-Brand";v="8"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
    )

    # Inject stealth scripts before any page load
    await context.add_init_script(STEALTH_JS)

    page = await context.new_page()
    await page.route("**/*", _route_blocker)   # block images/fonts/CSS/trackers

    # ── Intercept Redfin's internal GIS / search API ──────────────
    GIS_PATTERNS = ["/stingray/api/gis", "/stingray/api/v1/search/", "/api/v1/search/"]

    # Capture the GIS API URL and total count for pagination
    api_meta = {"total": 0, "gis_url": ""}

    def _parse_gis_response(text, source_url=""):
        """Parse a GIS response text, return (homes_list, total_count)."""
        try:
            if text.startswith("{}&&"):
                text = text[4:]
            if not text.strip().startswith("{"):
                return [], 0
            data = json.loads(text)
            payload = data.get("payload") or {}
            homes = payload.get("homes") or data.get("homes") or []
            total = (
                payload.get("totalCount")
                or payload.get("numHomes")
                or payload.get("count")
                or len(homes)
            )
            return homes, int(total)
        except Exception as e:
            print(f"    [API] Parse error ({source_url[:60]}): {e}")
            return [], 0

    # Signal fired the moment GIS data arrives via on_response listener
    gis_received = asyncio.Event()

    async def on_response(response):
        url_lower = response.url.lower()
        if not any(p in url_lower for p in GIS_PATTERNS):
            return
        if "csv" in url_lower:
            return
        try:
            text = await response.text()
            homes, total = _parse_gis_response(text, response.url)
            if homes:
                api_homes.extend(homes)
                types = {str(h.get("propertyType") or h.get("homeType") or "?") for h in homes[:20]}
                print(f"    [API intercepted] {len(homes)} homes (total={total}) | types={types}")
                gis_received.set()
                if not api_meta["gis_url"] and "/stingray/api/gis" in url_lower:
                    api_meta["gis_url"] = response.url
                    api_meta["total"]   = total
        except Exception as e:
            print(f"    [API] Parse error ({response.url[:60]}): {e}")

    page.on("response", on_response)

    try:
        # networkidle waits until the GIS API response completes (no new network
        # requests for 500ms). With images/fonts/CSS/analytics blocked by our
        # route blocker, networkidle fires as soon as the data calls finish —
        # much more reliable than domcontentloaded + a fixed timeout.
        await page.goto(url, wait_until="networkidle", timeout=30000)

        # GIS API response should already be in api_homes via on_response.
        # Give it one extra tick in case the event fired during the goto.
        try:
            await asyncio.wait_for(gis_received.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pass  # will try performance-timeline approach below

        # ── Strategy 2: scan performance timeline for GIS URLs that fired
        # before/during page load (even if on_response missed them) and
        # re-fetch them directly from within the page (same-origin, cookies included).
        if not api_homes:
            try:
                perf_gis_urls = await page.evaluate("""() => {
                    try {
                        return performance.getEntriesByType('resource')
                            .map(e => e.name)
                            .filter(u => u.includes('/stingray/api/gis') && !u.includes('csv'));
                    } catch(e) { return []; }
                }""")
                if perf_gis_urls:
                    print(f"    [Perf] Found {len(perf_gis_urls)} GIS URL(s) in timeline, re-fetching...")
                    for gis_u in perf_gis_urls[:3]:
                        raw = await page.evaluate(f"""async () => {{
                            try {{
                                const r = await fetch({json.dumps(gis_u)}, {{credentials:'include'}});
                                return await r.text();
                            }} catch(e) {{ return ''; }}
                        }}""")
                        if raw:
                            homes_p, total_p = _parse_gis_response(raw, gis_u)
                            if homes_p:
                                api_homes.extend(homes_p)
                                print(f"    [Perf] Re-fetched {len(homes_p)} homes (total={total_p})")
                                if not api_meta["gis_url"]:
                                    api_meta["gis_url"] = gis_u
                                    api_meta["total"]   = total_p
            except Exception as e:
                print(f"    [Perf] Timeline fetch error: {e}")

        # ── Strategy 3: construct and call GIS API directly from page context
        # Extract the region_id Redfin loaded for this URL, then call /stingray/api/gis
        if not api_homes:
            try:
                direct_raw = await page.evaluate("""async () => {
                    try {
                        // Redfin embeds region data in window.__reactProps or the URL
                        const path = window.location.pathname;
                        const zipM = path.match(/\\/zipcode\\/(\\d+)/);
                        const regionId = zipM ? zipM[1] : null;

                        // Try to find the GIS call params from the page's React props
                        const scripts = Array.from(document.scripts);
                        for (const s of scripts) {
                            if (s.src && s.src.includes('gis')) {
                                return null; // external, skip
                            }
                        }

                        // Build a GIS request using what we know
                        if (regionId) {
                            const params = new URLSearchParams(window.location.href.split('filter/')[1] || '');
                            const apiUrl = `/stingray/api/gis?al=1&isRentals=false&num_homes=350&ord=redfin-recommended-asc&page_number=1&sf=1,2,3,4,5,6,10,11&start=0&status=9&v=8&region_id=${regionId}&region_type=6`;
                            const r = await fetch(apiUrl, {credentials:'include'});
                            return await r.text();
                        }
                    } catch(e) {}
                    return null;
                }""")
                if direct_raw:
                    homes_d, total_d = _parse_gis_response(direct_raw, "direct-gis")
                    if homes_d:
                        api_homes.extend(homes_d)
                        print(f"    [Direct] Got {len(homes_d)} homes via direct GIS call (total={total_d})")
                        if not api_meta["gis_url"]:
                            api_meta["total"] = total_d
            except Exception as e:
                print(f"    [Direct] GIS call error: {e}")

        # ── Strategy 4: page-state extractor ─────────────────────
        # Redfin SSR-renders listing data directly into window globals.
        # Try all known locations and inline <script> JSON blobs.
        if not api_homes:
            try:
                extracted = await page.evaluate("""() => {
                    // 1. Known window globals
                    const candidates = [
                        window.__PRELOADED_STATE__,
                        window.__APP_STATE__,
                        window.__reactProps,
                        window.__INITIAL_STATE__,
                    ];
                    for (const obj of candidates) {
                        if (!obj) continue;
                        try {
                            const s = typeof obj === 'string' ? obj : JSON.stringify(obj);
                            if (s.includes('listingId') || s.includes('"homes"')) return s;
                        } catch(e) {}
                    }

                    // 2. Scan all inline <script> tags for embedded JSON blobs
                    const scripts = Array.from(document.querySelectorAll('script:not([src])'));
                    for (const sc of scripts) {
                        const t = sc.textContent || '';
                        if (!t.includes('listingId') && !t.includes('"homes"')) continue;
                        // Try to extract a JSON object/array from the script text
                        const jsonMatch = t.match(/({[\\s\\S]*"homes"[\\s\\S]*}|\\[[\\s\\S]*"listingId"[\\s\\S]*\\])/);
                        if (jsonMatch) {
                            try { JSON.parse(jsonMatch[0]); return jsonMatch[0]; } catch(e) {}
                        }
                        // Try window assignment: window.__X__ = { ... } or var X = { ... }
                        const assignMatch = t.match(/(?:window\\.__\\w+__|var\\s+\\w+)\\s*=\\s*({[\\s\\S]+});?\\s*$/);
                        if (assignMatch) {
                            try { JSON.parse(assignMatch[1]); return assignMatch[1]; } catch(e) {}
                        }
                    }
                    return null;
                }""")
                if extracted:
                    try:
                        blob = json.loads(extracted) if isinstance(extracted, str) else extracted
                        # Recursively search for a "homes" list inside the blob
                        def _find_homes(obj, depth=0):
                            if depth > 8:
                                return []
                            if isinstance(obj, list) and obj and isinstance(obj[0], dict) and (
                                "listingId" in obj[0] or "price" in obj[0] or "beds" in obj[0]
                            ):
                                return obj
                            if isinstance(obj, dict):
                                if "homes" in obj and isinstance(obj["homes"], list):
                                    return obj["homes"]
                                for v in obj.values():
                                    found = _find_homes(v, depth + 1)
                                    if found:
                                        return found
                            return []

                        state_homes = _find_homes(blob)
                        if state_homes:
                            api_homes.extend(state_homes)
                            print(f"    [PageState] Extracted {len(state_homes)} homes from page globals/scripts")
                    except Exception as e:
                        print(f"    [PageState] Parse error: {e}")
            except Exception as e:
                print(f"    [PageState] Extractor error: {e}")

        # Light scroll to catch any lazy-triggered API calls
        for scroll_y in [500, 1500, 0]:
            await page.evaluate(f"window.scrollTo(0, {scroll_y})")
            await page.wait_for_timeout(300)

        await page.wait_for_timeout(600)

        # ── Pagination: fetch remaining pages if totalCount > received ────
        PAGE_SIZE = 350
        if api_meta["gis_url"] and api_meta["total"] > len(api_homes):
            extra_pages = min(10, (api_meta["total"] - 1) // PAGE_SIZE)
            print(f"    [Pagination] total={api_meta['total']}, have={len(api_homes)}, fetching {extra_pages} more page(s)")
            base_url = api_meta["gis_url"]
            for pg in range(2, extra_pages + 2):
                start = (pg - 1) * PAGE_SIZE
                paged_url = re.sub(r'([\?&]start=)\d+', lambda m: m.group(1) + str(start), base_url)
                if 'start=' not in paged_url:
                    sep = '&' if '?' in paged_url else '?'
                    paged_url += f"{sep}start={start}"
                paged_url = re.sub(r'([\?&]page_number=)\d+', lambda m: m.group(1) + str(pg), paged_url)
                if 'page_number=' not in paged_url:
                    paged_url += f"&page_number={pg}"
                try:
                    raw = await page.evaluate(f"""async () => {{
                        try {{
                            const r = await fetch({json.dumps(paged_url)}, {{credentials:'include'}});
                            return await r.text();
                        }} catch(e) {{ return ''; }}
                    }}""")
                    if raw:
                        homes_p, _ = _parse_gis_response(raw, paged_url)
                        if homes_p:
                            api_homes.extend(homes_p)
                            print(f"    [Pagination] Page {pg}: +{len(homes_p)} homes")
                        else:
                            break
                except Exception as e:
                    print(f"    [Pagination] Page {pg} error: {e}")
                    break

        # ── Primary: use intercepted API data ──────────────────────
        if api_homes:
            # Deduplicate across pages — same listing can appear on page 1 and 2.
            # IMPORTANT: if we can't compute a stable ID, always keep the home.
            # Never silently drop a home just because we can't identify it.
            seen_ids: set = set()
            unique_homes = []
            for h in api_homes:
                # Try every field name Redfin has used for a stable listing ID
                hid = None
                for id_field in ("listingId", "mlsId", "propertyId", "id"):
                    v = h.get(id_field)
                    if v:
                        hid = str(v)
                        break
                if hid is None:
                    # Fallback: address string + price
                    addr  = str(_val(h.get("address")) or h.get("address") or "")
                    price = str(_val(h.get("price"))   or h.get("price")   or "")
                    combo = addr + "|" + price
                    if combo != "|":
                        hid = combo

                if hid is not None:
                    if hid in seen_ids:
                        continue      # genuine duplicate — skip
                    seen_ids.add(hid)
                # hid is None means we couldn't fingerprint it — keep it anyway
                unique_homes.append(h)

            api_homes = unique_homes
            print(f"    Parsing {len(api_homes)} homes from API intercept (after dedup)")
            for home in api_homes:
                try:
                    listing = build_listing(home, market_name, state, criteria, require_pool, min_yield)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    print(f"    Home parse error: {e}")
        else:
            # ── Fallback: parse rendered DOM cards ─────────────────
            print(f"    API interception empty — falling back to DOM parsing")
            card_selectors = [
                ".HomeCardContainer",
                "[data-rf-test-id='mapHomeCard']",
                "[class*='HomeCard']",
                "[class*='homeCard']",
                "[class*='listing-card']",
                "[class*='property-card']",
                "article[class*='home']",
                "[data-listing-id]",
            ]

            # Scroll through the full page so Redfin lazy-loads all cards,
            # keep going until the card count stops growing.
            best_sel = None
            prev_card_count = 0
            for scroll_y in [800, 1600, 2800, 4200, 6000, 8000, 11000, 15000, 0]:
                await page.evaluate(f"window.scrollTo(0, {scroll_y})")
                await page.wait_for_timeout(400)
                for sel in card_selectors:
                    try:
                        c = await page.query_selector_all(sel)
                        if len(c) > prev_card_count:
                            prev_card_count = len(c)
                            best_sel = sel
                    except Exception:
                        continue
                if scroll_y > 4000 and prev_card_count == prev_card_count:
                    pass  # keep scrolling

            cards = []
            if best_sel:
                try:
                    cards = await page.query_selector_all(best_sel)
                except Exception:
                    pass

            page_title = await page.title()
            print(f"    DOM fallback: {len(cards)} cards  (page: {page_title!r})")

            # ── Batch JS property-type scan (single round-trip for all cards) ──
            # outerHTML includes hidden labels, CSS class names, data-* attrs, aria-labels
            # that inner_text() misses — critical for catching condos without "condo" in visible text
            card_type_hints = []
            try:
                card_type_hints = await page.evaluate("""() => {
                    const selectors = [
                        '.HomeCardContainer',
                        '[data-rf-test-id="mapHomeCard"]',
                        '[class*="HomeCard"]',
                        '[class*="homeCard"]'
                    ];
                    let els = [];
                    for (const sel of selectors) {
                        els = Array.from(document.querySelectorAll(sel));
                        if (els.length > 0) break;
                    }
                    return els.slice(0, 200).map(el => {
                        const html = (el.outerHTML || '').toLowerCase();
                        // Also check all visible/hidden text, aria-labels, titles
                        const attrText = Array.from(el.querySelectorAll('*'))
                            .map(e => [
                                e.getAttribute('aria-label') || '',
                                e.getAttribute('title') || '',
                                e.className || '',
                            ].join(' '))
                            .join(' ')
                            .toLowerCase();
                        const combined = html + ' ' + attrText;
                        return {
                            isCondo:     /\\bcondo\\b|\\bco-op\\b|\\bcondominium\\b|\\bcooperative\\b/.test(combined),
                            isTownhouse: /\\btownhouse\\b|\\btown.?home\\b/.test(combined),
                            isDuplex:    /\\bduplex\\b|\\btri-?plex\\b|\\bquadplex\\b|\\bmulti-?family\\b/.test(combined),
                        };
                    });
                }""")
            except Exception as e:
                print(f"    JS card-type scan error: {e}")

            min_price = criteria.get("min_price", 0)
            max_price = criteria.get("max_price", 9999999)
            min_beds  = criteria.get("min_beds",  1)
            min_baths = criteria.get("min_baths", 1)
            max_dom   = criteria.get("max_dom",   30)
            min_sqft  = criteria.get("min_sqft",  0)
            max_sqft  = criteria.get("max_sqft",  999999)
            keywords  = [k.strip().lower() for k in criteria.get("keywords", "").split(",") if k.strip()]

            for _ci, card in enumerate(cards[:200]):
                try:
                    text  = await card.inner_text()
                    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]

                    price_str = next(
                        (l for l in lines if l.startswith("$") and any(c.isdigit() for c in l) and len(l) < 20),
                        None,
                    )
                    if not price_str:
                        price_str = next(
                            (l for l in lines if "$" in l and any(c.isdigit() for c in l) and len(l) < 20), None
                        )
                    price = parse_price(price_str)
                    if not price or not (min_price <= price <= max_price):
                        continue

                    beds, baths = None, None
                    for line in lines:
                        b, ba = parse_beds_baths(line)
                        if b:  beds  = b
                        if ba: baths = ba
                    if not beds or beds < min_beds:
                        continue
                    if min_baths > 1 and baths and baths < min_baths:
                        continue

                    addr = _normalize_addr(extract_address(text, lines))

                    sqft_match = re.search(r"([\d,]+)\s*[Ss]q", text)
                    sqft = int(sqft_match.group(1).replace(",", "")) if sqft_match else 0
                    if sqft and (sqft < min_sqft or sqft > max_sqft):
                        continue

                    dom = check_dom(text)
                    if dom is not None and dom > max_dom:
                        continue
                    # For tight filters (1d / 7d), unknown DOM means we can't
                    # confirm recency — skip it to avoid stale listings slipping through.
                    if dom is None and max_dom <= 7:
                        continue

                    # ── Grab the listing-specific link ─────────────────────────
                    # Redfin cards have multiple <a> tags; we want the one pointing
                    # to the actual listing (/home/ path), not nav/logo links.
                    link = None
                    try:
                        all_anchors = await card.query_selector_all("a[href]")
                        for _a in all_anchors:
                            _href = await _a.get_attribute("href")
                            if _href and "/home/" in _href:
                                link = _href
                                break
                        if not link:
                            # Fallback: any deep path (at least 3 slashes, not just "/")
                            for _a in all_anchors:
                                _href = await _a.get_attribute("href")
                                if _href and _href.startswith("/") and _href.count("/") >= 3:
                                    link = _href
                                    break
                    except Exception:
                        pass
                    full_url = (
                        f"https://www.redfin.com{link}"
                        if link and link.startswith("/")
                        else (link or "")
                    )
                    # Fallback: zip-based market URL (guaranteed to work)
                    if not full_url or full_url == "https://www.redfin.com":
                        zip_code = _zip_lookup(market_name)
                        if zip_code:
                            full_url = f"https://www.redfin.com/zipcode/{zip_code}/filter/property-type=house,condo,townhouse"
                        else:
                            slug = market_name.replace(" ", "-")
                            full_url = f"https://www.redfin.com/{state}/{slug}/filter/property-type=house,condo,townhouse"

                    # ── Property type filter (4 layers) ────────────────────────
                    fb_allowed = set(criteria.get("home_types", "1,2,3").split(","))
                    only_houses = "2" not in fb_allowed and "3" not in fb_allowed

                    if only_houses:
                        # Layer 1: JS batch hint (outerHTML, class names, aria-labels)
                        ct = card_type_hints[_ci] if _ci < len(card_type_hints) else {}

                        # Layer 2: visible text keywords
                        text_is_condo = bool(re.search(
                            r'\bcondo\b|\bcondominium\b|\bco-?op\b|\bcooperative\b'
                            r'|\bunit\s*#|\bapt\.?\s*\d|\bfloor\s*\d'
                            r'|\bmaintenance fee\b|\bcondo fee\b|\bassociation fee\b',
                            text, re.IGNORECASE
                        ))
                        text_is_townhouse = bool(re.search(
                            r'\btownhouse\b|\btown\s*home\b|\bduplex\b|\btri-?plex\b|\bquadplex\b|\bmulti-?family\b',
                            text, re.IGNORECASE
                        ))

                        is_condo     = ct.get('isCondo', False) or text_is_condo
                        is_townhouse = ct.get('isTownhouse', False) or ct.get('isDuplex', False) or text_is_townhouse

                        if is_condo or is_townhouse:
                            continue

                        # Layer 3: address unit-number check (conservative)
                        full_addr = addr or ""
                        if re.search(
                            r'\bUnit\s+\w{2,}|\bApt\.?\s+\w{2,}|\bSuite\s+\w{2,}'
                            r'|#\s*[A-Z]\d|#\s*\d[A-Z]|#\s*\d{2,}'
                            r'|\bFl\.?\s*\d{1,2}\b|\bFloor\s+\d{1,2}\b',
                            full_addr, re.IGNORECASE
                        ):
                            continue

                        # Layer 4: listing URL check — Redfin encodes unit/apt in the slug
                        link_lower = (link or "").lower()
                        if re.search(r'/unit-\d{2,}|/apt-\d{2,}|/unit-[a-z]\d|/apt-[a-z]\d', link_lower):
                            continue

                    elif "2" not in fb_allowed:  # townhouses allowed but not condos
                        ct = card_type_hints[_ci] if _ci < len(card_type_hints) else {}
                        if ct.get('isCondo') or re.search(r'\bcondo\b|\bco-?op\b|\bcondominium\b', text, re.IGNORECASE):
                            continue

                    elif "3" not in fb_allowed:  # condos allowed but not townhouses
                        ct = card_type_hints[_ci] if _ci < len(card_type_hints) else {}
                        if ct.get('isTownhouse') or ct.get('isDuplex') or re.search(r'\btownhouse\b|\bduplex\b', text, re.IGNORECASE):
                            continue

                    # pool_status: check inner text, then outerHTML for hidden amenity labels
                    pool_status = check_pool(text)
                    if pool_status is None:
                        try:
                            outer = await card.evaluate("el => el.outerHTML")
                            pool_status = check_pool(outer)
                        except Exception:
                            pass
                    pool_confirmed = pool_status is True

                    # Hard-reject only when listing explicitly denies a pool.
                    # Ambiguous (None) → trust Redfin's amenities=pool URL filter.
                    if require_pool and pool_status is False:
                        continue

                    if keywords:
                        hay = text.lower()
                        if not all(k in hay for k in keywords):
                            continue

                    gross_yield, cap_rate, airbnb_est = estimate_yield(price, beds or 2, market_name, has_pool=pool_confirmed or require_pool)
                    if gross_yield < min_yield:
                        continue

                    has_hoa   = bool(re.search(r"\bhoa\b|\bhomeowners?\s+association\b", text, re.IGNORECASE))
                    hoa_match = re.search(r"hoa[:\s\$]+([\d,]+)", text, re.IGNORECASE)
                    hoa_amt   = int(hoa_match.group(1).replace(",", "")) if hoa_match else None

                    img_el  = await card.query_selector("img")
                    img_src = await img_el.get_attribute("src") if img_el else None
                    if img_src and img_src.startswith("data:"):
                        img_src = None

                    tags = []
                    if re.search(r"\bacre\b|\bacres\b|\bacreage\b", text, re.IGNORECASE):
                        tags.append("acreage")
                    if re.search(r"\bhot tub\b|\bjacuzzi\b", text, re.IGNORECASE):
                        tags.append("hot tub")
                    if re.search(r"\bcabin\b", text, re.IGNORECASE):
                        tags.append("cabin")
                    if re.search(r"\bmountain view\b|\bviews\b", text, re.IGNORECASE):
                        tags.append("views")
                    if re.search(r"\bcreek\b|\bwaterfront\b|\briver\b", text, re.IGNORECASE):
                        tags.append("waterfront")

                    listings.append({
                        # DOM-card path has no API object — address-only stable id
                        "id":         _stable_id(None, addr) or abs(hash(addr)),
                        "addr":       addr,
                        "city":       market_name,
                        "state":      state,
                        "lat":        None,   # DOM cards carry no coordinates
                        "lng":        None,
                        "price":      price,
                        "beds":       beds or 0,
                        "baths":      baths or 0,
                        "sqft":       sqft,
                        "dom":        dom if dom is not None else -1,  # -1 = unknown
                        "grossYield": gross_yield,
                        "capRate":    cap_rate,
                        "airbnbEst":  airbnb_est,
                        "tags":       list(set(tags)),
                        "isNew":      dom is not None and dom <= 1,
                        "hasPool":    pool_confirmed,   # only True when detected in card text
                        "imgSrc":     img_src,
                        "detailUrl":  full_url,
                        "zestimate":  None,
                        "hoa":          has_hoa,
                        "hoaAmt":       hoa_amt,
                        "propertyType": "SINGLE_FAMILY_RESIDENTIAL",
                        "source":       "redfin",
                    })

                except Exception as e:
                    print(f"    Card error: {e}")
                    continue

    except Exception as e:
        print(f"    Page error for {market_name}: {e}")
    finally:
        await context.close()

    # Final dedup on listings — catches any duplicates produced by multiple
    # API strategies (on_response + performance timeline + direct call) all
    # returning overlapping data. Dedup by listing id (hash of addr+price).
    seen_listing_ids: set = set()
    unique_listings = []
    for lst in listings:
        lid = lst.get("id")
        if lid and lid in seen_listing_ids:
            continue
        if lid:
            seen_listing_ids.add(lid)
        unique_listings.append(lst)
    listings = unique_listings

    print(f"    {len(listings)} matched in {market_name}")
    return listings


# ── Legacy scrape_market (kept for /api/scan compatibility) ────
async def scrape_market(browser, market, max_dom=30, require_pool=False):
    criteria = {**CRITERIA, "max_dom": max_dom}
    url = build_redfin_url(market["name"], market["state"], criteria, pool=require_pool)
    return await scrape_url(browser, url, market["name"], market["state"], criteria, require_pool=require_pool)


async def run_scan(max_dom=30, pool_states=None):
    if pool_states is None:
        pool_states = POOL_STATES

    all_listings = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        for market in MARKETS:
            require_pool = market["state"] in pool_states
            results = await scrape_market(browser, market, max_dom=max_dom, require_pool=require_pool)
            all_listings.extend(results)
            await asyncio.sleep(random.randint(4, 8))
        await browser.close()

    all_listings.sort(key=lambda x: x["grossYield"], reverse=True)
    return all_listings


if __name__ == "__main__":
    results = asyncio.run(run_scan())
    print(json.dumps(results, indent=2))
    print(f"\nTotal: {len(results)} listings")
