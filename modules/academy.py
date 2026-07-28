"""
EdgeFlo app :: academy.py
Personal lesson/checklist tracker — your own study material, not
EdgeFlo's proprietary course content. Same shape as their Academy module
(ordered lessons, mark-complete progress) applied to whatever you drop
in: notes from your own SMC/quant research, links, checklists.
"""

from datetime import datetime
from .db import get_conn


def create_lesson(title, content="", category=None, order_index=None, source=None):
    if not title or not title.strip():
        raise ValueError("Lesson title is required")

    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO lessons (title, content, category, order_index, source, created_at)
            VALUES (?,?,?,?,?,?)
        """, (title.strip(), content, category, order_index, source,
              datetime.now().isoformat(timespec="seconds")))
        return cur.lastrowid


def get_lesson(lesson_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM lessons WHERE id=?", (lesson_id,)).fetchone()
        return dict(row) if row else None


def list_lessons(category=None, completed=None):
    """completed=None -> all, True -> only completed, False -> only
    incomplete. Ordered by order_index (nulls last), then created_at, so
    a defined curriculum sequence is respected when set, and creation
    order is the sensible fallback when it isn't."""
    query = "SELECT * FROM lessons WHERE 1=1"
    params = []
    if category:
        query += " AND category=?"
        params.append(category)
    if completed is True:
        query += " AND completed_at IS NOT NULL"
    elif completed is False:
        query += " AND completed_at IS NULL"
    query += " ORDER BY (order_index IS NULL), order_index, created_at"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def mark_complete(lesson_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM lessons WHERE id=?", (lesson_id,)).fetchone()
        if row is None:
            raise ValueError(f"No lesson with id {lesson_id}")
        conn.execute("UPDATE lessons SET completed_at=? WHERE id=?",
                     (datetime.now().isoformat(timespec="seconds"), lesson_id))


def mark_incomplete(lesson_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM lessons WHERE id=?", (lesson_id,)).fetchone()
        if row is None:
            raise ValueError(f"No lesson with id {lesson_id}")
        conn.execute("UPDATE lessons SET completed_at=NULL WHERE id=?", (lesson_id,))


def delete_lesson(lesson_id):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM lessons WHERE id=?", (lesson_id,))
        if cur.rowcount == 0:
            raise ValueError(f"No lesson with id {lesson_id}")


def progress_summary(category=None):
    lessons = list_lessons(category=category)
    if not lessons:
        return {"total": 0, "completed": 0, "pct": None}
    completed = sum(1 for l in lessons if l["completed_at"] is not None)
    return {
        "total": len(lessons),
        "completed": completed,
        "pct": round(completed / len(lessons) * 100, 1),
    }
