"""
Justin's-Flo app :: app.py
Entry point. Run with:
    streamlit run app.py

Ties together all 11 modules built in steps 1-11. Sidebar navigation
groups related modules into sections instead of one flat 10-tab strip;
a floating Quick Log button (bottom-right) is reachable from every
section for the one action used constantly.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from modules.db import init_db
from modules import journal, risk, plan, discipline, broker, news, notebook, sanctuary, coach, academy

st.set_page_config(page_title="Justin's-Flo", layout="wide")
init_db()

# ----------------------------------------------------------------- Styling
# Palette is grounded in the app itself, not a generic dark theme: gold
# because XAU/USD is one of the three pairs this journal tracks, teal/coral
# as functional win-loss signal colors (not decoration), Plex Mono for
# every number so data reads distinctly from labels — a real distinction
# for a quant-facing tool, not just "monospace because trading app."
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }

[data-testid="stMetricValue"], [data-testid="stMetricDelta"],
.stDataFrame, .stNumberInput input {
    font-family: 'IBM Plex Mono', monospace !important;
}

h1:first-of-type {
    border-bottom: 2px solid #C9A227;
    padding-bottom: 0.4rem;
}

[data-testid="stMetric"] {
    background-color: #1B212B;
    border: 1px solid #2A3240;
    border-radius: 8px;
    padding: 0.9rem 1rem;
}

div[data-testid="stAlertContainer"] {
    border-left: 3px solid #C9A227;
    border-radius: 4px;
}

.stTabs [aria-selected="true"] {
    color: #C9A227 !important;
    border-bottom-color: #C9A227 !important;
}

/* Sidebar nav: section groups read as a real menu, not a generic radio
   list — bigger tap targets, gold highlight on the active section */
section[data-testid="stSidebar"] .stRadio label {
    font-size: 1.02rem;
    padding: 0.35rem 0;
}
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {
    color: #C9A227;
    letter-spacing: 0.02em;
}

/* Floating Quick Log button: pinned to the viewport, not the page flow,
   so it's reachable from any section without scrolling back up. Targets
   the container by its Streamlit-assigned key class. */
.st-key-quick_log_fab {
    position: fixed;
    bottom: 1.75rem;
    right: 1.75rem;
    z-index: 9999;
}
.st-key-quick_log_fab button {
    border-radius: 999px !important;
    background-color: #C9A227 !important;
    color: #12161C !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 14px rgba(0,0,0,0.45) !important;
    border: none !important;
    padding: 0.7rem 1.4rem !important;
}
.st-key-quick_log_fab button:hover {
    background-color: #E0BC3D !important;
}
</style>
""", unsafe_allow_html=True)

st.title("Justin's-Flo")
st.caption("Discipline-first trading superapp — local, no subscription, your data stays on this machine.")

# A pending reset (from a flagged revenge-entry) takes priority over
# everything else in the UI — surfaced right under the title regardless
# of which section is selected, not buried in a tab nobody's looking at
# in the moment it matters.
pending_reset = sanctuary.get_pending_reset()
if pending_reset:
    with st.container(border=True):
        st.warning(f"**Reset pending** — triggered by trade #{pending_reset['trigger_trade_id']} "
                   f"({pending_reset['trigger_reason']}) at {pending_reset['triggered_at']}")
        for step in sanctuary.RESET_ROUTINE:
            st.markdown(f"**{step['step']}** — {step['prompt']}")
        action_note = st.text_input("What did you actually do?", key="reset_action")
        if st.button("Mark reset complete"):
            sanctuary.complete_reset(pending_reset["id"], action_taken=action_note or None)
            st.rerun()


# ============================================================= Section bodies
# Each section is a plain function so sidebar nav can dispatch to exactly
# one at a time, instead of Streamlit rendering (and running the DB calls
# for) all ten every single run the way a flat tabs=[...] strip does.

def render_dashboard():
    stats = journal.performance_summary()
    disc = discipline.discipline_score()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Closed Trades", stats["count"])
    c2.metric("Win Rate", f"{stats['win_rate']}%" if stats["win_rate"] is not None else "—")
    c3.metric("Avg R", stats["avg_r"] if stats["avg_r"] is not None else "—")
    c4.metric("Total R", stats["total_r"] if stats["total_r"] is not None else "—")
    c5.metric("Discipline Score", f"{disc['score']}/100")

    active_plan = plan.get_active_plan()
    st.subheader("Active Plan")
    if active_plan:
        st.write(f"**{active_plan['name']}**")
        compliance = plan.plan_compliance(active_plan["id"])
        if compliance["count"] > 0:
            st.write(f"Compliance: {compliance['compliance_pct']}% over {compliance['count']} trades "
                     f"(win rate {compliance['win_rate']}%, avg R {compliance['avg_r']})")
    else:
        st.info("No active plan set — see Trading \u2192 Plan.")

    open_trades = journal.list_trades(status="open")
    st.subheader("Open Positions")
    if open_trades:
        st.dataframe(pd.DataFrame(open_trades), width="stretch")
    else:
        st.info("No open trades.")

    if disc["breakdown"]:
        st.subheader("Discipline Flags (all time)")
        st.dataframe(pd.DataFrame(disc["breakdown"]).T, width="stretch")


def render_trade_log():
    st.subheader("Log a New Trade")
    active_plan = plan.get_active_plan()
    if active_plan:
        st.caption(f"Active plan: **{active_plan['name']}** — this trade will be linked to it.")

    with st.form("log_trade_form"):
        col1, col2 = st.columns(2)
        with col1:
            instrument = st.selectbox("Instrument", ["XAUUSD", "GBPUSD", "GBPJPY", "Other"])
            direction = st.selectbox("Direction", ["long", "short"])
            entry_price = st.number_input("Entry Price", format="%.5f")
            stop_price = st.number_input("Stop Price", format="%.5f")
            target_price = st.number_input("Target Price (optional, 0 = none)", format="%.5f", value=0.0)
        with col2:
            size_units = st.number_input("Size (units)", format="%.4f", min_value=0.0001)
            account_balance = st.number_input("Account Balance at Entry", value=10000.0)
            setup_tag = st.text_input("Setup Tag (e.g. 'order block reclaim')")
            emotion_before = st.selectbox("Emotion Before Entry",
                                           ["calm", "confident", "anxious", "impatient", "frustrated", "other"])
        trade_notes = st.text_area("Notes")

        submitted = st.form_submit_button("Log Trade")
        if submitted:
            try:
                blocked, matches = news.is_high_impact_window(instrument)
                if blocked:
                    st.warning(f"High-impact news window: {matches[0]['title']} at {matches[0]['when']} — "
                               f"logging anyway, this is a flag not a block.")
            except Exception:
                st.info("Couldn't check the news calendar (feed unavailable) — logging the trade anyway.")
            trade_id = journal.log_trade(
                instrument=instrument, direction=direction, entry_price=entry_price,
                stop_price=stop_price, size_units=size_units,
                account_balance_at_entry=account_balance,
                target_price=(target_price or None), setup_tag=setup_tag or None,
                emotion_before=emotion_before, notes=trade_notes or None,
                plan_id=(active_plan["id"] if active_plan else None),
            )
            discipline.scan_trades_for_violations()
            st.success(f"Trade #{trade_id} logged.")

    st.divider()
    st.subheader("Close an Open Trade")
    open_trades = journal.list_trades(status="open")
    if open_trades:
        options = {f"#{t['id']} {t['instrument']} {t['direction']} @ {t['entry_price']}": t["id"]
                   for t in open_trades}
        choice = st.selectbox("Select trade", list(options.keys()))
        exit_price = st.number_input("Exit Price", format="%.5f", key="exit_price")
        emotion_after = st.selectbox("Emotion After Exit",
                                      ["satisfied", "relieved", "frustrated", "regretful", "neutral", "other"])
        followed_plan_input = st.checkbox("Followed the original plan?", value=True)
        close_notes = st.text_area("Close Notes", key="close_notes")
        if st.button("Close Trade"):
            selected_id = options[choice]
            realized_r = journal.close_trade(selected_id, exit_price,
                                              emotion_after=emotion_after,
                                              followed_plan=followed_plan_input, notes=close_notes or None)
            discipline.scan_trades_for_violations()
            if sanctuary.needs_reset(selected_id):
                sanctuary.trigger_reset(selected_id)
                st.warning("Revenge-entry pattern detected — a reset has been triggered. See the banner above.")
            st.success(f"Closed. Realized R-multiple: {realized_r:.2f}")
            st.rerun()
    else:
        st.info("No open trades to close.")

    st.divider()
    st.subheader("Position Sizer")
    method = st.radio("Method", ["Fixed-fractional", "Kelly (from journal stats)"])
    sizer_balance = st.number_input("Account Balance", value=10000.0, key="sizer_balance")
    sizer_entry = st.number_input("Entry Price", format="%.5f", key="sizer_entry")
    sizer_stop = st.number_input("Stop Price", format="%.5f", key="sizer_stop")

    if method == "Fixed-fractional":
        risk_pct = st.slider("Risk % per trade", 0.1, 5.0, 1.0, 0.1)
        if st.button("Calculate Size"):
            try:
                result = risk.fixed_fractional_size(sizer_balance, risk_pct, sizer_entry, sizer_stop)
                st.metric("Position Size (units)", result.size_units)
                st.caption(result.notes)
            except ValueError as e:
                st.error(str(e))
    else:
        fraction = st.slider("Fraction of Kelly to use", 0.1, 1.0, 0.5, 0.1)
        if st.button("Calculate Size"):
            try:
                result = risk.kelly_size(sizer_balance, sizer_entry, sizer_stop, fraction_of_kelly=fraction)
                st.metric("Position Size (units)", result.size_units)
                st.caption(result.notes)
            except ValueError as e:
                st.error(str(e))

    st.divider()
    st.subheader("Full Journal")
    status_filter = st.selectbox("Filter by status", ["all", "open", "closed"], key="journal_status_filter")
    trades = journal.list_trades(status=None if status_filter == "all" else status_filter)
    if trades:
        st.dataframe(pd.DataFrame(trades), width="stretch")
    else:
        st.info("No trades logged yet.")


def render_plan():
    st.subheader("Active Plan")
    active_plan = plan.get_active_plan()
    if active_plan:
        st.write(f"**{active_plan['name']}**")
        st.write("**Criteria:**", active_plan["criteria"] or "—")
        st.write("**Invalidation:**", active_plan["invalidation"] or "—")
        st.write("**Management rules:**", active_plan["management_rules"] or "—")
        if st.button("Clear active plan"):
            plan.clear_active_plan()
            st.rerun()

        compliance = plan.plan_compliance(active_plan["id"])
        if compliance["count"] > 0:
            st.metric("Compliance", f"{compliance['compliance_pct']}%")
            st.write(f"{compliance['count']} trades, win rate {compliance['win_rate']}%, "
                     f"avg R {compliance['avg_r']}, total R {compliance['total_r']}")
    else:
        st.info("No plan is currently active.")

    st.divider()
    st.subheader("All Plans")
    all_plans = plan.list_plans()
    if all_plans:
        for p in all_plans:
            with st.container(border=True):
                st.write(f"**{p['name']}**" + (" (active)" if p["is_active"] else ""))
                if not p["is_active"]:
                    if st.button("Set active", key=f"activate_{p['id']}"):
                        plan.set_active_plan(p["id"])
                        st.rerun()

    st.divider()
    st.subheader("Create a New Plan")
    with st.form("create_plan_form"):
        plan_name = st.text_input("Plan name")
        plan_criteria = st.text_area("Criteria")
        plan_invalidation = st.text_area("Invalidation")
        plan_management = st.text_area("Management rules")
        if st.form_submit_button("Create Plan"):
            try:
                new_plan_id = plan.create_plan(plan_name, criteria=plan_criteria or None,
                                                invalidation=plan_invalidation or None,
                                                management_rules=plan_management or None)
                st.success(f"Plan #{new_plan_id} created. Set it active above to start using it.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def render_discipline():
    st.subheader("Discipline Tracker")
    if st.button("Re-scan journal for violations"):
        flagged = discipline.scan_trades_for_violations()
        st.success(f"Scan complete — {len(flagged)} new flag(s) logged.")

    disc = discipline.discipline_score()
    st.metric("Discipline Score", f"{disc['score']}/100")
    if disc["breakdown"]:
        st.dataframe(pd.DataFrame(disc["breakdown"]).T, width="stretch")
    else:
        st.info("No violations flagged yet — or no trades logged.")


def render_broker():
    st.subheader("MT5 Trade History Import")
    st.caption("Read-only — pulls CLOSED trade history from your connected MT5 terminal. "
               "Does not place, modify, or close anything.")
    days_back = st.slider("Days of history to pull", 1, 90, 30)
    import_balance = st.number_input("Account balance to use for imported trades' risk %",
                                      value=10000.0, key="import_balance")
    if st.button("Connect and Import"):
        try:
            broker.connect()
            date_to = datetime.now()
            date_from = date_to - timedelta(days=days_back)
            inserted = broker.import_closed_trades(date_from, date_to, import_balance)
            broker.disconnect()
            discipline.scan_trades_for_violations()
            st.success(f"Imported {len(inserted)} new closed trade(s).")
        except Exception as e:
            st.error(f"Import failed: {e}")


def render_news():
    st.subheader("Economic Calendar")
    if st.button("Refresh calendar"):
        try:
            events = news.get_events(force_refresh=True)
            st.session_state["_news_events"] = events
        except Exception as e:
            st.error(f"Couldn't refresh the calendar: {e}")
    else:
        if "_news_events" not in st.session_state:
            try:
                st.session_state["_news_events"] = news.get_events()
            except Exception as e:
                st.error(f"Couldn't load the calendar: {e}")
                st.session_state["_news_events"] = []

    events = st.session_state.get("_news_events", [])
    high_impact = [e for e in events if e["impact"] == "High"]
    st.write(f"{len(high_impact)} high-impact events this week")
    if high_impact:
        st.dataframe(pd.DataFrame(high_impact)[["when", "currency", "title", "forecast", "previous"]],
                     width="stretch")

    st.divider()
    st.subheader("Check a pair right now")
    check_instrument = st.selectbox("Instrument", ["XAUUSD", "GBPUSD", "GBPJPY"], key="news_check_instrument")
    if events:
        blocked, matches = news.is_high_impact_window(check_instrument, events=events)
        if blocked:
            st.warning(f"Blocked window: {matches[0]['title']} ({matches[0]['currency']}) at {matches[0]['when']}")
        else:
            st.success("Clear — no high-impact event within the buffer window.")


def render_sanctuary():
    st.subheader("Reset Routine")
    for step in sanctuary.RESET_ROUTINE:
        st.markdown(f"**{step['step']}** — {step['prompt']}")

    st.divider()
    st.subheader("Reset History")
    history = sanctuary.list_resets()
    if history:
        st.dataframe(pd.DataFrame(history), width="stretch")
    else:
        st.info("No resets triggered yet.")


def render_notebook():
    st.subheader("New Note")
    note_mode = st.radio("Start from", ["Blank", "Template"], horizontal=True)
    if note_mode == "Template":
        template_choice = st.selectbox("Template", list(notebook.TEMPLATES.keys()))
    note_title = st.text_input("Title", key="note_title")
    if st.button("Create Note"):
        try:
            if note_mode == "Template":
                new_note_id = notebook.create_from_template(template_choice, note_title)
            else:
                new_note_id = notebook.create_note(note_title)
            st.success(f"Note #{new_note_id} created — edit it below.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))

    st.divider()
    st.subheader("Notes")
    all_notes = notebook.list_notes()
    for n in all_notes:
        with st.expander(f"{n['title']} ({n['category'] or 'uncategorized'})"):
            new_body = st.text_area("Body", value=n["body"] or "", key=f"note_body_{n['id']}")
            col1, col2 = st.columns(2)
            if col1.button("Save", key=f"save_note_{n['id']}"):
                notebook.update_note(n["id"], body=new_body)
                st.rerun()
            if col2.button("Delete", key=f"delete_note_{n['id']}"):
                notebook.delete_note(n["id"])
                st.rerun()


def render_academy():
    st.subheader("Add a Lesson")
    with st.form("add_lesson_form"):
        lesson_title = st.text_input("Title")
        lesson_content = st.text_area("Content")
        lesson_category = st.text_input("Category (optional)")
        lesson_source = st.text_input("Source (optional link or reference)")
        if st.form_submit_button("Add Lesson"):
            try:
                new_lesson_id = academy.create_lesson(lesson_title, content=lesson_content,
                                                       category=lesson_category or None,
                                                       source=lesson_source or None)
                st.success(f"Lesson #{new_lesson_id} added.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    st.divider()
    progress = academy.progress_summary()
    if progress["total"]:
        st.metric("Progress", f"{progress['completed']}/{progress['total']} ({progress['pct']}%)")

    lessons = academy.list_lessons()
    for lesson_row in lessons:
        done = lesson_row["completed_at"] is not None
        with st.expander(("\u2705 " if done else "\u2b1c ") + lesson_row["title"]):
            st.write(lesson_row["content"] or "—")
            if lesson_row["source"]:
                st.caption(f"Source: {lesson_row['source']}")
            col1, col2 = st.columns(2)
            if done:
                if col1.button("Mark incomplete", key=f"incomplete_{lesson_row['id']}"):
                    academy.mark_incomplete(lesson_row["id"])
                    st.rerun()
            else:
                if col1.button("Mark complete", key=f"complete_{lesson_row['id']}"):
                    academy.mark_complete(lesson_row["id"])
                    st.rerun()
            if col2.button("Delete", key=f"delete_lesson_{lesson_row['id']}"):
                academy.delete_lesson(lesson_row["id"])
                st.rerun()


def render_coach():
    st.subheader("AI Trade Review")
    st.caption("Requires ANTHROPIC_API_KEY set in your environment. Reviews process, not P&L predictions.")
    closed_trades = journal.list_trades(status="closed")
    if closed_trades:
        options = {f"#{t['id']} {t['instrument']} {t['direction']} (R: {t['realized_r_multiple']})": t
                   for t in closed_trades}
        choice = st.selectbox("Select a closed trade to review", list(options.keys()))
        if st.button("Get AI Review"):
            trade = options[choice]
            trade_events = discipline.list_events(trade["id"])
            flags = [e["event_type"] for e in trade_events]
            with st.spinner("Reviewing..."):
                try:
                    review = coach.review_trade(trade, discipline_flags=flags)
                    st.write("**Summary:**", review.get("summary"))
                    st.write("**Strengths:**", review.get("strengths"))
                    st.write("**Leaks:**", review.get("leaks"))
                    st.write("**Action item:**", review.get("action_item"))
                except Exception as e:
                    st.error(f"Review failed: {e}")
    else:
        st.info("Close some trades first — the coach reviews completed trades.")

    st.divider()
    st.subheader("Past Reviews")
    if closed_trades:
        for t in closed_trades:
            past = coach.get_coach_notes(t["id"])
            for note_row in past:
                with st.expander(f"Trade #{t['id']} — {note_row['created_at']}"):
                    st.write("**Summary:**", note_row["summary"])
                    st.write("**Strengths:**", note_row["strengths"])
                    st.write("**Leaks:**", note_row["leaks"])
                    st.write("**Action item:**", note_row["action_item"])


# ================================================================ Navigation
# Grouped sidebar sections instead of one flat 10-tab strip. Each group's
# sub-items render as sub-tabs within the main area; a single-item group
# (Overview) skips the sub-tab wrapper since there's nothing to switch
# between.
NAV_GROUPS = {
    "\U0001F4CA Overview": {"Dashboard": render_dashboard},
    "\U0001F4DD Trading": {"Trade Log": render_trade_log, "Plan": render_plan, "Discipline": render_discipline},
    "\U0001F6E1\uFE0F Protection": {"Broker Import": render_broker, "News": render_news, "Sanctuary": render_sanctuary},
    "\U0001F4DA Growth": {"Notebook": render_notebook, "Academy": render_academy, "Coach": render_coach},
}

with st.sidebar:
    st.markdown("## Navigate")
    selected_group = st.radio("Section", list(NAV_GROUPS.keys()), label_visibility="collapsed")

section_map = NAV_GROUPS[selected_group]
section_names = list(section_map.keys())

if len(section_names) == 1:
    section_map[section_names[0]]()
else:
    rendered_tabs = st.tabs(section_names)
    for rendered_tab, name in zip(rendered_tabs, section_names):
        with rendered_tab:
            section_map[name]()


# ============================================================ Floating Quick Log
# Reachable from every section, not just the Trading group — the one
# action used constantly shouldn't require switching sections first.
with st.container(key="quick_log_fab"):
    with st.popover("+ Quick Log"):
        st.markdown("**Quick Log Trade**")
        active_plan_fab = plan.get_active_plan()
        fab_instrument = st.selectbox("Instrument", ["XAUUSD", "GBPUSD", "GBPJPY", "Other"], key="fab_instrument")
        fab_direction = st.selectbox("Direction", ["long", "short"], key="fab_direction")
        fab_entry = st.number_input("Entry Price", format="%.5f", key="fab_entry")
        fab_stop = st.number_input("Stop Price", format="%.5f", key="fab_stop")
        fab_size = st.number_input("Size (units)", format="%.4f", min_value=0.0001, key="fab_size")
        fab_balance = st.number_input("Account Balance", value=10000.0, key="fab_balance")
        if st.button("Log it", key="fab_submit"):
            try:
                new_id = journal.log_trade(
                    instrument=fab_instrument, direction=fab_direction,
                    entry_price=fab_entry, stop_price=fab_stop, size_units=fab_size,
                    account_balance_at_entry=fab_balance,
                    plan_id=(active_plan_fab["id"] if active_plan_fab else None),
                )
                discipline.scan_trades_for_violations()
                st.success(f"Trade #{new_id} logged.")
            except ValueError as e:
                st.error(str(e))
