from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestMetrics:
    total_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    trades: int


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.Series
    metrics: BacktestMetrics


def backtest_long_only(
    prices: pd.Series,
    entries: pd.Series,
    *,
    hold_days: int,
    cost_pct: float,
) -> BacktestResult:
    if len(prices) != len(entries):
        raise ValueError("prices and entries must align")
    if hold_days < 1:
        raise ValueError("hold_days must be >= 1")
    equity = 1.0
    curve: list[float] = [equity]
    trade_returns: list[float] = []
    i = 0
    while i < len(prices) - 1:
        if bool(entries.iloc[i]):
            exit_index = min(i + hold_days, len(prices) - 1)
            gross = prices.iloc[exit_index] / prices.iloc[i]
            net = gross * (1 - cost_pct) / (1 + cost_pct)
            trade_returns.append(float(net - 1.0))
            equity *= net
            curve.append(equity)
            i = exit_index + 1
        else:
            curve.append(equity)
            i += 1
    series = pd.Series(curve, dtype=float)
    daily = series.pct_change().dropna()
    sharpe = 0.0
    if len(daily) > 1 and daily.std(ddof=0) != 0:
        sharpe = float(daily.mean() / daily.std(ddof=0) * np.sqrt(252))
    peak = series.cummax()
    max_drawdown = float((series / peak - 1.0).min())
    wins = [r for r in trade_returns if r > 0]
    gross_win = sum(wins)
    gross_loss = -sum(r for r in trade_returns if r < 0)
    if gross_loss > 0:
        profit_factor = gross_win / gross_loss
    elif wins:
        profit_factor = float("inf")
    else:
        profit_factor = 0.0
    return BacktestResult(
        equity_curve=series,
        metrics=BacktestMetrics(
            total_return=float(series.iloc[-1] - 1.0),
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            win_rate=len(wins) / len(trade_returns) if trade_returns else 0.0,
            profit_factor=profit_factor,
            trades=len(trade_returns),
        ),
    )
