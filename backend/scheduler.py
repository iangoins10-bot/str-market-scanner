"""
Scheduled scans + notification queue.

Persists user-defined scan schedules to data/schedules.json and runs them on a
real APScheduler AsyncIOScheduler. Each run scrapes the market, updates the
price-history tracker, and pushes a notification when new price drops appear.
The frontend polls /api/notifications and raises browser notifications.

The actual scraping is injected as `scan_fn(market, state, criteria, pool)` so
this module stays decoupled from Playwright/main.
"""
import json, os, uuid, datetime, asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

_DATA_DIR        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
_SCHEDULES_FILE  = os.path.join(_DATA_DIR, "schedules.json")
_NOTIFS_FILE     = os.path.join(_DATA_DIR, "notifications.json")

_DOW = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


# ── persistence helpers ────────────────────────────────────────────────────
def _load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default

def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_schedules() -> list:
    return _load(_SCHEDULES_FILE, [])

def save_schedules(schedules: list):
    _save(_SCHEDULES_FILE, schedules)


# ── notifications ──────────────────────────────────────────────────────────
def load_notifications() -> list:
    return _load(_NOTIFS_FILE, [])

def add_notification(kind: str, title: str, body: str, market: str = "", data: dict = None):
    notifs = load_notifications()
    notifs.insert(0, {
        "id":     uuid.uuid4().hex[:12],
        "type":   kind,                 # 'price-drop' | 'scan' | 'error'
        "title":  title,
        "body":   body,
        "market": market,
        "data":   data or {},
        "ts":     datetime.datetime.now().isoformat(),
        "read":   False,
    })
    _save(_NOTIFS_FILE, notifs[:100])   # keep newest 100

def mark_notifications_read(ids=None):
    notifs = load_notifications()
    idset  = set(ids) if ids else None
    for n in notifs:
        if idset is None or n["id"] in idset:
            n["read"] = True
    _save(_NOTIFS_FILE, notifs)

def clear_notifications():
    _save(_NOTIFS_FILE, [])


# ── schedule normalization / validation ────────────────────────────────────
def _normalize_schedule(s: dict) -> dict:
    freq = (s.get("frequency") or "daily").lower()
    if freq not in ("hourly", "daily", "weekly"):
        freq = "daily"
    try:    hour = max(0, min(23, int(s.get("hour", 8))))
    except Exception: hour = 8
    try:    minute = max(0, min(59, int(s.get("minute", 0))))
    except Exception: minute = 0
    dow = (s.get("day_of_week") or "mon").lower()
    if dow not in _DOW:
        dow = "mon"
    crit = s.get("criteria") or {}
    return {
        "id":          s.get("id") or uuid.uuid4().hex[:12],
        "market":      (s.get("market") or "").strip(),
        "state":       (s.get("state") or "").strip().upper(),
        "criteria": {
            "min_price":  int(crit.get("min_price", 150000)),
            "max_price":  int(crit.get("max_price", 99999999)),
            "min_beds":   int(crit.get("min_beds", 2)),
            "max_beds":   int(crit.get("max_beds", 6)),
            "min_baths":  float(crit.get("min_baths", 1.0)),
            "max_dom":    int(crit.get("max_dom", 90)),
            "min_sqft":   int(crit.get("min_sqft", 0)),
            "max_sqft":   int(crit.get("max_sqft", 999999)),
            "keywords":   crit.get("keywords", ""),
            "home_types": crit.get("home_types", "1,2,3"),
        },
        "pool":        bool(s.get("pool", False)),
        "min_yield":   float(s.get("min_yield", 0.0)),
        "frequency":   freq,
        "hour":        hour,
        "minute":      minute,
        "day_of_week": dow,
        "enabled":     bool(s.get("enabled", True)),
        "lastRun":     s.get("lastRun"),
        "lastCount":   s.get("lastCount", 0),
        "lastDrops":   s.get("lastDrops", 0),
        "created":     s.get("created") or datetime.datetime.now().isoformat(),
    }


def _trigger_for(s: dict) -> CronTrigger:
    freq = s["frequency"]
    if freq == "hourly":
        return CronTrigger(minute=s["minute"])
    if freq == "weekly":
        return CronTrigger(day_of_week=s["day_of_week"], hour=s["hour"], minute=s["minute"])
    return CronTrigger(hour=s["hour"], minute=s["minute"])   # daily


def describe(s: dict) -> str:
    freq = s["frequency"]
    t = f"{s['hour']:02d}:{s['minute']:02d}"
    if freq == "hourly":
        return f"Every hour at :{s['minute']:02d}"
    if freq == "weekly":
        return f"Weekly on {s['day_of_week'].capitalize()} at {t}"
    return f"Daily at {t}"


class ScanScheduler:
    """Owns the AsyncIOScheduler and keeps it in sync with schedules.json."""

    def __init__(self, scan_fn):
        # scan_fn: async (market, state, criteria, pool, min_yield) -> list[listing]
        self._scan_fn = scan_fn
        self._sched = AsyncIOScheduler()

    def start(self):
        self._sched.start()
        for s in load_schedules():
            if s.get("enabled", True):
                self._add_job(s)
        print(f"[scheduler] started with {len(self._sched.get_jobs())} active job(s)")

    def shutdown(self):
        try:
            self._sched.shutdown(wait=False)
        except Exception:
            pass

    # ── job wiring ──────────────────────────────────────────────────────
    def _add_job(self, s: dict):
        try:
            self._sched.add_job(
                self._run_job, trigger=_trigger_for(s), args=[s["id"]],
                id=s["id"], replace_existing=True, max_instances=1, coalesce=True,
            )
        except Exception as e:
            print(f"[scheduler] failed to add job {s.get('id')}: {e}")

    def _remove_job(self, sid: str):
        try:
            self._sched.remove_job(sid)
        except Exception:
            pass

    def next_run(self, sid: str):
        job = self._sched.get_job(sid)
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
        return None

    # ── CRUD ────────────────────────────────────────────────────────────
    def list(self) -> list:
        out = []
        for s in load_schedules():
            d = dict(s)
            d["nextRun"]  = self.next_run(s["id"])
            d["describe"] = describe(s)
            out.append(d)
        return out

    def create(self, payload: dict) -> dict:
        s = _normalize_schedule(payload)
        schedules = load_schedules()
        schedules.append(s)
        save_schedules(schedules)
        if s["enabled"]:
            self._add_job(s)
        return s

    def update(self, sid: str, payload: dict):
        schedules = load_schedules()
        out = None
        for i, s in enumerate(schedules):
            if s["id"] == sid:
                merged = {**s, **payload, "id": sid}
                out = _normalize_schedule(merged)
                schedules[i] = out
                break
        if out is None:
            return None
        save_schedules(schedules)
        self._remove_job(sid)
        if out["enabled"]:
            self._add_job(out)
        return out

    def delete(self, sid: str) -> bool:
        schedules = load_schedules()
        new = [s for s in schedules if s["id"] != sid]
        if len(new) == len(schedules):
            return False
        save_schedules(new)
        self._remove_job(sid)
        return True

    # ── the actual run ──────────────────────────────────────────────────
    async def run_now(self, sid: str) -> dict:
        schedules = load_schedules()
        s = next((x for x in schedules if x["id"] == sid), None)
        if not s:
            return {"error": "not found"}
        return await self._execute(s)

    async def _run_job(self, sid: str):
        schedules = load_schedules()
        s = next((x for x in schedules if x["id"] == sid), None)
        if s:
            await self._execute(s)

    async def _execute(self, s: dict) -> dict:
        market, state = s["market"], s["state"]
        print(f"[scheduler] running scan: {market}, {state}")
        try:
            listings = await self._scan_fn(
                market, state, s["criteria"], s.get("pool", False), s.get("min_yield", 0.0)
            )
        except Exception as e:
            print(f"[scheduler] scan error {market}: {e}")
            add_notification("error", f"Scan failed: {market}", str(e)[:200], market)
            self._touch(s["id"], count=0, drops=0)
            return {"error": str(e)}

        if isinstance(listings, dict):
            listings = listings.get("listings", [])
        listings = listings or []

        drops = [l for l in listings if l.get("priceDrop")]
        count = len(listings)
        self._touch(s["id"], count=count, drops=len(drops))

        # Notify on each new price drop (top 5 to avoid spam)
        for l in drops[:5]:
            pd = l["priceDrop"]
            add_notification(
                "price-drop",
                f"Price cut in {market}: -{pd['dropPct']}%",
                f"{l.get('addr','A listing')} dropped ${pd['dropAmount']:,} "
                f"to ${l.get('price'):,}",
                market,
                {"id": l.get("id"), "url": l.get("url"),
                 "price": l.get("price"), "dropPct": pd["dropPct"]},
            )
        if drops:
            print(f"[scheduler] {market}: {count} listings, {len(drops)} price drops")
        else:
            print(f"[scheduler] {market}: {count} listings, no drops")
        return {"count": count, "drops": len(drops)}

    def _touch(self, sid: str, count: int, drops: int):
        schedules = load_schedules()
        for s in schedules:
            if s["id"] == sid:
                s["lastRun"]   = datetime.datetime.now().isoformat()
                s["lastCount"] = count
                s["lastDrops"] = drops
                break
        save_schedules(schedules)
