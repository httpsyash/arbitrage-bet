"""SQLite store. Stdlib only."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).with_name("arb.db")
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    con = connect()
    con.executescript(SCHEMA_PATH.read_text())
    con.commit()
    con.close()


# ---- virtual wallet ----

def create_wallet(name: str, starting_balance: float = 0.0) -> int:
    con = connect()
    cur = con.execute("INSERT INTO virtual_wallets (name, balance) VALUES (?, ?)", (name, starting_balance))
    wid = cur.lastrowid
    con.execute(
        "INSERT INTO virtual_wallet_ledger (wallet_id, kind, amount, balance_after, created_at) VALUES (?, 'CREATE', ?, ?, ?)",
        (wid, starting_balance, starting_balance, int(time.time())),
    )
    con.commit()
    con.close()
    return wid


def topup_wallet(wallet_id: int, amount: float) -> float:
    """User can add as much virtual money as wanted. Returns new balance."""
    if amount <= 0:
        raise ValueError("topup amount must be > 0")
    con = connect()
    row = con.execute("SELECT balance FROM virtual_wallets WHERE id=?", (wallet_id,)).fetchone()
    if row is None:
        con.close()
        raise ValueError("wallet not found")
    new_bal = row["balance"] + amount
    con.execute("UPDATE virtual_wallets SET balance=? WHERE id=?", (new_bal, wallet_id))
    con.execute(
        "INSERT INTO virtual_wallet_ledger (wallet_id, kind, amount, balance_after, created_at) VALUES (?, 'TOPUP', ?, ?, ?)",
        (wallet_id, amount, new_bal, int(time.time())),
    )
    con.commit()
    con.close()
    return new_bal


def get_wallet(wallet_id: int) -> dict | None:
    con = connect()
    row = con.execute("SELECT * FROM virtual_wallets WHERE id=?", (wallet_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def list_wallets() -> list[dict]:
    con = connect()
    rows = con.execute("SELECT * FROM virtual_wallets ORDER BY id").fetchall()
    con.close()
    return [dict(r) for r in rows]


def save_ticks(ticks: list[dict]) -> None:
    con = connect()
    now = int(time.time())
    con.executemany(
        "INSERT INTO ticks (event_key, sport, home, away, book, outcome, price, fetched_at) VALUES (?,?,?,?,?,?,?,?)",
        [(t["event_key"], t["sport"], t["home"], t["away"], t["book"], t["outcome"], t["price"], now) for t in ticks],
    )
    con.commit()
    con.close()


def save_opportunity(event_key: str, sport: str, legs: str, arb_sum: float, profit_pct: float) -> int:
    con = connect()
    cur = con.execute(
        "INSERT INTO opportunities (event_key, sport, legs, arb_sum, profit_pct, created_at) VALUES (?,?,?,?,?,?)",
        (event_key, sport, legs, arb_sum, profit_pct, int(time.time())),
    )
    oid = cur.lastrowid
    con.commit()
    con.close()
    return oid


def list_opportunities(limit: int = 100) -> list[dict]:
    con = connect()
    rows = con.execute("SELECT * FROM opportunities ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def reset_wallet(wallet_id: int, amount: float) -> float:
    if amount < 0:
        raise ValueError("reset amount must be >= 0")
    con = connect()
    row = con.execute("SELECT id FROM virtual_wallets WHERE id=?", (wallet_id,)).fetchone()
    if row is None:
        con.close()
        raise ValueError("wallet not found")
    con.execute("UPDATE virtual_wallets SET balance=? WHERE id=?", (amount, wallet_id))
    con.execute(
        "INSERT INTO virtual_wallet_ledger (wallet_id, kind, amount, balance_after, created_at) VALUES (?, 'RESET', ?, ?, ?)",
        (wallet_id, amount, amount, int(time.time())),
    )
    con.commit()
    con.close()
    return amount


def list_ledger(wallet_id: int, limit: int = 100) -> list[dict]:
    con = connect()
    rows = con.execute(
        "SELECT * FROM virtual_wallet_ledger WHERE wallet_id=? ORDER BY id DESC LIMIT ?", (wallet_id, limit)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def list_paper_bets(wallet_id: int | None = None, limit: int = 100) -> list[dict]:
    con = connect()
    if wallet_id is None:
        rows = con.execute("SELECT * FROM paper_bets ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    else:
        rows = con.execute(
            "SELECT * FROM paper_bets WHERE wallet_id=? ORDER BY id DESC LIMIT ?", (wallet_id, limit)
        ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def settle_paper_bet(bet_id: int, result: str, payout: float = 0.0) -> dict:
    """result: WON | LOST | VOID. WON credits payout, VOID refunds stake, LOST credits 0."""
    result = result.upper()
    if result not in ("WON", "LOST", "VOID"):
        raise ValueError("result must be WON, LOST or VOID")
    con = connect()
    bet = con.execute("SELECT * FROM paper_bets WHERE id=?", (bet_id,)).fetchone()
    if bet is None:
        con.close()
        raise ValueError("bet not found")
    if bet["status"] != "OPEN":
        con.close()
        raise ValueError("bet already settled")
    w = con.execute("SELECT balance FROM virtual_wallets WHERE id=?", (bet["wallet_id"],)).fetchone()
    credit = float(payout) if result == "WON" else (float(bet["stake_total"]) if result == "VOID" else 0.0)
    new_bal = w["balance"] + credit
    con.execute("UPDATE virtual_wallets SET balance=? WHERE id=?", (new_bal, bet["wallet_id"]))
    con.execute(
        "INSERT INTO virtual_wallet_ledger (wallet_id, kind, amount, balance_after, created_at) VALUES (?, ?, ?, ?, ?)",
        (bet["wallet_id"], "SETTLE_" + result, credit, new_bal, int(time.time())),
    )
    con.execute("UPDATE paper_bets SET status=? WHERE id=?", (result, bet_id))
    con.commit()
    con.close()
    return {"bet_id": bet_id, "status": result, "credit": credit, "balance": new_bal}
