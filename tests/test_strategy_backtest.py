import numpy as np
import pandas as pd
import pytest

from stock_trader.strategy_backtest import (
    Signal,
    curve_metrics,
    simulate_portfolio,
    split_indices,
)


def make_bars(closes):
    index = pd.date_range("2026-01-01", periods=len(closes), freq="B")
    close = pd.Series(closes, index=index, dtype=float)
    return pd.DataFrame({
        "Close": close,
        "High": close + 1.0,
        "Low": close - 1.0,
        "Volume": np.full(len(closes), 1_000_000.0),
    })


def test_split_indices_are_chronological():
    assert split_indices(100, 0.6, 0.2) == (0, 60, 80, 100)


def test_curve_metrics_reports_return_and_drawdown():
    index = pd.date_range("2026-01-01", periods=3, freq="B")
    metrics = curve_metrics(pd.Series([100.0, 110.0, 99.0], index=index))
    assert metrics["total_return"] == pytest.approx(-0.01)
    assert metrics["max_drawdown"] == pytest.approx(-0.10)


def test_time_exit_and_costs_produce_expected_pnl():
    bars = {"AAPL": make_bars([100.0] * 20)}
    signals = [Signal("AAPL", bars["AAPL"].index[2], 0.8)]
    report = simulate_portfolio(
        bars, signals, hold_days=5, cost_pct=0.001
    )
    assert len(report.trades) == 1
    trade = report.trades[0]
    assert trade.qty == 50
    assert trade.reason == "time"
    assert trade.pnl == pytest.approx(-10.0, abs=0.01)
    assert report.metrics["total_return"] == pytest.approx(-0.0005, abs=0.001)


def test_stop_exit_cuts_the_loss():
    bars = {"AAPL": make_bars([100, 100, 100, 90, 90, 90, 90, 90])}
    signals = [Signal("AAPL", bars["AAPL"].index[2], 0.8)]
    report = simulate_portfolio(
        bars, signals, hold_days=10, cost_pct=0.001
    )
    trade = report.trades[0]
    assert trade.reason == "stop"
    assert trade.exit_price == pytest.approx(96.0, abs=0.2)
    assert trade.pnl < -30


def test_max_positions_caps_concurrent_entries():
    symbols = ["A", "B", "C", "D", "E", "F"]
    bars = {}
    for symbol in symbols:
        data = make_bars([100.0] * 20)
        data["High"] = data["Close"] + 4.0
        data["Low"] = data["Close"] - 4.0
        bars[symbol] = data
    signals = [
        Signal(symbol, bars[symbol].index[2], 0.8) for symbol in symbols
    ]
    report = simulate_portfolio(
        bars, signals, max_positions=5, hold_days=3
    )
    assert report.metrics["max_open_positions"] == 5
    assert len(report.trades) == 5
