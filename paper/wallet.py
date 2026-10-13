"""Virtual-money paper trading. Stdlib only."""
from __future__ import annotations

import time
from store import db


def place_paper_bet(wallet_id: int, event_key: str, legs: list[dict], stake_total: float) -> int:
    import json
    w = db.get_wallet(wallet_id)
    if w is None:
        raise ValueError("wallet not found")
    if stake_total <= 0 or stake_total > w["balance"]:
        raise ValueError("insufficient virtual balance")
    con = db.connect()
    new_bal = w["balance"] - stake_total
    con.execute("UPDATE virtual_wallets SET balance=? WHERE id=?", (new_bal, wallet_id))
    con.execute(
        "INSERT INTO virtual_wallet_ledger (wallet_id, kind, amount, balance_after, created_at) VALUES (?, 'STAKE', ?, ?, ?)",
        (wallet_id, -stake_total, new_bal, int(time.time())),
    )
    cur = con.execute(
        "INSERT INTO paper_bets (wallet_id, event_key, legs, stake_total, status, placed_at) VALUES (?,?,?,?, 'OPEN', ?)",
        (wallet_id, event_key, json.dumps(legs), stake_total, int(time.time())),
    )
    bid = cur.lastrowid
    con.commit()
    con.close()
    return bid
