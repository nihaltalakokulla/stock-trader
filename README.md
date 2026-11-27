# Stock Trader

Approval-gated swing-trading bot. The bot screens liquid US stocks, ranks them
with an ML model fed by price, volume, and news features, and texts a proposal
only when a pick clears a confidence bar. Trades execute only after the user
replies `YES`.

Paper trading first ($20,000 simulated), then Robinhood's official agentic
trading endpoint through a broker adapter ($500 live account).

## Status

- [x] Design spec and implementation plan
- [x] Settings, 1% risk sizing, trade state machine, SMS reply parsing
- [x] Screener, news sentiment with leakage guard, price/volume features
- [x] Confidence gate, idempotent paper broker, backtest harness
- [x] Proposal text, approval execution, repository seam
- [x] yfinance/Finnhub adapters, signal ranking, Supabase schema
- [x] Thin Cloudflare Worker for Twilio replies and GitHub dispatch
- [x] CLI wiring, GitHub Actions workflows, dashboard
- [x] ML model training pipeline and backtest harness
- [ ] Backtest tuning against real history and two-week paper dry run
- [ ] Two-week paper dry run, then Robinhood adapter

Design: `docs/superpowers/specs/2026-11-27-stock-trader-design.md`

Plan: `docs/superpowers/plans/2026-11-27-stock-trader-implementation.md`

## Tests

```powershell
# Python (uses the workspace interpreter in this environment)
..\NBA_Prediction_Bot\.venv\Scripts\python.exe -m pytest

# Worker (Node 22+ with native TypeScript support)
cd worker
node --test test/index.test.ts
```

## Layout

```text
src/stock_trader/   Python engine: risk, screener, news, features, gate,
                    paper broker, backtest, execution, data adapters
worker/             Cloudflare Worker: Twilio webhook -> Supabase -> dispatch
supabase/           schema, RLS, dashboard views
dashboard/          read-only static dashboard (next milestone)
docs/               design spec, implementation plan, setup guides
```
