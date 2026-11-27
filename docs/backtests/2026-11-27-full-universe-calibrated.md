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
| 0.50 | +10.59% | 0.67 | -13.55% | 71 |
| 0.55 | +10.59% | 0.67 | -13.55% | 71 |
| 0.60 | +10.59% | 0.67 | -13.55% | 71 |
| 0.65 | +10.59% | 0.67 | -13.55% | 71 |
| 0.70 | +10.59% | 0.67 | -13.55% | 71 |
| 0.75 | +3.32% | 0.27 | -15.76% | 73 |

Chosen on validation: **0.50**

## Held-out test

| Metric | ML strategy | SPY | Equal-weight universe | Momentum top-1 |
|---|---|---|---|---|
| Total return | +3.61% | +7.72% | +14.57% | +9.60% |
| Sharpe | 0.29 | 0.58 | 0.79 | 0.77 |
| Max drawdown | -12.62% | -11.46% | -15.55% | -7.57% |
| Trades | 76 | 1 | 1 | 43 |
| Excess vs SPY | -4.12% | — | — | — |

## Probability calibration

| Window | Min | 10th pct | Median | 90th pct | Max | Brier |
|---|---|---|---|---|---|---|
| validation | 0.53 | 0.53 | 0.60 | 0.74 | 0.93 | 0.296 |
| test | 0.42 | 0.54 | 0.58 | 0.69 | 0.96 | 0.329 |

## Caveats

- News features are zero in this backtest: free historical news was not available, so the news half of the hybrid model is not validated here.
- Universe is today's liquid large caps (survivorship bias).
- Fixed 21-session hold with ATR stop approximates the live exit rules.
- Close-price fills with 0.1% cost per side; real slippage may be worse.
- Threshold was selected on validation and reported once on the held-out test window; still one sample, not a guarantee.
- Predicted probabilities cluster high: thresholds 0.50-0.65 produced identical portfolios, so the confidence gate is not yet calibrated.
