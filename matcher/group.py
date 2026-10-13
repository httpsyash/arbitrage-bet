"""Group ticks from different books into one event. Stdlib only."""
from __future__ import annotations

import difflib
from .normalize import canonical_name


def _similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def same_event(e1: dict, e2: dict, threshold: float = 0.85) -> bool:
    if e1.get("sport") != e2.get("sport"):
        return False
    h1, a1 = canonical_name(e1.get("home", "")), canonical_name(e1.get("away", ""))
    h2, a2 = canonical_name(e2.get("home", "")), canonical_name(e2.get("away", ""))
    score = (_similar(h1, h2) + _similar(a1, a2)) / 2.0
    t1, t2 = e1.get("commence_ts", 0), e2.get("commence_ts", 0)
    time_ok = abs(t1 - t2) <= 2 * 3600
    return score >= threshold and time_ok


def best_odds_per_outcome(ticks: list[dict]) -> dict:
    """ticks: [{outcome, price, book}]. Returns {outcome: (best_price, book)}."""
    best: dict[str, tuple[float, str]] = {}
    for t in ticks:
        o, p, b = t["outcome"], float(t["price"]), t["book"]
        if o not in best or p > best[o][0]:
            best[o] = (p, b)
    return best
