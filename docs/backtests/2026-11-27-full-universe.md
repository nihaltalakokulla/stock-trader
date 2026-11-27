# Stock Trader Walk-Forward Backtest

Generated 2026-11-27 · 47 symbols · 5y daily data

## Split

- Train through **2024-11-25**
- Validation **2024-11-26 → 2025-11-26**
- Held-out test **2025-11-28 → 2026-11-27**

## Validation threshold sweep

| Threshold | Return | Sharpe | Max DD | Trades |
|---|---|---|---|---|
| 0.50 | +14.25% | 0.83 | -19.44% | 74 |
| 0.55 | +14.25% | 0.83 | -19.44% | 74 |
| 0.60 | +14.25% | 0.83 | -19.44% | 74 |
| 0.65 | +14.25% | 0.83 | -19.44% | 74 |
| 0.70 | -8.46% | -0.50 | -18.53% | 73 |
| 0.75 | -3.50% | -0.19 | -16.72% | 65 |

Chosen on validation: **0.50**

## Held-out test

| Metric | Strategy | SPY buy-and-hold |
|---|---|---|
| Total return | +15.77% | +7.72% |
| Excess return | +8.04% | — |
| Sharpe (daily→annualized) | 0.96 | — |
| Max drawdown | -10.77% | — |
| Win rate | 43.8% | — |
| Profit factor | 1.40 | — |
| Trades | 80 | — |
| Max concurrent positions | 5 | — |

## Caveats

- News features are zero in this backtest: free historical news was not available, so the news half of the hybrid model is not validated here.
- Universe is today's liquid large caps (survivorship bias).
- Fixed 21-session hold with ATR stop approximates the live exit rules.
- Close-price fills with 0.1% cost per side; real slippage may be worse.
- Threshold was selected on validation and reported once on the held-out test window; still one sample, not a guarantee.
- Predicted probabilities cluster high: thresholds 0.50-0.65 produced identical portfolios, so the confidence gate is not yet calibrated.
