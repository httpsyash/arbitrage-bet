"""Proportional stake calculator. Stdlib only."""
from __future__ import annotations


def calc_stakes(bankroll: float, odds: list[float], round_to: int = 10) -> list[float]:
    s = sum(1.0 / o for o in odds)
    stakes = [bankroll * (1.0 / o) / s for o in odds]
    if round_to > 1:
        stakes = [round(x / round_to) * round_to for x in stakes]
    return stakes


def expected_return(stakes: list[float], odds: list[float]) -> float:
    return min(s * o for s, o in zip(stakes, odds))
