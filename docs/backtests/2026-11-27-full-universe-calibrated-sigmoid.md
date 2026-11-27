# Stock Trader Walk-Forward Backtest

Generated 2026-11-27 · 47 symbols · 5y daily data
Data source: yfinance (10s timeout) with Yahoo chart fallback
Calibration: sigmoid

## Split

- Train through **2024-11-25**
- Validation **2024-11-26 → 2025-11-26**
- Held-out test **2025-11-28 → 2026-11-27**

## Validation threshold sweep

| Threshold | Return | Sharpe | Max DD | Trades |
|---|---|---|---|---|
| 0.50 | +8.53% | 0.52 | -17.55% | 73 |
| 0.55 | +8.53% | 0.52 | -17.55% | 73 |
| 0.60 | +8.53% | 0.52 | -17.55% | 73 |
| 0.65 | +8.53% | 0.52 | -17.55% | 73 |
| 0.70 | +7.49% | 0.48 | -17.69% | 74 |
| 0.75 | +8.42% | 0.69 | -10.79% | 38 |

Chosen on validation: **0.50**

## Held-out test

| Metric | ML strategy | SPY | Equal-weight universe | Momentum top-1 |
|---|---|---|---|---|
| Total return | -1.38% | +7.72% | +14.57% | +9.60% |
| Sharpe | -0.02 | 0.58 | 0.79 | 0.77 |
| Max drawdown | -14.99% | -11.46% | -15.55% | -7.57% |
| Trades | 79 | 1 | 1 | 43 |
| Excess vs SPY | -9.11% | — | — | — |

## Probability calibration

| Window | Min | 10th pct | Median | 90th pct | Max | Brier |
|---|---|---|---|---|---|---|
| validation | 0.47 | 0.55 | 0.62 | 0.71 | 0.81 | 0.265 |
| test | 0.47 | 0.55 | 0.59 | 0.64 | 0.71 | 0.274 |

## Caveats

- News features are zero in this backtest: free historical news was not available, so the news half of the hybrid model is not validated here.
- Universe is today's liquid large caps (survivorship bias).
- Fixed 21-session hold with ATR stop approximates the live exit rules.
- Close-price fills with 0.1% cost per side; real slippage may be worse.
- Threshold was selected on validation and reported once on the held-out test window; still one sample, not a guarantee.
- Predicted probabilities cluster high: thresholds 0.50-0.65 produced identical portfolios, so the confidence gate is not yet calibrated.
