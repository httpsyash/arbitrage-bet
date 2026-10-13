"""Full end-to-end API: markets + wallets + paper bets + opportunities. Stdlib only."""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.detector import arb_sum, profit_pct
from engine.stakes import calc_stakes, expected_return
from fetcher.oddsapi_client import fetch_odds_api
from matcher.normalize import canonical_name
from store import db

MIN_PROFIT = 1.5


def build_markets() -> list[dict]:
    ticks = fetch_odds_api()
    for t in ticks:
        t["home"] = canonical_name(t["home"])
        t["away"] = canonical_name(t["away"])
        t["outcome"] = canonical_name(t["outcome"])
    events: dict[str, list[dict]] = {}
    for t in ticks:
        events.setdefault(t["event_key"], []).append(t)
    out = []
    for ekey, ts in events.items():
        best: dict[str, dict] = {}
        for t in ts:
            o = t["outcome"]
            if o not in best or t["price"] > best[o]["price"]:
                best[o] = {"price": t["price"], "book": t["book"]}
        odds = [v["price"] for v in best.values()]
        s = arb_sum(odds)
        p = profit_pct(odds)
        outcomes = list(best)
        stakes = calc_stakes(10000, odds)
        legs = [{"outcome": o, "price": best[o]["price"], "book": best[o]["book"], "stake": st}
                for o, st in zip(outcomes, stakes)]
        db.save_ticks(ts)
        opp_id = None
        if p >= MIN_PROFIT:
            opp_id = db.save_opportunity(ekey, ts[0]["sport"], json.dumps(legs), s, p)
        out.append({"event_key": ekey, "sport": ts[0]["sport"], "home": ts[0]["home"],
                    "away": ts[0]["away"], "best": best, "legs": legs,
                    "arb_sum": s, "profit_pct": p, "is_arb": p >= MIN_PROFIT,
                    "opportunity_id": opp_id, "quotes": ts,
                    "expected_return_10k": expected_return(stakes, odds)})
    out.sort(key=lambda e: -e["profit_pct"])
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self):
        root = Path(__file__).resolve().parents[1]
        page = (root / "dashboard" / "index.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            n = 0
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return {}

    def do_GET(self):
        db.init_db()
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path in ("/", "/dashboard", "/index.html"):
                self._send_html()
            elif u.path == "/markets":
                self._send(build_markets())
            elif u.path == "/wallets":
                self._send(db.list_wallets())
            elif u.path == "/paper-bets":
                wid = q.get("wallet_id", [None])[0]
                self._send(db.list_paper_bets(int(wid) if wid else None))
            elif u.path == "/opportunities":
                self._send(db.list_opportunities(int(q.get("limit", ["100"])[0])))
            elif u.path == "/ledger":
                wid = int(q.get("wallet_id", ["0"])[0])
                self._send(db.list_ledger(wid))
            elif u.path == "/stats":
                mk = build_markets()
                arbs = [m for m in mk if m["is_arb"]]
                self._send({"events": len(mk), "arbs": len(arbs),
                            "best_profit": max([m["profit_pct"] for m in mk], default=0),
                            "sports": sorted({m["sport"] for m in mk})})
            else:
                self._send({"ok": True, "routes": ["GET /markets", "GET /stats", "GET /wallets",
                            "POST /wallets", "POST /wallets/<id>/topup", "POST /wallets/<id>/reset",
                            "GET /paper-bets?wallet_id=", "POST /paper-bets", "POST /paper-bets/<id>/settle",
                            "GET /opportunities", "GET /ledger?wallet_id="]})
        except ValueError as e:
            self._send({"error": str(e)}, 400)

    def do_POST(self):
        db.init_db()
        u = urlparse(self.path)
        payload = self._body()
        try:
            if u.path == "/wallets":
                wid = db.create_wallet(payload.get("name", "main"), float(payload.get("balance", 0)))
                self._send({"wallet_id": wid})
            elif u.path.startswith("/wallets/") and u.path.endswith("/topup"):
                wid = int(u.path.split("/")[2])
                bal = db.topup_wallet(wid, float(payload.get("amount", 0)))
                self._send({"wallet_id": wid, "balance": bal})
            elif u.path.startswith("/wallets/") and u.path.endswith("/reset"):
                wid = int(u.path.split("/")[2])
                bal = db.reset_wallet(wid, float(payload.get("amount", 0)))
                self._send({"wallet_id": wid, "balance": bal})
            elif u.path == "/paper-bets":
                from paper.wallet import place_paper_bet
                bid = place_paper_bet(int(payload["wallet_id"]), payload["event_key"],
                                      payload["legs"], float(payload["stake_total"]))
                self._send({"bet_id": bid})
            elif u.path.startswith("/paper-bets/") and u.path.endswith("/settle"):
                bid = int(u.path.split("/")[2])
                self._send(db.settle_paper_bet(bid, payload.get("result", "VOID"),
                                               float(payload.get("payout", 0))))
            else:
                self._send({"error": "not found"}, 404)
        except (ValueError, KeyError) as e:
            self._send({"error": str(e)}, 400)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    db.init_db()
    port = 8000
    print(f"serving on http://localhost:{port}  (dashboard at /)")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
