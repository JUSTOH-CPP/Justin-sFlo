"""
verify_broker.py
Run this ONCE on your machine (with MT5 open and logged in) to confirm
the live connection actually works before relying on broker.py in the app.
This is the one check I couldn't run myself — no MT5 terminal here.

Usage:
    python verify_broker.py

It only reads your last 30 days of closed trade history. It does not
place, modify, or close anything.
"""

from datetime import datetime, timedelta
from modules import broker

print("Connecting to MT5 terminal...")
broker.connect()
print("Connected OK.\n")

date_to = datetime.now()
date_from = date_to - timedelta(days=30)

print(f"Fetching closed positions from {date_from.date()} to {date_to.date()}...")
positions = broker.fetch_closed_positions(date_from, date_to)

print(f"\nFound {len(positions)} closed position(s).")
for p in positions[:5]:
    print(f"  #{p['mt5_ticket']}  {p['instrument']} {p['direction']:5s}  "
          f"entry {p['entry_price']}  exit {p['exit_price']}  "
          f"stop {p['stop_price']}  profit {p['profit']}")
if len(positions) > 5:
    print(f"  ... and {len(positions) - 5} more")

print("\nIf this looks right, broker.import_closed_trades() with the same")
print("date range will insert these into your journal (safe to re-run,")
print("duplicates are skipped automatically).")

broker.disconnect()
print("\nDisconnected.")
