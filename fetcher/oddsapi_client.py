"""Odds fetcher: real Odds API when ODDS_API_KEY is set, else mock data. Stdlib only."""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

MOCK_PATH = Path(__file__).with_name("mock_data.json")


def mock_ticks() -> list[dict]:
    return json.loads(MOCK_PATH.read_text())


def fetch_odds_api(sport: str = "soccer_epl") -> list[dict]:
    key = os.getenv("ODDS_API_KEY", "")
    if not key:
        return mock_ticks()
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?apiKey={key}&regions=eu,uk&markets=h2h&oddsFormat=decimal"
    with urllib.request.urlopen(url, timeout=15) as r:
        data = json.loads(r.read().decode())
    ticks: list[dict] = []
    now = int(time.time())
    for ev in data:
        home, away = ev.get("home_team", ""), ev.get("away_team", "")
        ekey = ev.get("id", f"{home}-{away}")
        for bm in ev.get("bookmakers", []):
            for m in bm.get("markets", []):
                for o in m.get("outcomes", []):
                    ticks.append({
                        "event_key": ekey, "sport": sport,
                        "home": home, "away": away,
                        "book": bm.get("key", ""), "outcome": o.get("name", ""),
                        "price": float(o.get("price", 0)), "fetched_at": now,
                    })
    return ticks
