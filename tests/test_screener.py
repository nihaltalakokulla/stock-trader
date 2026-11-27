import pytest

from stock_trader.config import Settings
from stock_trader.domain.models import StockSnapshot
from stock_trader.screener import passes_screener


def snapshot(**overrides):
    base = dict(symbol="AAPL", price=50.0, avg_dollar_volume=50_000_000.0,
                sma_long=45.0, days_to_earnings=10)
    base.update(overrides)
    return StockSnapshot(**base)


def test_liquid_trending_stock_passes():
    assert passes_screener(snapshot(), Settings()) is True


@pytest.mark.parametrize("overrides", [
    {"price": 4.99},
    {"avg_dollar_volume": 9_999_999.0},
    {"sma_long": 55.0},
    {"days_to_earnings": 2},
    {"days_to_earnings": 0},
])
def test_each_rule_can_reject(overrides):
    assert passes_screener(snapshot(**overrides), Settings()) is False


def test_two_days_before_earnings_is_blacked_out_but_three_is_not():
    assert passes_screener(snapshot(days_to_earnings=2), Settings()) is False
    assert passes_screener(snapshot(days_to_earnings=3), Settings()) is True
