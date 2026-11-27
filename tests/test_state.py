import pytest

from stock_trader.domain.state import InvalidTransition, TradeState, transition


def test_approval_flow_transitions():
    assert transition(TradeState.PROPOSED, TradeState.APPROVED) is TradeState.APPROVED
    assert transition(TradeState.APPROVED, TradeState.ORDER_SUBMITTED) is TradeState.ORDER_SUBMITTED
    assert transition(TradeState.FILLED, TradeState.OPEN) is TradeState.OPEN
    assert transition(TradeState.OPEN, TradeState.EXIT_SUBMITTED) is TradeState.EXIT_SUBMITTED
    assert transition(TradeState.EXIT_SUBMITTED, TradeState.CLOSED) is TradeState.CLOSED


def test_cannot_close_an_unapproved_proposal():
    with pytest.raises(InvalidTransition):
        transition(TradeState.PROPOSED, TradeState.CLOSED)


def test_terminal_states_have_no_exits():
    for terminal in (TradeState.CLOSED, TradeState.REJECTED,
                     TradeState.EXPIRED, TradeState.CANCELLED):
        with pytest.raises(InvalidTransition):
            transition(terminal, TradeState.OPEN)
