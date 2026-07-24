"""
EdgeFlo app :: discipline.py
Rule-based discipline scoring — no ML, no black box. Flags concrete,
auditable behaviors (oversized risk, plan deviation, revenge entries)
so the score is always explainable from the trades table. This is what
EdgeFlo calls "Guardrails"; here it's detection after the fact rather
than live blocking, since broker.py (step 6) is read-only import only —
see SPEC.md for why live blocking is out of scope for now.
"""

from datetime import datetime, timedelta
from .db import get_conn
from .journal import list_trades

DEFAULT_MAX_RISK_PCT = 1.5           # flag any trade risking more than this
DEFAULT_REVENGE_WINDOW_MINUTES = 30  # a new trade this soon after a loss is flagged

PENALTIES = {"oversized": 5, "plan_deviation": 4, "revenge_entry": 8}
DEFAULT_PENALTY = 2


def log_event(trade_id, event_type, detail=""):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO discipline_events (trade_id, event_type, detail, created_at)
            VALUES (?,?,?,?)
        """, (trade_id, event_type, detail, datetime.now().isoformat(timespec="seconds")))


def list_events(trade_id=None):
    query = "SELECT * FROM discipline_events"
    params = []
    if trade_id is not None:
        query += " WHERE trade_id=?"
        params.append(trade_id)
    query += " ORDER BY created_at DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def _already_flagged(conn, trade_id, event_type):
    row = conn.execute(
        "SELECT 1 FROM discipline_events WHERE trade_id=? AND event_type=?",
        (trade_id, event_type)
    ).fetchone()
    return row is not None


def scan_trades_for_violations(max_risk_pct=DEFAULT_MAX_RISK_PCT,
                                revenge_window_minutes=DEFAULT_REVENGE_WINDOW_MINUTES):
    """Walk the full journal and flag oversized risk, plan deviation, and
    revenge-entry patterns. Idempotent — safe to call after every log/close,
    since each check skips a (trade_id, event_type) pair that's already
    been flagged rather than duplicating it."""
    trades = sorted(list_trades(), key=lambda t: t["opened_at"])
    flagged = []

    with get_conn() as conn:
        for i, t in enumerate(trades):
            if t["risk_pct"] and t["risk_pct"] > max_risk_pct \
                    and not _already_flagged(conn, t["id"], "oversized"):
                log_event(t["id"], "oversized",
                          f"Risked {t['risk_pct']:.2f}% (limit {max_risk_pct}%)")
                flagged.append((t["id"], "oversized"))

            if t["status"] == "closed" and not t["followed_plan"] \
                    and not _already_flagged(conn, t["id"], "plan_deviation"):
                log_event(t["id"], "plan_deviation", "Marked as not following plan on close")
                flagged.append((t["id"], "plan_deviation"))

            if i > 0:
                prev = trades[i - 1]
                if prev["status"] == "closed" and prev["realized_r_multiple"] is not None \
                        and prev["realized_r_multiple"] < 0 \
                        and not _already_flagged(conn, t["id"], "revenge_entry"):
                    try:
                        prev_close = datetime.fromisoformat(prev["closed_at"])
                        this_open = datetime.fromisoformat(t["opened_at"])
                        gap = this_open - prev_close
                        if timedelta(0) <= gap < timedelta(minutes=revenge_window_minutes):
                            log_event(t["id"], "revenge_entry",
                                      f"Opened {int(gap.total_seconds() / 60)} min after a losing trade")
                            flagged.append((t["id"], "revenge_entry"))
                    except (TypeError, ValueError):
                        pass

    return flagged


def discipline_score():
    """0-100 score: starts at 100, deducts fixed points per flagged event,
    floored at 0. Simple and transparent on purpose — the breakdown always
    shows exactly why the number moved."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT event_type, COUNT(*) as n FROM discipline_events GROUP BY event_type"
        ).fetchall()

    score = 100
    breakdown = {}
    for r in rows:
        deduction = PENALTIES.get(r["event_type"], DEFAULT_PENALTY) * r["n"]
        score -= deduction
        breakdown[r["event_type"]] = {"count": r["n"], "points_lost": deduction}

    return {"score": max(0, score), "breakdown": breakdown}
