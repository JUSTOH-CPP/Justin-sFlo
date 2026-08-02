# EdgeFlo app — spec

A local, discipline-first trading superapp inspired by EdgeFlo
(edgeflo.com), built as a standalone desktop app in Python/Streamlit for
Justin's Anaconda `quant` environment. Not affiliated with or a copy of
EdgeFlo's code/content — this recreates the *workflow shape* using the
research below, then adapts it for a solo, local, no-subscription build.

## Research: what EdgeFlo actually is

EdgeFlo (edgeflo.com) markets itself as a "discipline-first trading
superapp" with 10 modules, based on their public site (July 2026):

1. **Trading** — execution with auto-calculated risk/position size,
   one-click trade from the chart, direct MT4/MT5/cTrader connection
2. **Guardrails** — set max trades, max daily loss, profit cap, risk per
   trade, session windows; trade button disables when a limit is hit
3. **Journal** — trades auto-import from broker; log emotion + notes/
   screenshots instantly, tied to each trade
4. **Dashboard** — win rate, profit factor, equity curve, discipline
   score, "Edge Score" (unlocks after 100 trades)
5. **News** — economic calendar filtered to your watchlist; block
   trading around high-impact events
6. **Plan** — define setups/criteria/invalidation/management rules,
   pin an Active plan beside the chart, track compliance
7. **Notebook** — strategy notes, templates for reviews/mindset
8. **Sanctuary** — structured reset routine (meditation, breathing,
   calm prompts) to interrupt revenge trading
9. **FloAI** — chat coach on your execution/journal data, weekly
   AI-generated recap
10. **Academy** — step-by-step lessons from the founder (proprietary
    content, not reproducible here)

Pricing is $44–63/mo; broker connection is read-only (EdgeFlo states it
never touches funds or places trades on your behalf directly — user
executes, EdgeFlo enforces/journals around that execution).

## What we're building instead

Same 10 module *shapes*, adapted for a solo local build:

| # | Module | Scope for this build |
|---|--------|----------------------|
| 1 | `db.py` | SQLite schema — **done** |
| 2 | `journal.py` | Log/close trades manually, R-multiple calc |
| 3 | `risk.py` | Fixed-fractional + Kelly position sizing |
| 4 | `plan.py` | Active trade plan, pinned, compliance tracking |
| 5 | `discipline.py` | Rule flags, detected after the fact from journal data (no live blocking — see below) |
| 6 | `broker.py` | **Read-only MT5 import only.** Pulls trade history into the journal automatically. No order placement, no live guardrail-blocking — that's out of scope for now. |
| 7 | `news.py` | Economic calendar (free feed), flag high-impact windows |
| 8 | `notebook.py` | Freeform notes/templates |
| 9 | `sanctuary.py` | Reset prompt after a flagged revenge-entry pattern |
| 10 | `coach.py` | Claude API trade review + weekly digest |
| 11 | `academy.py` | Personal lesson/checklist tracker (own content, not EdgeFlo's) |

### Explicitly out of scope for now
- **Live order execution** — EdgeFlo lets you trade from inside the app;
  we are not building order placement. `broker.py` only *reads* MT5
  trade history.
- **Live guardrail blocking** — since we're not sitting between Justin
  and order execution, `discipline.py` flags rule breaks after import/
  entry rather than disabling a trade button in real time. This could
  be revisited once read-only import has been solid for a while.
- Reproducing EdgeFlo's Academy course content (that's their IP).

## Architecture

Three layers, one local process, no server:

- **UI layer** — `app.py`, Streamlit, one tab per module
- **Service layer** — `modules/`, one file per module above, plain
  Python functions, no framework coupling so modules are testable
  standalone
- **Data layer** — `db.py`, single SQLite file (`data/edgeflo.db`)

External dependencies: Claude API (coach.py only), MetaTrader5 Python
package (broker.py, read-only), a free economic calendar feed (news.py).

## Build process

Standalone git repo, separate from `quant-trading`. One module built,
tested, and committed at a time. Justin pushes to GitHub himself after
each commit (no push access configured for this environment).

## Status

- [x] Step 1: `db.py` — SQLite schema, verified
- [x] Step 2: `journal.py`
- [x] Step 3: `risk.py`
- [x] Step 4: `plan.py`
- [x] Step 5: `discipline.py`
- [x] Step 6: `broker.py` (read-only MT5 import) — live connection confirmed
      working against Justin's real MT5 terminal (`verify_broker.py`),
      returned 0 closed positions as expected (fresh/demo account, no
      history yet). Position-reconstruction logic (matching IN/OUT deals,
      computing R, handling missing stops) is tested against mocked deal
      data only — not yet confirmed against a real closed trade's actual
      field values. Re-verify once real trade history exists.
- [x] Step 7: `news.py` — live feed confirmed working end to end on
      Justin's machine (verify_news.py)
- [x] Step 8: `notebook.py`
- [x] Step 9: `sanctuary.py`
- [x] Step 10: `coach.py` — built and tested against a mocked Claude API
      client (JSON parsing, DB writes, error handling, markdown-fence
      edge case all verified). Live API call NOT yet verified — Justin
      doesn't currently have API billing set up. Options on the table:
      (a) Anthropic's small signup credit, (b) swap to a free local
      model via Ollama, same interface. Deferred, not blocking.
- [x] Step 11: `academy.py`
- [x] Step 12: `app.py` — Streamlit UI tying every module together.
      Independently re-verified (not just accepted): ran the actual app
      headlessly via streamlit.testing.v1.AppTest and confirmed, through
      real widget interaction, that trades log and close with correct
      values/R-multiple, Plan/Notebook/Academy/Discipline tabs all work,
      the sanctuary pending-reset banner genuinely appears after a real
      revenge-entry scenario, and — the specific claim worth calling
      out — a live request to the news feed does return a genuine 403
      from this sandbox, and the app survives it gracefully both in the
      News tab and inside the Log Trade submit handler (a trade still
      saves correctly even when the news check fails).
