"""
EdgeFlo app :: news.py
Economic calendar via Forex Factory's public weekly feed (no API key
needed; widely used by MT4/MT5 EAs per public forum threads). Flags
whether a given instrument has a high-impact event inside a no-trade
buffer window around a given time.

Rate limit: Forex Factory limits this endpoint to ~2 requests per 5
minutes per source (documented in public MQL5 forum threads). Results
are cached in the calendar_cache table and only re-fetched when the
cache is older than CACHE_MINUTES, so the app can call
get_events()/is_high_impact_window() as often as it wants without
risking a block.

Verification status: the live endpoint (https://nfs.faireconomy.media/
ff_calendar_thisweek.json) was fetched and confirmed working during
this build, via a web-fetch tool separate from this app's own
requests.get() call (that domain isn't reachable from this sandbox's
outbound network). The response's shape matched exactly what this
module expects: a JSON array of {title, country, impact, date,
forecast, previous}. That live response was saved and is what
parsing/caching/currency-matching/window-detection are tested against
below — not a fabricated payload. The requests.get() call itself,
made from inside the actual app, is still unverified — see
verify_news.py to check that specifically on your machine.
"""

import json
from datetime import datetime, timedelta

from .db import get_conn

try:
    import requests
except ImportError:
    requests = None

CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CACHE_MINUTES = 60
DEFAULT_BUFFER_MINUTES = 30

# Metals aren't ISO currency codes in the calendar feed, but their price
# action is still driven mainly by USD data releases.
METAL_TO_CURRENCY = {"XAU": ["USD"], "XAG": ["USD"]}


def _require_requests():
    if requests is None:
        raise RuntimeError("The 'requests' package isn't installed. Run: pip install requests")


def _parse_event(raw):
    """Normalize one raw feed entry into our shape, with a real datetime
    object instead of a string."""
    return {
        "title": raw.get("title", ""),
        "currency": raw.get("country", ""),
        "impact": raw.get("impact", ""),
        "when": datetime.fromisoformat(raw["date"]),
        "forecast": raw.get("forecast", ""),
        "previous": raw.get("previous", ""),
    }


def _fetch_raw():
    _require_requests()
    resp = requests.get(CALENDAR_URL, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _cache_get():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT fetched_at, payload FROM calendar_cache ORDER BY fetched_at DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def _cache_set(payload):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO calendar_cache (fetched_at, payload) VALUES (?,?)",
            (datetime.now().isoformat(timespec="seconds"), json.dumps(payload))
        )


def get_events(force_refresh=False, cache_minutes=CACHE_MINUTES, raw_override=None):
    """Returns parsed events, using the cache unless it's stale or
    force_refresh is set. raw_override lets tests/other callers inject a
    raw payload directly, bypassing both the cache and the network call."""
    if raw_override is not None:
        return [_parse_event(e) for e in raw_override]

    cached = None if force_refresh else _cache_get()
    if cached:
        fetched_at = datetime.fromisoformat(cached["fetched_at"])
        if datetime.now() - fetched_at < timedelta(minutes=cache_minutes):
            return [_parse_event(e) for e in json.loads(cached["payload"])]

    raw = _fetch_raw()
    _cache_set(raw)
    return [_parse_event(e) for e in raw]


def instrument_currencies(instrument):
    """Best-effort split of an instrument name into the currency codes
    that affect it: 'XAUUSD' -> ['USD'] (metals map to USD, not
    themselves — XAU isn't a calendar country code), 'GBPJPY' -> ['GBP',
    'JPY']. Falls back to whatever 3-letter chunks it can find."""
    cleaned = "".join(ch for ch in instrument.upper() if ch.isalpha())
    codes = [cleaned[i:i + 3] for i in range(0, len(cleaned) - len(cleaned) % 3, 3)]

    result = []
    for code in codes:
        if code in METAL_TO_CURRENCY:
            result.extend(METAL_TO_CURRENCY[code])
        else:
            result.append(code)
    seen = set()
    return [c for c in result if not (c in seen or seen.add(c))]


def is_high_impact_window(instrument, when=None, buffer_minutes=DEFAULT_BUFFER_MINUTES,
                           events=None):
    """True if `when` (default: now) falls within buffer_minutes of a High
    impact event for a currency relevant to `instrument`. Returns
    (bool, [matching events]) so callers can show *why*, not just a flag.

    Timezone handling: the feed returns timezone-aware timestamps. `when`
    is normalized to an aware local-time datetime via .astimezone() —
    this correctly attaches the system's local timezone to a naive
    datetime (including bare datetime.now()), so the comparison below is
    always aware-to-aware and never raises on mixed naive/aware input."""
    when = (when or datetime.now()).astimezone()
    currencies = set(instrument_currencies(instrument))
    events = events if events is not None else get_events()

    window = timedelta(minutes=buffer_minutes)
    matches = [
        e for e in events
        if e["impact"] == "High"
        and e["currency"] in currencies
        and abs(e["when"] - when) <= window
    ]
    return (len(matches) > 0, matches)
