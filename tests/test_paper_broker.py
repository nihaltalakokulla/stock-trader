import pytest

from stock_trader.brokers.paper import InsufficientFunds, PaperBroker
from stock_trader.domain.models import Side


def broker():
    return PaperBroker(20_000.0, lambda symbol: 100.0, slippage_pct=0.001)


def test_buy_applies_slippage_and_reduces_cash():
    b = broker()
    order = b.submit_order("AAPL", Side.BUY, 10, client_id="c1")
    assert order.fill_price == pytest.approx(100.10)
    assert b.get_positions()["AAPL"] == 10
    assert b.get_account().cash == pytest.approx(20_000.0 - 1_001.0)


def test_sell_returns_cash_minus_slippage():
    b = broker()
    b.submit_order("AAPL", Side.BUY, 10, client_id="c1")
    b.submit_order("AAPL", Side.SELL, 10, client_id="c2")
    assert "AAPL" not in b.get_positions()
    assert b.get_account().cash == pytest.approx(18_999.0 + 999.0)


def test_insufficient_cash_rejected():
    b = PaperBroker(500.0, lambda symbol: 100.0)
    with pytest.raises(InsufficientFunds):
        b.submit_order("AAPL", Side.BUY, 10, client_id="c1")
    assert b.get_positions() == {}


def test_duplicate_client_id_does_not_trade_twice():
    b = broker()
    first = b.submit_order("AAPL", Side.BUY, 10, client_id="same")
    second = b.submit_order("AAPL", Side.BUY, 10, client_id="same")
    assert first == second
    assert b.get_positions()["AAPL"] == 10


def test_cannot_sell_more_than_held():
    b = broker()
    with pytest.raises(ValueError):
        b.submit_order("AAPL", Side.SELL, 1, client_id="c1")


def test_restored_positions_can_be_sold():
    b = PaperBroker(
        19_000.0, lambda symbol: 100.0, positions={"AAPL": 5}
    )
    assert b.get_positions()["AAPL"] == 5
    b.submit_order("AAPL", Side.SELL, 5, client_id="exit-1")
    assert "AAPL" not in b.get_positions()
