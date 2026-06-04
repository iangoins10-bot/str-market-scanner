"""
Market Discovery Engine
=======================
Scans regulations.comparent.com for STR-friendly markets that are NOT in the
main scanner yet.  For each market found it extracts:
  • Overall STR status (allowed / restricted / banned / unregulated)
  • NOO (Non-Owner-Occupied investor) status
  • Permit / license requirement
  • Minimum & maximum night stay limits
  • Occupancy cap (max guests)
  • Zoning restrictions (flag + note)
  • Annual rental-days cap
  • Tax rate note
  • Fee / license cost note
  • Up to 5 key regulatory rules verbatim from the source page
  • NOO-friendliness score (0–100)

Usage:
  results = await discover_state("FL", existing_cities={"Miami","Orlando"})
"""

import asyncio
import datetime
import re

import httpx
from html.parser import HTMLParser


# ── State slug map (matches regulations.comparent.com URL scheme) ─────────────
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

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    )
}

# ── HTML Parsers ──────────────────────────────────────────────────────────────

class _CityLinkParser(HTMLParser):
    """Extract (city_name, city_slug) pairs from a state index page."""
    def __init__(self, state_slug: str):
        super().__init__()
        self.state_slug = state_slug
        self.cities: list[tuple[str, str]] = []
        self._in_link = False
        self._cur_slug: str | None = None
        self._buf = ''

    def handle_starttag(self, tag, attrs):
        if tag != 'a':
            return
        href = dict(attrs).get('href', '')
        pattern = rf'/regulations/{re.escape(self.state_slug)}/([^/]+)/?$'
        m = re.match(pattern, href)
        if m:
            self._cur_slug = m.group(1)
            self._in_link = True
            self._buf = ''

    def handle_data(self, data):
        if self._in_link:
            self._buf += data

    def handle_endtag(self, tag):
        if tag == 'a' and self._in_link:
            name = self._buf.strip()
            if name and self._cur_slug:
                self.cities.append((name, self._cur_slug))
            self._in_link = False
            self._cur_slug = None
            self._buf = ''


class _TextExtractor(HTMLParser):
    """Strip tags, skip nav/script/style, collapse blank lines."""
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'nav', 'footer', 'header'):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav', 'footer', 'header'):
            self._skip = False
        if tag in ('p', 'li', 'div', 'h1', 'h2', 'h3', 'h4', 'td', 'tr', 'section'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def get_text(self) -> str:
        return re.sub(r'\n{3,}', '\n\n', ''.join(self.parts)).strip()


# ── Regulation Parser ─────────────────────────────────────────────────────────

def parse_city_regs(html: str, source_url: str, city: str, state: str) -> dict:
    """
    Parse a regulations.comparent.com city page into structured data.
    Returns a dict ready to send to the frontend.
    """
    p = _TextExtractor()
    p.feed(html)
    text = p.get_text()
    tl = text.lower()

    # ── Overall STR operating status ─────────────────────────────
    str_status = 'unknown'
    if re.search(r'\bprohibited\b|\bstr.*\bban\b|\billegal\b|\bnot\s+allowed\b|\bnot\s+permitted\b', tl):
        str_status = 'banned'
    elif re.search(r'\bunregulated\b|\bno\s+specific\s+reg', tl):
        str_status = 'unregulated'
    elif re.search(r'\ballowed\b|\bpermitted\b|\blicensed\b|\blegal\b', tl):
        str_status = 'allowed'
    elif re.search(r'\brestrict', tl):
        str_status = 'restricted'

    # ── NOO (Non-Owner-Occupied / investor-owned) status ─────────
    noo_status = 'unknown'
    owner_occ_only = bool(re.search(
        r'owner.?occupied\s+only|must\s+be\s+(?:the\s+)?(?:owner|primary|principal)\s+resid'
        r'|primary\s+resid\w+\s+only|hosted\s+only|owner\s+must\s+reside',
        tl
    ))
    if owner_occ_only:
        noo_status = 'banned'
    elif re.search(r'non.?owner.?occupied.*\bprohibit|\bnoo\b.*\bban\b|\bnon.?owner.?occupied.*\bnot\s+permit', tl):
        noo_status = 'banned'
    elif re.search(r'non.?owner.?occupied.*\ballowed\b|\bnoo\b.*\ballowed\b|investor.?owned.*\ballowed\b|unhosted.*\ballowed\b', tl):
        noo_status = 'allowed'
    elif re.search(r'non.?owner.?occupied|investor.?owned|unhosted\s+rental|noo\b', tl):
        noo_status = 'restricted'
    elif str_status == 'unregulated':
        noo_status = 'likely_allowed'  # unregulated = no restrictions on NOO

    # ── Permit / registration requirement ────────────────────────
    permit_req = None
    if re.search(r'permit\s+(?:is\s+)?required|must\s+obtain\s+(?:a\s+)?permit|registration\s+required'
                 r'|license\s+required|must\s+register\b', tl):
        permit_req = True
    elif re.search(r'no\s+permit\s+required|permit\s+not\s+required|no\s+registration', tl):
        permit_req = False

    # ── Minimum stay ─────────────────────────────────────────────
    min_stay = None
    for pat in [
        r'minimum\s+(?:stay|night)[^\d]{0,20}(\d+)\s*(?:night|day)',
        r'(\d+)[- ]night\s+minimum',
        r'min(?:imum)?\s+(\d+)\s*night',
        r'(?:stay|rental)\s+(?:of\s+)?at\s+least\s+(\d+)\s*night',
    ]:
        m = re.search(pat, tl)
        if m:
            min_stay = int(m.group(1))
            break

    # ── Maximum stay ─────────────────────────────────────────────
    max_stay = None
    m = re.search(r'maximum\s+(?:stay|night|nights?)[^\d]{0,20}(\d+)\s*(?:night|day)', tl)
    if not m:
        m = re.search(r'(?:stay|rental)\s+(?:of\s+)?no\s+more\s+than\s+(\d+)\s*night', tl)
    if m:
        max_stay = int(m.group(1))

    # ── Occupancy cap ────────────────────────────────────────────
    occupancy_cap = None
    for pat in [
        r'(?:maximum|max)\s+occupancy[^\d]{0,20}(\d+)',
        r'occupancy\s+(?:is\s+)?limited?\s+to\s+(\d+)',
        r'(?:no\s+more\s+than|maximum\s+of)\s+(\d+)\s+(?:person|guest|people)',
        r'(\d+)\s+(?:person|guest|people)\s+(?:maximum|max|limit)',
    ]:
        m = re.search(pat, tl)
        if m:
            occupancy_cap = int(m.group(1))
            break

    # ── Zoning restrictions ──────────────────────────────────────
    zoning_restricted = bool(re.search(r'\bzon(?:e|ing|ed|es)\b', tl))
    zoning_note = None
    if zoning_restricted:
        for pat in [
            r'(?:only|allowed|permitted)\s+in\s+([^.\n]{10,100}(?:zone|district|area)[^.\n]{0,60})',
            r'(?:zone|district)\s+[A-Z0-9\-]+\s+(?:only|required)',
            r'zoning[^\n]{10,120}',
        ]:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                zoning_note = m.group(0).strip()[:150]
                break

    # ── Annual rental days cap ───────────────────────────────────
    days_cap = None
    for pat in [
        r'(\d+)\s+days?\s+(?:per\s+year|annually|per\s+calendar\s+year)',
        r'(?:limit|cap|maximum)\s+(?:of\s+)?(\d+)\s+(?:rental\s+)?days?\s+(?:per|a)\s+year',
    ]:
        m = re.search(pat, tl)
        if m:
            days_cap = int(m.group(1))
            break

    # ── Tax rate ────────────────────────────────────────────────
    tax_note = None
    m = re.search(r'(\d+(?:\.\d+)?)\s*%[^\n]{0,60}(?:tax|lodging|occupancy|transient)', text, re.I)
    if not m:
        m = re.search(r'(?:tax|lodging|occupancy)[^\n]{0,40}?(\d+(?:\.\d+)?)\s*%', text, re.I)
    if m:
        tax_note = m.group(0).strip()[:80]

    # ── License / permit fee ────────────────────────────────────
    fee_note = None
    m = re.search(r'\$\s*([\d,]+(?:\.\d+)?)[^\n]{0,60}(?:fee|license|permit|registration)', text, re.I)
    if m:
        fee_note = m.group(0).strip()[:80]

    # ── Extract up to 5 key rule lines ──────────────────────────
    rule_kws = (
        'permit', 'license', 'registr', 'tax', 'zoning', 'occupancy', 'noise',
        'parking', 'insurance', 'inspect', 'renew', 'cap', 'limit', 'ban',
        'prohibit', 'allow', 'restrict', 'hosted', 'owner', 'investor', 'noo',
        'minimum', 'maximum', 'stay', 'night', 'unregulated',
    )
    skip_pats = (
        ' | ', 'how to obtain', 'short-term rental regulations in ',
        'are airbnbs', 'are short-term rentals', 'regulations.comparent',
        'click here', 'read more', 'learn more',
    )
    rules = []
    for line in text.splitlines():
        ls = line.strip()
        ll = ls.lower()
        if len(ls) < 35 or len(ls) > 400:
            continue
        if any(sp in ll for sp in skip_pats):
            continue
        if any(kw in ll for kw in rule_kws):
            rules.append(ls[:200])
        if len(rules) >= 5:
            break

    # ── NOO-friendliness score (0–100) ──────────────────────────
    score = 50  # neutral start
    if str_status == 'unregulated':  score = 88
    elif str_status == 'allowed':    score = 72
    elif str_status == 'restricted': score = 38
    elif str_status == 'banned':     score = 2

    if noo_status == 'banned' or owner_occ_only:
        score = min(score, 3)
    elif noo_status == 'allowed':
        score = min(100, score + 15)
    elif noo_status == 'likely_allowed':
        score = min(100, score + 8)
    elif noo_status == 'restricted':
        score = min(score, 35)

    if permit_req is False:
        score = min(100, score + 8)
    if permit_req is True:
        score = max(0, score - 5)   # permit required is fine, small penalty
    if min_stay and min_stay >= 30:
        score = min(score, 18)      # 30-night min = effectively not STR
    elif min_stay and min_stay >= 7:
        score = min(score, 55)      # week minimum — still workable
    if days_cap is not None:
        if days_cap < 30:
            score = min(score, 10)
        elif days_cap < 90:
            score = min(score, 30)
        elif days_cap < 180:
            score = min(score, 50)
    if zoning_restricted:
        score = min(score, score - 5)   # zoning complicates things

    score = max(0, min(100, score))

    return {
        'city':             city,
        'state':            state,
        'strStatus':        str_status,
        'nooStatus':        noo_status,
        'ownerOccOnly':     owner_occ_only,
        'permitReq':        permit_req,
        'minStay':          min_stay,
        'maxStay':          max_stay,
        'occupancyCap':     occupancy_cap,
        'zoningRestricted': zoning_restricted,
        'zoningNote':       zoning_note,
        'daysCap':          days_cap,
        'taxNote':          tax_note,
        'feeNote':          fee_note,
        'rules':            rules,
        'nooScore':         score,
        'sourceUrl':        source_url,
    }


# ── Network helpers ───────────────────────────────────────────────────────────

async def fetch_state_cities(state_slug: str) -> list[tuple[str, str]]:
    """Return list of (city_name, city_slug) from the state index page."""
    url = f"https://regulations.comparent.com/regulations/{state_slug}/"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=_HEADERS)
            if resp.status_code != 200:
                print(f"[discover] State page {state_slug} returned HTTP {resp.status_code}")
                return []
            parser = _CityLinkParser(state_slug)
            parser.feed(resp.text)
            cities = parser.cities
            print(f"[discover] {state_slug}: found {len(cities)} cities on index page")
            return cities
    except Exception as e:
        print(f"[discover] Failed to fetch state page {state_slug}: {e}")
        return []


async def _check_one_city(
    city_name: str,
    city_slug: str,
    state_code: str,
    state_slug: str,
    sem: asyncio.Semaphore,
) -> dict:
    """Fetch and parse one city's regulations page (rate-limited via semaphore)."""
    url = f"https://regulations.comparent.com/regulations/{state_slug}/{city_slug}/"
    async with sem:
        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=_HEADERS)
                if resp.status_code == 404:
                    return {
                        'city': city_name, 'state': state_code,
                        'strStatus': 'not_found', 'nooScore': -1,
                        'sourceUrl': url,
                    }
                if resp.status_code != 200:
                    return {
                        'city': city_name, 'state': state_code,
                        'strStatus': 'error', 'nooScore': -1,
                        'sourceUrl': url,
                    }
                return parse_city_regs(resp.text, url, city_name, state_code)
        except Exception as e:
            return {
                'city': city_name, 'state': state_code,
                'strStatus': 'error', 'nooScore': -1,
                'error': str(e), 'sourceUrl': url,
            }


# ── Discovery cache ───────────────────────────────────────────────────────────

_discovery_cache: dict = {}
_DISCOVERY_TTL = 43_200   # 12 hours


async def discover_state(
    state_code: str,
    existing_cities: set | None = None,
    include_banned: bool = False,
    concurrency: int = 8,
) -> dict:
    """
    Discover STR-friendly markets in a state.

    Args:
        state_code:      Two-letter state abbreviation, e.g. "FL"
        existing_cities: Set of city names already in the scanner (case-insensitive)
        include_banned:  Whether to include banned/NOO-banned markets in results
        concurrency:     Max simultaneous HTTP requests

    Returns:
        {
          state, total_cities, checked, scanned_at,
          markets: [ {city, state, strStatus, nooStatus, ...nooScore, ...} ]
        }
    """
    state_code = state_code.upper()
    state_slug = STATE_SLUGS.get(state_code)
    if not state_slug:
        return {'error': f'Unknown state code: {state_code}', 'markets': [], 'total_cities': 0}

    # ── Cache check ──────────────────────────────────────────────
    cache_key = f"{state_code}:{'banned' if include_banned else 'noBanned'}"
    now = datetime.datetime.now().timestamp()
    if cache_key in _discovery_cache:
        entry = _discovery_cache[cache_key]
        if now - entry['ts'] < _DISCOVERY_TTL:
            cached = dict(entry['data'])
            cached['fromCache'] = True
            return cached

    # ── Fetch city list ──────────────────────────────────────────
    cities = await fetch_state_cities(state_slug)
    if not cities:
        return {
            'error': f'Could not find cities for {state_code}. '
                     'regulations.comparent.com may not have data for this state.',
            'markets': [],
            'total_cities': 0,
        }

    # ── Filter out already-known markets ─────────────────────────
    existing_lower = {c.lower() for c in (existing_cities or set())}
    to_check = [
        (name, slug) for name, slug in cities
        if name.lower() not in existing_lower
    ]
    print(f"[discover] {state_code}: checking {len(to_check)} new cities "
          f"(skipped {len(cities)-len(to_check)} already in scanner)")

    # ── Batch-check regulations ──────────────────────────────────
    sem = asyncio.Semaphore(concurrency)
    tasks = [
        _check_one_city(name, slug, state_code, state_slug, sem)
        for name, slug in to_check
    ]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # ── Filter & sort ────────────────────────────────────────────
    markets = []
    for r in raw_results:
        if isinstance(r, Exception) or not isinstance(r, dict):
            continue
        if r.get('strStatus') in ('not_found', 'error'):
            continue
        if not include_banned and r.get('nooScore', 0) <= 3:
            continue
        markets.append(r)

    # Sort: highest NOO score first
    markets.sort(key=lambda m: m.get('nooScore', 0), reverse=True)

    result = {
        'state':        state_code,
        'total_cities': len(cities),
        'checked':      len(to_check),
        'markets':      markets,
        'scanned_at':   datetime.datetime.now().isoformat(),
        'fromCache':    False,
    }

    _discovery_cache[cache_key] = {'data': result, 'ts': now}
    return result
