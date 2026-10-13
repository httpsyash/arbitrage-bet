"""Demo: fetch -> normalize -> detect -> virtual wallet -> compare markets."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.detector import arb_sum, profit_pct
from engine.stakes import calc_stakes, expected_return
from fetcher.oddsapi_client import fetch_odds_api
from matcher.normalize import canonical_name
from store import db


def main() -> None:
    db.init_db()
    ticks = fetch_odds_api()
    # normalize team names
    for t in ticks:
        t["home"] = canonical_name(t["home"])
        t["away"] = canonical_name(t["away"])
        t["outcome"] = canonical_name(t["outcome"])
    db.save_ticks(ticks)

    # group by event
    events: dict[str, list[dict]] = {}
    for t in ticks:
        events.setdefault(t["event_key"], []).append(t)

    print("=== ALL MARKETS COMPARISON ===")
    for ekey, ts in events.items():
        print(f"\n{ekey} ({ts[0]['sport']}): {ts[0]['home']} vs {ts[0]['away']}")
        by_outcome: dict[str, list[tuple[str, float]]] = {}
        for t in ts:
            by_outcome.setdefault(t["outcome"], []).append((t["book"], t["price"]))
        best = {}
        for outcome, quotes in by_outcome.items():
            quotes.sort(key=lambda x: -x[1])
            line = ", ".join(f"{b} {p}" for b, p in quotes)
            print(f"  {outcome:22s} | {line}  -> BEST {quotes[0][1]} @ {quotes[0][0]}")
            best[outcome] = quotes[0][1]
        odds = list(best.values())
        s = arb_sum(odds)
        p = profit_pct(odds)
        print(f"  arb_sum={s:.4f} profit={p:.2f}% {'<== SUREBET' if p >= 1.5 else ''}")

    # virtual wallet: user can add as much as wanted
    wallets = db.list_wallets()
    wid = wallets[0]["id"] if wallets else db.create_wallet("demo", 0.0)
    bal = db.topup_wallet(wid, 100000)
    print(f"\n=== VIRTUAL WALLET #{wid} balance after +100000 topup: {bal:.0f} ===")

    # place one paper bet on first surebet found
    for ekey, ts in events.items():
        by_outcome: dict[str, tuple[float, str]] = {}
        for t in ts:
            if t["outcome"] not in by_outcome or t["price"] > by_outcome[t["outcome"]][0]:
                by_outcome[t["outcome"]] = (t["price"], t["book"])
        outcomes = list(by_outcome)
        odds = [by_outcome[o][0] for o in outcomes]
        if profit_pct(odds) >= 1.5:
            from paper.wallet import place_paper_bet
            stakes = calc_stakes(10000, odds)
            legs = [{"outcome": o, "price": by_outcome[o][0], "book": by_outcome[o][1], "stake": s}
                    for o, s in zip(outcomes, stakes)]
            bid = place_paper_bet(wid, ekey, legs, sum(stakes))
            oid = db.save_opportunity(ekey, ts[0]["sport"], json.dumps(legs), arb_sum(odds), profit_pct(odds))
            print(f"paper bet #{bid} placed on {ekey}: stakes={stakes} expected_return={expected_return(stakes, odds):.0f} (opp #{oid})")
            break

    w = db.get_wallet(wid)
    print(f"wallet balance now: {w['balance']:.0f}")
    print("\nDone. DB at store/arb.db")


if __name__ == "__main__":
    main()
