"""
Address geocoding fallback for listings that arrive without coordinates
(e.g. when the scrape falls back to DOM-card parsing, which has no latLong).

Uses the free US Census batch geocoder — no API key, accepts up to 10k
addresses per POST. Results are cached in data/geocode_cache.json keyed by
"street|city|state" so repeat scans never re-hit the API.
"""
import csv
import io
import json
import os

import httpx

_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "geocode_cache.json"
)
_CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"

_cache = None


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        try:
            with open(_CACHE_FILE) as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}
    return _cache


def _save_cache():
    if _cache is None:
        return
    os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
    with open(_CACHE_FILE, "w") as f:
        json.dump(_cache, f)


def _key(street: str, city: str, state: str) -> str:
    return f"{street}|{city}|{state}".lower()


async def geocode_missing(listings: list) -> int:
    """Fill lat/lng on listings that lack them. Returns how many got coords.

    Cache misses are sent to the Census batch geocoder in one POST. Unmatched
    addresses are cached as null so they aren't retried every scan.
    """
    todo = [
        l for l in listings
        if l.get("lat") is None and l.get("addr") and l["addr"] != "Unknown"
    ]
    if not todo:
        return 0

    cache = _load_cache()
    filled = 0
    misses = {}   # key -> listing(s)

    for l in todo:
        k = _key(l["addr"], l["city"], l["state"])
        if k in cache:
            hit = cache[k]
            if hit:
                l["lat"], l["lng"] = hit[0], hit[1]
                filled += 1
        else:
            misses.setdefault(k, []).append(l)

    if misses:
        rows = io.StringIO()
        w = csv.writer(rows)
        keys = list(misses.keys())
        for i, k in enumerate(keys):
            sample = misses[k][0]
            # Census CSV format: id, street, city, state, zip
            w.writerow([i, sample["addr"], sample["city"], sample["state"], ""])

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    _CENSUS_URL,
                    data={"benchmark": "Public_AR_Current"},
                    files={"addressFile": ("addrs.csv", rows.getvalue().encode(), "text/csv")},
                )
                resp.raise_for_status()
                # Response CSV: id, input, match flag, match type, matched addr, "lng,lat", ...
                for rec in csv.reader(io.StringIO(resp.text)):
                    if len(rec) < 6 or rec[2] != "Match":
                        continue
                    try:
                        idx = int(rec[0])
                        lng_s, lat_s = rec[5].split(",")
                        lat, lng = float(lat_s), float(lng_s)
                    except (ValueError, IndexError):
                        continue
                    k = keys[idx]
                    cache[k] = [lat, lng]
                    for l in misses[k]:
                        l["lat"], l["lng"] = lat, lng
                        filled += 1
        except Exception as e:
            print(f"    [geocode] Census batch failed: {e}")
            return filled   # don't poison the cache on transport errors

        # Cache non-matches as null so they aren't retried every scan
        for k in keys:
            if k not in cache:
                cache[k] = None
        _save_cache()

    return filled
