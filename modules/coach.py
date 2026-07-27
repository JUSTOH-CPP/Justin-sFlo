"""
EdgeFlo app :: coach.py
AI coaching layer. Sends a closed trade + its discipline flags to Claude
for a short, structured review (strengths / leaks / one action item) and
stores the result alongside the trade. Requires an ANTHROPIC_API_KEY
environment variable — this module never hardcodes a key, and never logs
it either.

Model: claude-sonnet-5 (current as of this build — see
docs.claude.com/en/docs/about-claude/models/overview if this needs
updating later).
"""

import os
import json
from datetime import datetime
from .db import get_conn

try:
    import anthropic
except ImportError:
    anthropic = None

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You are a disciplined trading coach reviewing ONE closed trade
from a systematic SMC + quantitative trader's journal. Be concise and concrete.
Never give financial advice or predict future price action — only review the
process that already happened: entry logic, risk sizing, plan adherence, and
emotional state. Respond ONLY as JSON with keys: summary (1-2 sentences),
strengths (short string), leaks (short string, process weaknesses only),
action_item (one concrete, testable habit change for the next trade). No text
before or after the JSON object."""

WEEKLY_SYSTEM_PROMPT = SYSTEM_PROMPT.replace(
    "ONE closed trade", "a BATCH of closed trades"
).replace(
    "for the next trade", "for the coming week"
)


def _client():
    if anthropic is None:
        raise RuntimeError("The 'anthropic' package isn't installed. Run: pip install anthropic")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Set the ANTHROPIC_API_KEY environment variable before using the AI coach.")
    return anthropic.Anthropic(api_key=api_key)


def _extract_text(response):
    return "".join(block.text for block in response.content if block.type == "text")


def _parse_review_json(raw_text):
    """Parse the model's JSON reply defensively. Claude is instructed to
    return JSON only, but this still guards against stray text (e.g. a
    markdown code fence) rather than crashing the whole review."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"summary": raw_text, "strengths": "", "leaks": "", "action_item": ""}

    return {
        "summary": parsed.get("summary", ""),
        "strengths": parsed.get("strengths", ""),
        "leaks": parsed.get("leaks", ""),
        "action_item": parsed.get("action_item", ""),
    }


def review_trade(trade, discipline_flags=None, client=None):
    """trade: dict from journal.list_trades()/get_trade(). discipline_flags:
    list of event_type strings from discipline.py for this trade. `client`
    is injectable for tests to bypass the real API call."""
    if client is None:
        client = _client()

    user_content = f"""Trade record:
{json.dumps(trade, indent=2, default=str)}

Discipline flags raised for this trade: {discipline_flags or 'none'}
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    parsed = _parse_review_json(_extract_text(response))

    with get_conn() as conn:
        conn.execute("""
            INSERT INTO coach_notes (trade_id, created_at, summary, strengths, leaks, action_item)
            VALUES (?,?,?,?,?,?)
        """, (trade["id"], datetime.now().isoformat(timespec="seconds"),
              parsed["summary"], parsed["strengths"], parsed["leaks"], parsed["action_item"]))

    return parsed


def weekly_digest(trades, client=None):
    """Rollup review across several closed trades — same JSON contract,
    summarizing patterns across the batch. Called manually, not scheduled.
    Does not write to coach_notes (that table is per-trade) — the caller
    decides what to do with the digest, e.g. save it as a notebook entry."""
    if client is None:
        client = _client()

    user_content = f"Closed trades this period:\n{json.dumps(trades, indent=2, default=str)}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=WEEKLY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    return _parse_review_json(_extract_text(response))


def get_coach_notes(trade_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM coach_notes WHERE trade_id=? ORDER BY created_at DESC", (trade_id,)
        ).fetchall()
        return [dict(r) for r in rows]
