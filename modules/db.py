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
    stop_price REAL NOT NULL,
    target_price REAL,
    exit_price REAL,
    size_units REAL NOT NULL,
    account_balance_at_entry REAL NOT NULL,
    risk_pct REAL NOT NULL,
    planned_r_multiple REAL,
    realized_r_multiple REAL,
    setup_tag TEXT,
    followed_plan INTEGER DEFAULT 1,
    emotion_before TEXT,
    emotion_after TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed'))
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
"""


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)


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
