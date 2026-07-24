"""
EdgeFlo app :: broker.py
Read-only MetaTrader5 integration. Pulls CLOSED trade history into the
journal automatically. Does NOT place orders, does NOT touch open
positions, and does NOT enforce guardrails live — see SPEC.md for why
execution and live blocking are explicitly out of scope.

Requires the MetaTrader5 package (Windows only, needs the MT5 terminal
installed and logged into your broker):
    pip install MetaTrader5

This module cannot be functionally tested outside a real MT5 terminal —
only compiled/imported. The data-transformation and dedup logic below
(fetch_closed_positions, import_closed_trades) IS tested here against a
mocked MT5 API; the live mt5.initialize()/history_deals_get() calls
themselves are not, and need verification on your machine. See
verify_broker.py for a standalone script to run that check.
"""

from datetime import datetime
from .db import get_conn

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

DEAL_ENTRY_IN = 0
DEAL_ENTRY_OUT = 1
DEAL_TYPE_BUY = 0


def _require_mt5():
    if mt5 is None:
        raise RuntimeError(
            "MetaTrader5 package not installed (or not on Windows). Run: pip install MetaTrader5"
        )


def connect(path=None, login=None, password=None, server=None):
    """Connect to the MT5 terminal already running and logged in on this
    machine. If login/password/server are omitted, MT5 uses whatever
    account is currently logged into the terminal — the simplest path
    when you're already connected, as you are."""
    _require_mt5()
    kwargs = {}
    if path:
        kwargs["path"] = path
    if login:
        kwargs["login"] = int(login)
    if password:
        kwargs["password"] = password
    if server:
        kwargs["server"] = server

    ok = mt5.initialize(**kwargs)
    if not ok:
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    return True


def disconnect():
    if mt5 is not None:
        mt5.shutdown()


def _deal_direction(deal_type):
    return "long" if deal_type == DEAL_TYPE_BUY else "short"


def _deal_to_dict(deal):
    """Normalize an MT5 deal (namedtuple-like) to a plain dict so the rest
    of this module — and its tests — don't depend on the MT5 package
    being importable."""
    if isinstance(deal, dict):
        return deal
    return deal._asdict()


def fetch_closed_positions(date_from, date_to, deals=None):
    """Returns one dict per closed position, reconstructed from matching
    IN/OUT deals that share the same position_id. Stop price is pulled
    from the original order's `sl` field when available; if that order
    had no stop set (fully discretionary management, or SL removed before
    close), stop_price is left None rather than guessed.

    `deals` is an optional pre-fetched list, used by tests to bypass the
    live mt5.history_deals_get() call. In normal use it's fetched here."""
    if deals is None:
        _require_mt5()
        raw = mt5.history_deals_get(date_from, date_to)
        deals = [_deal_to_dict(d) for d in (raw or [])]

    by_position = {}
    for d in deals:
        by_position.setdefault(d["position_id"], []).append(d)

    results = []
    for position_id, group in by_position.items():
        entries = [d for d in group if d["entry"] == DEAL_ENTRY_IN]
        exits = [d for d in group if d["entry"] == DEAL_ENTRY_OUT]
        if not entries or not exits:
            continue  # still open, or a partial fill pattern we won't guess at

        entry_deal = entries[0]
        exit_deal = exits[-1]

        stop_price = None
        if mt5 is not None:
            try:
                orders = mt5.history_orders_get(ticket=entry_deal["order"])
                if orders:
                    sl = _deal_to_dict(orders[0]).get("sl")
                    stop_price = sl if sl else None
            except Exception:
                pass
        else:
            stop_price = entry_deal.get("_test_stop_price")  # test-only hook

        results.append({
            "mt5_ticket": position_id,
            "instrument": entry_deal["symbol"],
            "direction": _deal_direction(entry_deal["type"]),
            "entry_price": entry_deal["price"],
            "exit_price": exit_deal["price"],
            "stop_price": stop_price,
            "size_units": entry_deal["volume"],
            "opened_at": datetime.fromtimestamp(entry_deal["time"]).isoformat(timespec="seconds"),
            "closed_at": datetime.fromtimestamp(exit_deal["time"]).isoformat(timespec="seconds"),
            "profit": sum(d["profit"] for d in group),
        })
    return results


def import_closed_trades(date_from, date_to, account_balance_at_entry, deals=None):
    """Insert newly-seen closed positions into the trades table, skipping
    any mt5_ticket already imported (enforced at the app level here, and
    backstopped by the unique index in db.py so a race can't double-insert
    either). Safe to call repeatedly — e.g. once a day, or on app start."""
    positions = fetch_closed_positions(date_from, date_to, deals=deals)
    inserted = []

    with get_conn() as conn:
        for p in positions:
            exists = conn.execute(
                "SELECT 1 FROM trades WHERE mt5_ticket=?", (p["mt5_ticket"],)
            ).fetchone()
            if exists:
                continue

            risk_per_unit = abs(p["entry_price"] - p["stop_price"]) if p["stop_price"] else None
            risk_pct = None
            realized_r = None
            if risk_per_unit:
                risk_dollars = risk_per_unit * p["size_units"]
                risk_pct = (risk_dollars / account_balance_at_entry * 100
                            if account_balance_at_entry else None)
                pnl_per_unit = ((p["exit_price"] - p["entry_price"]) if p["direction"] == "long"
                                else (p["entry_price"] - p["exit_price"]))
                realized_r = pnl_per_unit / risk_per_unit

            conn.execute("""
                INSERT INTO trades (opened_at, closed_at, instrument, direction, entry_price,
                    stop_price, exit_price, size_units, account_balance_at_entry, risk_pct,
                    realized_r_multiple, mt5_ticket, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'closed')
            """, (p["opened_at"], p["closed_at"], p["instrument"], p["direction"],
                  p["entry_price"], p["stop_price"], p["exit_price"], p["size_units"],
                  account_balance_at_entry, risk_pct, realized_r, p["mt5_ticket"]))
            inserted.append(p["mt5_ticket"])

    return inserted
