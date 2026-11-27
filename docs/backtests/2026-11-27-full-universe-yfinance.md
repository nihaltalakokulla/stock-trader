# Stock Trader Walk-Forward Backtest

Generated 2026-11-27 · 47 symbols · 5y daily data
Data source: yfinance (10s timeout) with Yahoo chart fallback

## Split

- Train through **2024-11-25**
- Validation **2024-11-26 → 2025-11-26**
- Held-out test **2025-11-28 → 2026-11-27**

## Validation threshold sweep

| Threshold | Return | Sharpe | Max DD | Trades |
|---|---|---|---|---|
| 0.50 | +13.15% | 0.76 | -19.39% | 75 |
| 0.55 | +13.15% | 0.76 | -19.39% | 75 |
| 0.60 | +13.15% | 0.76 | -19.39% | 75 |
| 0.65 | +13.15% | 0.76 | -19.39% | 75 |
| 0.70 | -3.65% | -0.16 | -19.33% | 72 |
| 0.75 | -2.21% | -0.08 | -17.51% | 66 |

Chosen on validation: **0.50**

## Held-out test

| Metric | Strategy | SPY buy-and-hold |
|---|---|---|
| Total return | +15.43% | +7.72% |
| Excess return | +7.70% | — |
| Sharpe (daily→annualized) | 0.92 | — |
| Max drawdown | -13.15% | — |
| Win rate | 42.0% | — |
| Profit factor | 1.37 | — |
| Trades | 81 | — |
| Max concurrent positions | 5 | — |

## Caveats

- News features are zero in this backtest: free historical news was not available, so the news half of the hybrid model is not validated here.
- Universe is today's liquid large caps (survivorship bias).
- Fixed 21-session hold with ATR stop approximates the live exit rules.
- Close-price fills with 0.1% cost per side; real slippage may be worse.
- Threshold was selected on validation and reported once on the held-out test window; still one sample, not a guarantee.
- Predicted probabilities cluster high: thresholds 0.50-0.65 produced identical portfolios, so the confidence gate is not yet calibrated.
