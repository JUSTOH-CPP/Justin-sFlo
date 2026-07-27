"""
EdgeFlo app :: db.py
SQLite persistence layer — one local file DB, no server. All modules
(journal, risk, discipline, coach) read/write through this file so the
app has a single source of truth.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "edgeflo.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('long','short')),
    entry_price REAL NOT NULL,
    stop_price REAL,
    target_price REAL,
    exit_price REAL,
    size_units REAL NOT NULL,
    account_balance_at_entry REAL NOT NULL,
    risk_pct REAL,
    planned_r_multiple REAL,
    realized_r_multiple REAL,
    setup_tag TEXT,
    followed_plan INTEGER DEFAULT 1,
    emotion_before TEXT,
    emotion_after TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed'))
);

CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    criteria TEXT,
    invalidation TEXT,
    management_rules TEXT,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discipline_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER REFERENCES trades(id),
    event_type TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS coach_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER REFERENCES trades(id),
    created_at TEXT NOT NULL,
    summary TEXT,
    strengths TEXT,
    leaks TEXT,
    action_item TEXT
);

CREATE TABLE IF NOT EXISTS calendar_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT,
    category TEXT,
    trade_id INTEGER REFERENCES trades(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reset_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_trade_id INTEGER REFERENCES trades(id),
    trigger_reason TEXT NOT NULL,
    triggered_at TEXT NOT NULL,
    completed_at TEXT,
    action_taken TEXT
);

CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT,
    category TEXT,
    order_index INTEGER,
    source TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
"""


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
    _migrate()


def _migrate():
    """Lightweight schema migrations for DBs created before a given
    column/table existed. CREATE TABLE IF NOT EXISTS in SCHEMA handles new
    tables automatically; this handles new COLUMNS on existing tables,
    and the one constraint change SQLite can't do with ALTER TABLE, which
    SQLite has no IF NOT EXISTS shorthand for."""
    with get_conn() as conn:
        cols_info = {row["name"]: row for row in conn.execute("PRAGMA table_info(trades)")}

        if "plan_id" not in cols_info:
            conn.execute("ALTER TABLE trades ADD COLUMN plan_id INTEGER REFERENCES plans(id)")
            cols_info = {row["name"]: row for row in conn.execute("PRAGMA table_info(trades)")}

        if "mt5_ticket" not in cols_info:
            conn.execute("ALTER TABLE trades ADD COLUMN mt5_ticket INTEGER")

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_mt5_ticket
            ON trades(mt5_ticket) WHERE mt5_ticket IS NOT NULL
        """)

        # stop_price/risk_pct used to be NOT NULL. Broker-imported trades
        # (broker.py) sometimes genuinely don't have a known stop, so this
        # constraint needs relaxing. SQLite can't drop NOT NULL with ALTER
        # TABLE, so rebuild the table when an old-schema DB is detected.
        if cols_info.get("stop_price") and cols_info["stop_price"]["notnull"] == 1:
            _rebuild_trades_nullable_stop(conn)


def _rebuild_trades_nullable_stop(conn):
    conn.executescript("""
        CREATE TABLE trades_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opened_at TEXT NOT NULL,
            closed_at TEXT,
            instrument TEXT NOT NULL,
            direction TEXT NOT NULL CHECK(direction IN ('long','short')),
            entry_price REAL NOT NULL,
            stop_price REAL,
            target_price REAL,
            exit_price REAL,
            size_units REAL NOT NULL,
            account_balance_at_entry REAL NOT NULL,
            risk_pct REAL,
            planned_r_multiple REAL,
            realized_r_multiple REAL,
            setup_tag TEXT,
            followed_plan INTEGER DEFAULT 1,
            emotion_before TEXT,
            emotion_after TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),
            plan_id INTEGER REFERENCES plans(id),
            mt5_ticket INTEGER
        );
        INSERT INTO trades_new SELECT id, opened_at, closed_at, instrument, direction,
            entry_price, stop_price, target_price, exit_price, size_units,
            account_balance_at_entry, risk_pct, planned_r_multiple, realized_r_multiple,
            setup_tag, followed_plan, emotion_before, emotion_after, notes, status,
            plan_id, mt5_ticket
        FROM trades;
        DROP TABLE trades;
        ALTER TABLE trades_new RENAME TO trades;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_mt5_ticket
            ON trades(mt5_ticket) WHERE mt5_ticket IS NOT NULL;
    """)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
