"""Arbitrage detection math. Stdlib only."""
from __future__ import annotations


def arb_sum(odds: list[float]) -> float:
    return sum(1.0 / o for o in odds if o and o > 1.0)


def profit_pct(odds: list[float], commission: float = 0.0) -> float:
    """Return surebet profit % after commission. Negative = no arb."""
    s = arb_sum(odds)
    if s <= 0:
        return -100.0
    # commission reduces effective odds
    eff = [o * (1.0 - commission) for o in odds]
    s_eff = arb_sum(eff)
    return (1.0 - s_eff) * 100.0


def is_arb(odds: list[float], min_profit_pct: float = 1.5, commission: float = 0.0) -> bool:
    return profit_pct(odds, commission) >= min_profit_pct
