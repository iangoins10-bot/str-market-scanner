"""
Price tracker — persists listing prices across scans and detects cuts.
Data is stored in data/price_history.json keyed by listing ID.
"""
import json, os, datetime

_HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "price_history.json"
)


def _load() -> dict:
    if not os.path.exists(_HISTORY_FILE):
        return {}
    try:
        with open(_HISTORY_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save(h: dict):
    os.makedirs(os.path.dirname(_HISTORY_FILE), exist_ok=True)
    with open(_HISTORY_FILE, "w") as f:
        json.dump(h, f, indent=2)


def update_prices(listings: list) -> list:
    """
    Record current prices for all listings in the history file.
    Returns the same listings, each annotated with a 'priceDrop' dict if
    the price has decreased since the last recorded value.
    """
    history = _load()
    now = datetime.datetime.now().isoformat()
    annotated = []

    for lst in listings:
        lid = str(lst.get("id") or lst.get("listingId") or "").strip()
        price = lst.get("price")
        if not lid or not price:
            annotated.append(lst)
            continue

        entry = history.get(lid)

        if entry:
            old_price = entry.get("price", 0)
            if old_price and isinstance(old_price, (int, float)) and price < old_price:
                drop_amt = old_price - price
                drop_pct = round(drop_amt / old_price * 100, 1)
                lst = dict(lst)
                first_seen = entry.get("firstSeen", now)
                try:
                    days_tracked = max(0, (
                        datetime.datetime.now() -
                        datetime.datetime.fromisoformat(first_seen[:19])
                    ).days)
                except Exception:
                    days_tracked = 0

                lst["priceDrop"] = {
                    "oldPrice":    old_price,
                    "dropAmount":  drop_amt,
                    "dropPct":     drop_pct,
                    "firstSeen":   first_seen,
                    "daysTracked": days_tracked,
                }
                # Append old price to history log (keep last 20 entries)
                ph = entry.get("priceHistory", [])
                ph.append({"price": old_price, "date": entry.get("lastSeen", now)})
                entry["priceHistory"] = ph[-20:]

            # Update stored values
            entry["price"]    = price
            entry["lastSeen"] = now
            entry["dom"]      = lst.get("dom")
            # Update address/url if we now have better data
            if lst.get("addr"):  entry["address"] = lst["addr"]
            if lst.get("url"):   entry["url"]     = lst["url"]
        else:
            history[lid] = {
                "price":        price,
                "address":      lst.get("addr") or lst.get("address", ""),
                "market":       lst.get("city") or lst.get("market", ""),
                "state":        lst.get("state", ""),
                "beds":         lst.get("beds"),
                "baths":        lst.get("baths"),
                "sqft":         lst.get("sqft"),
                "url":          lst.get("url", ""),
                "dom":          lst.get("dom"),
                "firstSeen":    now,
                "lastSeen":     now,
                "priceHistory": [],
            }

        annotated.append(lst)

    _save(history)
    return annotated


def get_price_drops(min_drop_pct: float = 0.5) -> list:
    """
    Return all tracked listings that have experienced at least one price drop.
    Sorted by drop percentage descending.
    """
    history = _load()
    drops = []

    for lid, entry in history.items():
        ph = entry.get("priceHistory", [])
        if not ph:
            continue

        original = ph[0]["price"]   # price when first seen
        current  = entry["price"]

        if current < original:
            drop_amt = original - current
            drop_pct = round(drop_amt / original * 100, 1)
            if drop_pct >= min_drop_pct:
                # Calculate total drop from peak (in case of multiple cuts)
                peak = max(p["price"] for p in ph) if ph else original
                peak = max(peak, original)
                total_drop_pct = round((peak - current) / peak * 100, 1)

                drops.append({
                    "id":            lid,
                    "address":       entry.get("address", ""),
                    "market":        entry.get("market", ""),
                    "state":         entry.get("state", ""),
                    "currentPrice":  current,
                    "originalPrice": original,
                    "peakPrice":     peak,
                    "dropAmount":    original - current,
                    "dropPct":       drop_pct,
                    "totalDropPct":  total_drop_pct,
                    "dom":           entry.get("dom"),
                    "beds":          entry.get("beds"),
                    "baths":         entry.get("baths"),
                    "sqft":          entry.get("sqft"),
                    "url":           entry.get("url", ""),
                    "firstSeen":     entry.get("firstSeen"),
                    "lastSeen":      entry.get("lastSeen"),
                    "priceHistory":  ph,
                    "cutCount":      len(ph),
                })

    drops.sort(key=lambda x: x["dropPct"], reverse=True)
    return drops


def get_stats() -> dict:
    """Summary stats for the price history database."""
    history = _load()
    total   = len(history)
    with_drops = sum(
        1 for e in history.values()
        if e.get("priceHistory") and e["price"] < e["priceHistory"][0]["price"]
    )
    return {
        "totalTracked": total,
        "withDrops":    with_drops,
        "markets":      len({e.get("market") for e in history.values() if e.get("market")}),
    }


def get_tracked_markets() -> list:
    """Return unique [{market, state}] from all tracked listings."""
    history = _load()
    seen    = set()
    markets = []
    for entry in history.values():
        m = entry.get("market", "")
        s = entry.get("state", "")
        if m and s and (m, s) not in seen:
            seen.add((m, s))
            markets.append({"market": m, "state": s})
    return markets
