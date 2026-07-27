"""
verify_news.py
Run this on your machine to confirm the app's OWN requests.get() call to
the Forex Factory calendar feed actually works from your network (mine
fetched it successfully via a different tool, but the app's real code
path — requests.get() from inside modules/news.py — was never run
against the live endpoint until now).

Usage:
    python verify_news.py
"""

from modules.db import init_db
from modules import news

init_db()  # ensures calendar_cache (and any other pending migration) exists
           # on this DB before we try to write to it

print("Fetching live economic calendar (force_refresh, bypassing cache)...")
events = news.get_events(force_refresh=True)
print(f"Got {len(events)} events for the week.\n")

high_impact = [e for e in events if e["impact"] == "High"]
print(f"{len(high_impact)} High-impact events this week:")
for e in high_impact[:10]:
    print(f"  {e['when']}  {e['currency']:4s} {e['title']}")
if len(high_impact) > 10:
    print(f"  ... and {len(high_impact) - 10} more")

print("\nChecking current no-trade windows for your pairs...")
for instrument in ["XAUUSD", "GBPUSD", "GBPJPY"]:
    blocked, matches = news.is_high_impact_window(instrument, events=events)
    status = "BLOCKED" if blocked else "clear"
    print(f"  {instrument}: {status}" + (f" ({matches[0]['title']})" if matches else ""))

print("\nIf the event list and currencies look right, the live feed is confirmed working.")
