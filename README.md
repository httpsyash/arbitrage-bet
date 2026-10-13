# arb-betting-system — Phase 1 (alert-only + virtual money)

Runs on stdlib-only Python 3. No pip needed.

## Run demo (mock odds -> compare markets -> virtual wallet topup -> paper bet)
```
python3 demo.py
```

## Run API (markets comparison + wallet topup)
```
python3 api/main.py
curl localhost:8000/markets
curl localhost:8000/wallets
curl -X POST localhost:8000/wallets -H 'Content-Type: application/json' -d '{"name":"main","balance":0}'
curl -X POST localhost:8000/wallets/1/topup -H 'Content-Type: application/json' -d '{"amount":50000}'
```

Set `ODDS_API_KEY` env var to hit the real Odds API instead of `fetcher/mock_data.json`.

## Layout
- `fetcher/` odds fetch (real API or mock)
- `matcher/` normalize + group same event across books
- `engine/` arb math + stakes
- `store/` sqlite schema + wallet ledger
- `paper/` virtual-money paper bets
- `api/` stdlib HTTP server
