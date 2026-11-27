import pandas as pd
import pytest

from stock_trader.backtest import backtest_long_only


def test_single_winner_trade_produces_profit_and_metrics():
    prices = pd.Series([100.0, 100.0, 110.0, 120.0, 120.0])
    entries = pd.Series([False, True, False, False, False])
    result = backtest_long_only(prices, entries, hold_days=2, cost_pct=0.0)
    assert result.metrics.total_return == pytest.approx(0.20)
    assert result.metrics.trades == 1
    assert result.metrics.win_rate == 1.0
    assert result.metrics.max_drawdown == 0.0


def test_costs_reduce_return():
    prices = pd.Series([100.0, 100.0, 110.0, 120.0, 120.0])
    entries = pd.Series([False, True, False, False, False])
    free = backtest_long_only(prices, entries, hold_days=2, cost_pct=0.0)
    paid = backtest_long_only(prices, entries, hold_days=2, cost_pct=0.001)
    assert paid.metrics.total_return < free.metrics.total_return


def test_losing_trade_reported():
    prices = pd.Series([100.0, 100.0, 90.0, 80.0, 80.0])
    entries = pd.Series([False, True, False, False, False])
    result = backtest_long_only(prices, entries, hold_days=2, cost_pct=0.0)
    assert result.metrics.win_rate == 0.0
    assert result.metrics.total_return == pytest.approx(-0.20)
