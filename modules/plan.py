"""
Justin's-Flo app :: plan.py
Trade plan management: define setups/criteria/invalidation/management
rules, pin exactly one plan as Active, and track compliance against it.
Mirrors EdgeFlo's "Plan" module — the plan is meant to be visible during
execution so you stop improvising, and its stats show whether you
actually traded it or not.
"""

from datetime import datetime
from .db import get_conn


def create_plan(name, criteria=None, invalidation=None, management_rules=None):
    if not name or not name.strip():
        raise ValueError("Plan name cannot be empty")
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO plans (name, criteria, invalidation, management_rules, is_active, created_at)
            VALUES (?,?,?,?,0,?)
        """, (name.strip(), criteria, invalidation, management_rules,
              datetime.now().isoformat(timespec="seconds")))
        return cur.lastrowid


def set_active_plan(plan_id):
    """Exactly one plan can be Active at a time — setting one deactivates
    all others, same as EdgeFlo's single pinned plan."""
    with get_conn() as conn:
        exists = conn.execute("SELECT id FROM plans WHERE id=?", (plan_id,)).fetchone()
        if exists is None:
            raise ValueError(f"No plan with id {plan_id}")
        conn.execute("UPDATE plans SET is_active=0")
        conn.execute("UPDATE plans SET is_active=1 WHERE id=?", (plan_id,))


def clear_active_plan():
    """No plan pinned — trades logged now won't be linked to one."""
    with get_conn() as conn:
        conn.execute("UPDATE plans SET is_active=0")


def get_active_plan():
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM plans WHERE is_active=1").fetchone()
        return dict(row) if row else None


def list_plans():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM plans ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_plan(plan_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
        return dict(row) if row else None


def plan_compliance(plan_id):
    """Stats for trades logged against a specific plan: how many, win
    rate, avg R, and — the actual compliance number — what fraction were
    marked as having followed the plan on close. Only trades logged with
    this plan_id count; trades logged with no plan pinned are excluded,
    since there's nothing to be compliant with."""
    plan = get_plan(plan_id)
    if plan is None:
        raise ValueError(f"No plan with id {plan_id}")

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM trades WHERE plan_id=? AND status='closed'
        """, (plan_id,)).fetchall()
    trades = [dict(r) for r in rows]

    if not trades:
        return {"plan_id": plan_id, "plan_name": plan["name"], "count": 0,
                "win_rate": None, "avg_r": None, "compliance_pct": None}

    r_values = [t["realized_r_multiple"] for t in trades if t["realized_r_multiple"] is not None]
    wins = [r for r in r_values if r > 0]
    followed = [t for t in trades if t["followed_plan"]]

    return {
        "plan_id": plan_id,
        "plan_name": plan["name"],
        "count": len(trades),
        "win_rate": round(len(wins) / len(r_values) * 100, 1) if r_values else None,
        "avg_r": round(sum(r_values) / len(r_values), 2) if r_values else None,
        "compliance_pct": round(len(followed) / len(trades) * 100, 1),
    }
