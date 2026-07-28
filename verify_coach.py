"""
verify_coach.py
Run this once you have ANTHROPIC_API_KEY set, to confirm the live API
call actually works. Uses a small made-up trade so it doesn't require
you to have a real closed trade in the journal yet.

Usage (after `set ANTHROPIC_API_KEY=sk-ant-...`):
    python verify_coach.py
"""

from modules.db import init_db
from modules import coach

init_db()

sample_trade = {
    "id": None,
    "instrument": "XAUUSD",
    "direction": "long",
    "entry_price": 2000.0,
    "stop_price": 1995.0,
    "exit_price": 2015.0,
    "realized_r_multiple": 3.0,
    "setup_tag": "OB reclaim",
    "followed_plan": 1,
    "emotion_before": "calm",
    "emotion_after": "satisfied",
}

print("Sending a sample trade to Claude for review...")
review = coach.review_trade(sample_trade, discipline_flags=[])

print("\nReview received:")
print("  Summary:    ", review["summary"])
print("  Strengths:  ", review["strengths"])
print("  Leaks:      ", review["leaks"])
print("  Action item:", review["action_item"])

print("\nIf this looks like a real, sensible review (not an error or garbled")
print("text), the live coach is confirmed working.")
