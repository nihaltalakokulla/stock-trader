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
- [x] First walk-forward backtest against 5 years of real history
- [ ] Backtest tuning and two-week paper dry run
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

## Backtest snapshot

5 years of yfinance daily data, 47 large-cap symbols, chronological
train/validation/test, 0.1% cost per side, 21-session hold, ATR stops, 1% risk
per trade:

| Metric (held-out, calibrated) | ML strategy | SPY | Equal-weight | Momentum |
|---|---|---|---|---|
| Total return | +3.61% | +7.72% | +14.57% | +9.60% |
| Sharpe | 0.29 | 0.58 | 0.79 | 0.77 |
| Max drawdown | -12.62% | -11.46% | -15.55% | -7.57% |
| Trades | 76 | 1 | 1 | 43 |

The uncalibrated run appeared to return +15.43%, but isotonic calibration
revealed that as overconfidence: the honest held-out result trails SPY,
equal-weight ownership, and the momentum baseline. Sigmoid calibration was
worse (-1.38%). News features remain zero because historical free news was
unavailable. This model is experimental and must not trade real money yet.

Full report: `docs/backtests/2026-11-27-full-universe-calibrated.md`

Paper-trading setup: `docs/paper-runbook.md`

## Layout

```text
src/stock_trader/   Python engine: risk, screener, news, features, gate,
                    paper broker, backtest, execution, data adapters
worker/             Cloudflare Worker: Twilio webhook -> Supabase -> dispatch
supabase/           schema, RLS, dashboard views
dashboard/          read-only static dashboard (next milestone)
docs/               design spec, implementation plan, setup guides
```
