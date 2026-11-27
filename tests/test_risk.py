import pytest

from stock_trader.risk import position_size, risk_amount


def test_risk_amount_is_one_percent_of_equity():
    assert risk_amount(20_000.0, 0.01) == 200.0


def test_position_size_uses_stop_distance():
    # $200 risk / ($100 - $95) = 40 shares
    assert position_size(20_000.0, 100.0, 95.0, 0.01) == 40


def test_position_size_rounds_down_to_whole_shares():
    # $100 risk / $1.50 stop distance = 66.67 -> 66
    assert position_size(10_000.0, 50.0, 48.5, 0.01) == 66


def test_position_size_rejects_stop_at_or_above_entry():
    with pytest.raises(ValueError):
        position_size(20_000.0, 100.0, 100.0, 0.01)


def test_position_size_rejects_bad_risk_pct():
    with pytest.raises(ValueError):
        position_size(20_000.0, 100.0, 95.0, 0.0)
