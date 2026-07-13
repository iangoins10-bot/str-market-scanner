"""
Market intelligence: regulation profiles + scan-derived performance stats.

Powers the Deal Finder. For each market it combines:
  1. A regulation profile (parsed from regulations.comparent.com via
     discover.parse_city_regs) — NOO status, caps, permits, min-stay,
     moratoriums — cached persistently with a 7-day TTL.
  2. Performance stats recorded from every scan (median price, avg yield,
     avg DOM, est ADR / revenue, price-drop rate).
  3. Derived deal gating: human-readable blockers and a 0–1 dealMultiplier
     that discounts (or zeroes) deals in hostile markets.
"""
import asyncio
import datetime
import json
import os
import re
import statistics

import httpx

from discover import parse_city_regs, STATE_SLUGS, _HEADERS

_DATA_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
_REGS_FILE  = os.path.join(_DATA_DIR, "regulations_cache.json")
_STATS_FILE = os.path.join(_DATA_DIR, "market_stats.json")

_REG_TTL_SECONDS = 7 * 24 * 3600   # regulation pages change slowly


def _load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=1)


def _key(city, state):
    return f"{city}|{state}".lower()


# ── Performance stats (recorded on every scan) ─────────────────────────────
def record_market_stats(market: str, state: str, listings: list):
    """Persist a per-market performance snapshot after each scan."""
    if not listings:
        return
    prices = [l["price"] for l in listings if l.get("price")]
    yields = [l["grossYield"] for l in listings if l.get("grossYield", 0) > 0]
    doms   = [l["dom"] for l in listings if l.get("dom", -1) >= 0]
    revs   = [l["airbnbEst"] for l in listings if l.get("airbnbEst", 0) > 0]
    drops  = [l for l in listings if l.get("priceDrop")]

    stats = _load(_STATS_FILE)
    stats[_key(market, state)] = {
        "market":      market,
        "state":       state,
        "ts":          datetime.datetime.now().isoformat(),
        "activeCount": len(listings),
        "medianPrice": int(statistics.median(prices)) if prices else None,
        "avgYield":    round(sum(yields) / len(yields), 1) if yields else None,
        "avgDom":      round(sum(doms) / len(doms), 1) if doms else None,
        "estRevenue":  int(sum(revs) / len(revs)) if revs else None,
        # airbnbEst is annual revenue at 65% occupancy → back out implied ADR
        "estAdr":      int(sum(revs) / len(revs) / (365 * 0.65)) if revs else None,
        "estOccupancy": 65,   # assumption baked into estimate_yield
        "newToday":    sum(1 for l in listings if l.get("isNew")),
        "dropCount":   len(drops),
        "dropRate":    round(len(drops) / len(listings) * 100, 1),
    }
    _save(_STATS_FILE, stats)


def get_market_stats(market: str, state: str):
    return _load(_STATS_FILE).get(_key(market, state))


# ── Regulation profiles (fetched + cached) ─────────────────────────────────
def _city_slug(city: str) -> str:
    return re.sub(r"['.]", "", city.lower()).replace(" ", "-")


async def get_regs(city: str, state: str, force: bool = False) -> dict:
    """Regulation profile for one market, from cache or a fresh fetch."""
    cache = _load(_REGS_FILE)
    k = _key(city, state)
    now = datetime.datetime.now().timestamp()

    if not force and k in cache and now - cache[k].get("_ts", 0) < _REG_TTL_SECONDS:
        return cache[k]

    state_slug = STATE_SLUGS.get(state.upper(), state.lower().replace(" ", "-"))
    url = f"https://regulations.comparent.com/regulations/{state_slug}/{_city_slug(city)}/"
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=_HEADERS)
        if resp.status_code == 200:
            regs = parse_city_regs(resp.text, url, city, state.upper())
        else:
            regs = {"city": city, "state": state.upper(), "strStatus": "not_found",
                    "nooStatus": "unknown", "nooScore": -1, "sourceUrl": url}
    except Exception as e:
        print(f"[intel] regs fetch failed {city}, {state}: {e}")
        # Serve stale cache over nothing
        if k in cache:
            return cache[k]
        regs = {"city": city, "state": state.upper(), "strStatus": "error",
                "nooStatus": "unknown", "nooScore": -1, "sourceUrl": url}

    regs["_ts"] = now
    cache[k] = regs
    _save(_REGS_FILE, cache)
    return regs


# ── State preemption of local STR bans ──────────────────────────────────────
# States whose law limits how far cities can go in banning STRs. The regex
# parser only sees the city page, so without this a state-protected market
# can read as banned/restricted.
STATE_PREEMPTION = {
    "AZ": "Arizona SB 1350 bars cities from banning STRs — local rules limited to permits, taxes, and nuisance",
    "FL": "Florida preempts local STR bans (post-2011 ordinances) — cities may still license and inspect",
    "TN": "Tennessee law grandfathers existing NOO STRs in most cities",
    "TX": "Texas courts have repeatedly limited city STR bans — enforcement varies by city",
}


# ── Deal gating ─────────────────────────────────────────────────────────────
def derive_blockers(regs: dict) -> tuple[list, float]:
    """Turn a regulation profile into (blockers, dealMultiplier).

    Each blocker: {severity: 'block'|'severe'|'caution', label}.
    dealMultiplier scales a listing's deal score; 0 kills the market.
    """
    blockers = []
    mult = 1.0

    noo   = regs.get("nooStatus")
    strst = regs.get("strStatus")

    if strst == "banned":
        blockers.append({"severity": "block", "label": "STRs banned or illegal city-wide"})
        mult = 0.0
    if regs.get("ownerOccOnly") or noo == "banned":
        blockers.append({"severity": "block", "label": "Owner-occupied only — NOO deals blocked"})
        mult = 0.0

    ms = regs.get("minStay")
    if ms and ms >= 30:
        blockers.append({"severity": "block", "label": f"{ms}-night minimum stay — effectively LTR only"})
        mult = 0.0
    elif ms and ms >= 7:
        blockers.append({"severity": "severe", "label": f"{ms}-night minimum stay limits booking volume"})
        mult = min(mult, 0.6)

    dc = regs.get("daysCap")
    if dc is not None:
        if dc < 90:
            blockers.append({"severity": "block", "label": f"Annual cap of {dc} rental days — kills full-time STR"})
            mult = 0.0
        elif dc < 180:
            blockers.append({"severity": "severe", "label": f"Annual cap of {dc} rental days"})
            mult = min(mult, 0.5)
        else:
            blockers.append({"severity": "caution", "label": f"Annual cap of {dc} rental days"})
            mult = min(mult, 0.85)

    if noo == "restricted":
        blockers.append({"severity": "severe", "label": "Non-owner-occupied STRs are restricted — verify eligibility"})
        mult = min(mult, 0.55)

    if strst == "restricted":
        blockers.append({"severity": "severe", "label": "STRs prohibited in some zones or cases — verify the specific parcel"})
        mult = min(mult, 0.5)

    # Very low STR-friendliness score → heavy discount even without a hard blocker
    score = regs.get("nooScore", 50)
    if 0 <= score < 25 and mult > 0.3:
        blockers.append({"severity": "severe", "label": f"Low STR-friendliness score ({score}/100)"})
        mult = min(mult, 0.3)

    # Moratorium / pause / cap-on-permits language in extracted rules
    rules_text = " ".join(regs.get("rules") or []).lower()
    if re.search(r"moratorium|paused?|suspend", rules_text):
        blockers.append({"severity": "block", "label": "Permit moratorium / pause in effect — no new STR permits"})
        mult = 0.0
    elif re.search(r"cap(?:ped)?\s+(?:on|at)\s+\d+|limited\s+number\s+of\s+(?:permits|licenses)|waitlist", rules_text):
        blockers.append({"severity": "severe", "label": "Permit count is capped — availability not guaranteed"})
        mult = min(mult, 0.5)

    if regs.get("zoningRestricted"):
        note = regs.get("zoningNote")
        blockers.append({"severity": "caution",
                         "label": f"Zoning-dependent{': ' + note if note else ' — confirm parcel zoning'}"})
        mult = min(mult, 0.9)

    if regs.get("permitReq"):
        blockers.append({"severity": "caution", "label": "Permit / license required before operating"})
        mult = min(mult, 0.95)

    if strst in ("unknown", "not_found", "error"):
        blockers.append({"severity": "caution", "label": "No regulation data found — verify with the city directly"})
        mult = min(mult, 0.8)

    # State preemption can override a local ban/restriction — soften the gate,
    # but never past an explicit owner-occupied-only rule (those often survive).
    state = (regs.get("state") or "").upper()
    if state in STATE_PREEMPTION and strst in ("banned", "restricted") and not regs.get("ownerOccOnly"):
        blockers.append({"severity": "caution",
                         "label": f"State preemption: {STATE_PREEMPTION[state]}"})
        mult = max(mult, 0.55)

    return blockers, round(mult, 2)


async def get_intel(markets: list) -> list:
    """Batch intel for [(city, state), ...] → regs + stats + gating per market."""
    sem = asyncio.Semaphore(5)

    async def one(city, state):
        async with sem:
            regs = await get_regs(city, state)
        blockers, mult = derive_blockers(regs)
        return {
            "market":         city,
            "state":          state.upper(),
            "regs":           {k: v for k, v in regs.items() if k != "_ts"},
            "stats":          get_market_stats(city, state),
            "blockers":       blockers,
            "dealMultiplier": mult,
            "nooAllowed":     mult > 0,
        }

    return list(await asyncio.gather(*[one(c, s) for c, s in markets]))
