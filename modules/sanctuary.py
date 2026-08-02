"""
Justin's-Flo app :: sanctuary.py
A structured pause after a flagged revenge-entry pattern — same idea as
EdgeFlo's Sanctuary module. Deliberately simple: this module tracks
*that* a reset was triggered and completed, and provides the routine
text; any breathing-timer countdown UI belongs in app.py, not here.

Not a substitute for professional support — this is a trading-discipline
circuit breaker (a structured pause before the next click), nothing more.
"""

from datetime import datetime
from .db import get_conn
from .discipline import list_events

RESET_ROUTINE = [
    {"step": "Stop", "prompt": "Step away from the platform for 60 seconds before anything else."},
    {"step": "Breathe", "prompt": "4 seconds in, hold 4, out for 6. Repeat 5 times."},
    {"step": "Name it", "prompt": "What just happened, in one plain sentence — no justification."},
    {"step": "Check the plan", "prompt": "Does the next trade you want to take match your Active plan, "
                                          "or is it a reaction to the last one?"},
    {"step": "Decide", "prompt": "Take the next setup only if it independently meets your criteria. "
                                  "If you're not sure, that's your answer."},
]


def needs_reset(trade_id):
    """True if this trade has a revenge_entry flag logged against it —
    the one discipline event type sanctuary responds to."""
    events = list_events(trade_id)
    return any(e["event_type"] == "revenge_entry" for e in events)


def trigger_reset(trade_id, reason="revenge_entry"):
    """Open a reset event. Returns its id. Safe to call more than once
    for the same trade — each call opens a new record rather than
    silently merging, so a repeated pattern is still visible in history."""
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO reset_events (trigger_trade_id, trigger_reason, triggered_at)
            VALUES (?,?,?)
        """, (trade_id, reason, datetime.now().isoformat(timespec="seconds")))
        return cur.lastrowid


def complete_reset(reset_id, action_taken=None):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM reset_events WHERE id=?", (reset_id,)).fetchone()
        if row is None:
            raise ValueError(f"No reset event with id {reset_id}")
        if row["completed_at"] is not None:
            raise ValueError(f"Reset event {reset_id} is already completed")

        conn.execute("""
            UPDATE reset_events SET completed_at=?, action_taken=? WHERE id=?
        """, (datetime.now().isoformat(timespec="seconds"), action_taken, reset_id))


def get_pending_reset():
    """The most recent reset event that hasn't been completed yet, or
    None. The app should treat a pending reset as something to surface
    prominently, not something to quietly skip past."""
    with get_conn() as conn:
        row = conn.execute("""
            SELECT * FROM reset_events WHERE completed_at IS NULL
            ORDER BY triggered_at DESC LIMIT 1
        """).fetchone()
        return dict(row) if row else None


def list_resets(trade_id=None):
    query = "SELECT * FROM reset_events WHERE 1=1"
    params = []
    if trade_id is not None:
        query += " AND trigger_trade_id=?"
        params.append(trade_id)
    query += " ORDER BY triggered_at DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]
