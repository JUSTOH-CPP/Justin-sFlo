"""
EdgeFlo app :: notebook.py
Freeform notes: strategy write-ups, session reviews, mindset templates.
Optionally linked to a specific trade (a note can stand alone, or be
attached to trade_id for a deeper post-mortem than the journal's
single notes field allows). Mirrors EdgeFlo's Notebook module.
"""

from datetime import datetime
from .db import get_conn

TEMPLATES = {
    "session_review": (
        "## What happened\n\n"
        "## What I did well\n\n"
        "## What I'd do differently\n\n"
        "## One thing to carry into tomorrow\n"
    ),
    "setup_writeup": (
        "## Setup name\n\n"
        "## Criteria\n\n"
        "## Invalidation\n\n"
        "## Management rules\n\n"
        "## Example trades\n"
    ),
    "mindset_check": (
        "## How I'm feeling before this session\n\n"
        "## What could derail me today\n\n"
        "## My plan if it happens\n"
    ),
}


def create_note(title, body="", category=None, trade_id=None):
    if not title or not title.strip():
        raise ValueError("Note title is required")

    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO notes (title, body, category, trade_id, created_at, updated_at)
            VALUES (?,?,?,?,?,?)
        """, (title.strip(), body, category, trade_id, now, now))
        return cur.lastrowid


def create_from_template(template_name, title, trade_id=None):
    """Create a note pre-filled with one of the built-in templates. Raises
    if the template name doesn't exist, rather than silently falling back
    to a blank note."""
    if template_name not in TEMPLATES:
        raise ValueError(f"Unknown template '{template_name}'. Available: {list(TEMPLATES)}")
    return create_note(title, body=TEMPLATES[template_name],
                        category=template_name, trade_id=trade_id)


def update_note(note_id, title=None, body=None, category=None):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        if row is None:
            raise ValueError(f"No note with id {note_id}")

        new_title = title if title is not None else row["title"]
        new_body = body if body is not None else row["body"]
        new_category = category if category is not None else row["category"]

        conn.execute("""
            UPDATE notes SET title=?, body=?, category=?, updated_at=?
            WHERE id=?
        """, (new_title, new_body, new_category,
              datetime.now().isoformat(timespec="seconds"), note_id))


def delete_note(note_id):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
        if cur.rowcount == 0:
            raise ValueError(f"No note with id {note_id}")


def get_note(note_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        return dict(row) if row else None


def list_notes(category=None, trade_id=None):
    query = "SELECT * FROM notes WHERE 1=1"
    params = []
    if category:
        query += " AND category=?"
        params.append(category)
    if trade_id is not None:
        query += " AND trade_id=?"
        params.append(trade_id)
    query += " ORDER BY updated_at DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]
