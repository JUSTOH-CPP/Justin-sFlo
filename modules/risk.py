"""
EdgeFlo app :: risk.py
Position sizing: fixed-fractional (the standard "risk 1% per trade" model)
and Kelly-based sizing derived from the journal's own win-rate / avg-R
stats, so the recommended size updates as real edge data accumulates
rather than staying pinned to an assumption made on day one.
"""

from dataclasses import dataclass
from .journal import performance_summary


@dataclass
class PositionSizeResult:
    method: str
    risk_pct_used: float
    risk_dollars: float
    size_units: float
    notes: str


def fixed_fractional_size(account_balance, risk_pct, entry_price, stop_price):
    """Classic risk-1%-per-trade sizing. This is the default and the safe
    fallback whenever there isn't enough closed-trade history for Kelly to
    be meaningful."""
    if account_balance <= 0:
        raise ValueError("Account balance must be positive")
    if risk_pct <= 0:
        raise ValueError("Risk % must be positive")

    risk_per_unit = abs(entry_price - stop_price)
    if risk_per_unit == 0:
        raise ValueError("Entry and stop price cannot be equal")

    risk_dollars = account_balance * (risk_pct / 100)
    size_units = risk_dollars / risk_per_unit
    return PositionSizeResult(
        method="fixed_fractional",
        risk_pct_used=risk_pct,
        risk_dollars=round(risk_dollars, 2),
        size_units=round(size_units, 4),
        notes=f"Risking {risk_pct}% of ${account_balance:,.0f} at ${risk_per_unit:.4f} risk/unit."
    )


def kelly_fraction(win_rate_pct, avg_r):
    """Kelly criterion for a binary win/loss system expressed in R-multiples.
    f* = W - (1-W)/b, where W = win probability and b is the payoff ratio
    implied by the blended average R across all trades. This is a blended
    edge estimate across the whole journal, not a per-setup one."""
    if avg_r is None or win_rate_pct is None or avg_r <= 0:
        return 0.0
    w = win_rate_pct / 100
    if not (0 < w < 1):
        return 0.0
    b = max(avg_r, 0.01)
    f_star = w - (1 - w) / b
    return max(0.0, min(f_star, 0.25))  # hard cap at 25% — full Kelly is never used raw


MIN_TRADES_FOR_KELLY = 20


def kelly_size(account_balance, entry_price, stop_price, fraction_of_kelly=0.5,
               min_trades=MIN_TRADES_FOR_KELLY):
    """Kelly sizing calibrated from the journal's own realized stats.
    fraction_of_kelly defaults to half-Kelly (0.5) — full Kelly is
    theoretically optimal but empirically too volatile for live accounts.
    Falls back to a zero-size result with an explanation if there isn't
    enough closed-trade history yet."""
    if account_balance <= 0:
        raise ValueError("Account balance must be positive")
    risk_per_unit = abs(entry_price - stop_price)
    if risk_per_unit == 0:
        raise ValueError("Entry and stop price cannot be equal")
    if not (0 < fraction_of_kelly <= 1):
        raise ValueError("fraction_of_kelly must be between 0 and 1")

    stats = performance_summary()
    if stats["count"] < min_trades:
        return PositionSizeResult(
            method="kelly",
            risk_pct_used=0,
            risk_dollars=0,
            size_units=0,
            notes=f"Only {stats['count']} closed trades logged — need {min_trades}+ for a "
                  f"stable Kelly estimate. Use fixed-fractional sizing until then."
        )

    f_star = kelly_fraction(stats["win_rate"], stats["avg_r"])
    applied_fraction = f_star * fraction_of_kelly
    risk_dollars = account_balance * applied_fraction
    size_units = risk_dollars / risk_per_unit

    return PositionSizeResult(
        method="kelly",
        risk_pct_used=round(applied_fraction * 100, 3),
        risk_dollars=round(risk_dollars, 2),
        size_units=round(size_units, 4),
        notes=f"Full Kelly f*={f_star:.3f} from {stats['count']} trades "
              f"(win rate {stats['win_rate']}%, avg R {stats['avg_r']}); "
              f"using {fraction_of_kelly:.0%} of Kelly."
    )
