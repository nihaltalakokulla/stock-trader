from dataclasses import dataclass
from math import floor

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Signal:
    symbol: str
    date: pd.Timestamp
    probability: float


@dataclass(frozen=True)
class Trade:
    symbol: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    qty: int
    entry_price: float
    exit_price: float
    pnl: float
    reason: str


@dataclass(frozen=True)
class BacktestReport:
    trades: list[Trade]
    equity_curve: pd.Series
    metrics: dict[str, float]


def curve_metrics(equity_curve: pd.Series) -> dict[str, float]:
    daily = equity_curve.pct_change().dropna()
    sharpe = 0.0
    if len(daily) > 1 and daily.std(ddof=0) > 0:
        sharpe = float(daily.mean() / daily.std(ddof=0) * np.sqrt(252))
    peak = equity_curve.cummax()
    return {
        "total_return": float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1.0),
        "sharpe": sharpe,
        "max_drawdown": float((equity_curve / peak - 1.0).min()),
    }


def split_indices(
    n: int, train_frac: float = 0.6, val_frac: float = 0.2
) -> tuple[int, int, int, int]:
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    return 0, train_end, val_end, n


def _atr_at(frame: pd.DataFrame, period: int = 14) -> float:
    close = frame["Close"].astype(float)
    high = frame["High"].astype(float) if "High" in frame else close
    low = frame["Low"].astype(float) if "Low" in frame else close
    previous = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous).abs(), (low - previous).abs()],
        axis=1,
    ).max(axis=1)
    return float(true_range.iloc[-period:].mean())


def simulate_portfolio(
    bars: dict[str, pd.DataFrame],
    signals: list[Signal],
    *,
    starting_cash: float = 20_000.0,
    risk_pct: float = 0.01,
    max_positions: int = 5,
    hold_days: int = 21,
    stop_multiple: float = 2.0,
    cost_pct: float = 0.001,
) -> BacktestReport:
    if not bars:
        raise ValueError("bars are required")
    by_date: dict[pd.Timestamp, list[Signal]] = {}
    for signal in signals:
        by_date.setdefault(pd.Timestamp(signal.date), []).append(signal)

    calendar = sorted(
        {date for frame in bars.values() for date in frame.index}
    )
    calendar_index = {date: i for i, date in enumerate(calendar)}
    cash = starting_cash
    positions: dict[str, dict] = {}
    trades: list[Trade] = []
    curve: list[tuple[pd.Timestamp, float]] = []
    max_open = 0

    def close_position(symbol: str, date, gross_price: float, reason: str) -> None:
        nonlocal cash
        position = positions.pop(symbol)
        proceeds = position["qty"] * gross_price * (1 - cost_pct)
        cash += proceeds
        trades.append(
            Trade(
                symbol=symbol,
                entry_date=position["entry_date"],
                exit_date=date,
                qty=position["qty"],
                entry_price=position["entry_price"],
                exit_price=gross_price,
                pnl=proceeds - position["cost_basis"],
                reason=reason,
            )
        )

    for date in calendar:
        day_index = calendar_index[date]

        for symbol in list(positions):
            position = positions[symbol]
            frame = bars[symbol]
            if date not in frame.index:
                continue
            row = frame.loc[date]
            low = float(row["Low"]) if "Low" in frame else float(row["Close"])
            close = float(row["Close"])
            if low <= position["stop"]:
                close_position(symbol, date, position["stop"], "stop")
            elif day_index - position["entry_index"] >= hold_days:
                close_position(symbol, date, close, "time")

        for signal in by_date.get(date, []):
            if len(positions) >= max_positions:
                break
            symbol = signal.symbol
            if symbol in positions or symbol not in bars:
                continue
            frame = bars[symbol]
            if date not in frame.index:
                continue
            history = frame.loc[:date]
            close = float(history["Close"].iloc[-1])
            volatility = _atr_at(history)
            stop = close - stop_multiple * volatility
            if stop <= 0 or stop >= close:
                continue
            equity = cash + sum(
                item["qty"] * float(bars[name].loc[:date]["Close"].iloc[-1])
                for name, item in positions.items()
            )
            qty = floor((equity * risk_pct) / (close - stop))
            if qty < 1:
                continue
            entry_price = close * (1 + cost_pct)
            basis = entry_price * qty
            if basis > cash:
                continue
            cash -= basis
            positions[symbol] = {
                "qty": qty,
                "entry_price": entry_price,
                "entry_date": date,
                "entry_index": day_index,
                "stop": stop,
                "cost_basis": basis,
            }
            max_open = max(max_open, len(positions))

        equity = cash + sum(
            position["qty"]
            * float(bars[symbol].loc[:date]["Close"].iloc[-1])
            for symbol, position in positions.items()
        )
        curve.append((date, equity))

    if positions:
        last_date = calendar[-1]
        for symbol in list(positions):
            frame = bars[symbol]
            close_position(
                symbol, last_date, float(frame["Close"].iloc[-1]), "end"
            )
        curve[-1] = (
            last_date,
            cash,
        )

    equity_curve = pd.Series(
        [value for _, value in curve],
        index=pd.DatetimeIndex([date for date, _ in curve]),
        dtype=float,
    )
    daily = equity_curve.pct_change().dropna()
    sharpe = 0.0
    if len(daily) > 1 and daily.std(ddof=0) > 0:
        sharpe = float(daily.mean() / daily.std(ddof=0) * np.sqrt(252))
    peak = equity_curve.cummax()
    max_drawdown = float((equity_curve / peak - 1.0).min())
    pnls = [trade.pnl for trade in trades]
    wins = [pnl for pnl in pnls if pnl > 0]
    gross_win = sum(wins)
    gross_loss = -sum(pnl for pnl in pnls if pnl < 0)
    if gross_loss > 0:
        profit_factor = gross_win / gross_loss
    elif wins:
        profit_factor = float("inf")
    else:
        profit_factor = 0.0
    return BacktestReport(
        trades=trades,
        equity_curve=equity_curve,
        metrics={
            "total_return": float(equity_curve.iloc[-1] / starting_cash - 1.0),
            "sharpe": sharpe,
            "max_drawdown": max_drawdown,
            "win_rate": len(wins) / len(trades) if trades else 0.0,
            "profit_factor": profit_factor,
            "trades": float(len(trades)),
            "max_open_positions": float(max_open),
        },
    )
