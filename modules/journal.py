"""
EdgeFlo app :: journal.py
Trade journal: log entries, close trades, compute realized R-multiples.
This is the ledger everything else (risk sizing, discipline scoring, AI
coaching, dashboard stats) is derived from.
"""

from datetime import datetime
from .db import get_conn


def log_trade(instrument, direction, entry_price, stop_price, size_units,
              account_balance_at_entry, target_price=None, setup_tag=None,
              emotion_before=None, notes=None, plan_id=None):
    """Log a new open trade. Risk % and planned R are derived from the
    prices entered, not typed in separately, so they can never silently
    drift from the actual numbers."""
    risk_per_unit = abs(entry_price - stop_price)
    if risk_per_unit == 0:
        raise ValueError("Entry and stop price cannot be equal")

    risk_dollars = risk_per_unit * size_units
    risk_pct = (risk_dollars / account_balance_at_entry) * 100 if account_balance_at_entry else 0

    planned_r = None
    if target_price is not None:
        reward_per_unit = abs(target_price - entry_price)
        planned_r = reward_per_unit / risk_per_unit

    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO trades (opened_at, instrument, direction, entry_price, stop_price,
                target_price, size_units, account_balance_at_entry, risk_pct,
                planned_r_multiple, setup_tag, emotion_before, notes, plan_id, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'open')
        """, (datetime.now().isoformat(timespec="seconds"), instrument, direction,
              entry_price, stop_price, target_price, size_units,
              account_balance_at_entry, risk_pct, planned_r, setup_tag,
              emotion_before, notes, plan_id))
        return cur.lastrowid


def close_trade(trade_id, exit_price, emotion_after=None, followed_plan=True, notes=None):
    """Close a trade and compute its realized R-multiple against the
    original stop distance (the plan) — not against whatever felt right
    in the moment. That gap is exactly what discipline.py tracks later."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
        if row is None:
            raise ValueError(f"No trade with id {trade_id}")
        if row["status"] == "closed":
            raise ValueError(f"Trade {trade_id} is already closed")

        risk_per_unit = abs(row["entry_price"] - row["stop_price"])
        if row["direction"] == "long":
            pnl_per_unit = exit_price - row["entry_price"]
        else:
            pnl_per_unit = row["entry_price"] - exit_price

        realized_r = pnl_per_unit / risk_per_unit if risk_per_unit else 0

        conn.execute("""
            UPDATE trades
            SET exit_price=?, closed_at=?, realized_r_multiple=?, emotion_after=?,
                followed_plan=?, notes=COALESCE(?, notes), status='closed'
            WHERE id=?
        """, (exit_price, datetime.now().isoformat(timespec="seconds"), realized_r,
              emotion_after, int(followed_plan), notes, trade_id))
        return realized_r


def list_trades(status=None, instrument=None):
    query = "SELECT * FROM trades WHERE 1=1"
    params = []
    if status:
        query += " AND status=?"
        params.append(status)
    if instrument:
        query += " AND instrument=?"
        params.append(instrument)
    query += " ORDER BY opened_at DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_trade(trade_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
        return dict(row) if row else None


def performance_summary(instrument=None):
    """Core stats derived purely from closed trades — no smoothing, no
    survivorship tricks. Matches the empirical framing already used in
    Justin's self-study work (walk-forward, no cherry-picking)."""
    trades = list_trades(status="closed", instrument=instrument)
    if not trades:
        return {"count": 0, "win_rate": None, "avg_r": None, "total_r": None,
                "plan_adherence_pct": None}

    r_values = [t["realized_r_multiple"] for t in trades if t["realized_r_multiple"] is not None]
    wins = [r for r in r_values if r > 0]
    followed = [t for t in trades if t["followed_plan"]]

    return {
        "count": len(trades),
        "win_rate": round(len(wins) / len(r_values) * 100, 1) if r_values else None,
        "avg_r": round(sum(r_values) / len(r_values), 2) if r_values else None,
        "total_r": round(sum(r_values), 2) if r_values else None,
        "plan_adherence_pct": round(len(followed) / len(trades) * 100, 1),
    }
