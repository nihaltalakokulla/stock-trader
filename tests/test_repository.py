from stock_trader.db.repository import InMemoryRepository
from stock_trader.domain.approvals import Decision
from stock_trader.domain.state import TradeState


def test_proposal_round_trip_and_approval_key():
    repo = InMemoryRepository()
    repo.save_proposal("p1", {"symbol": "AAPL"})
    assert repo.get_proposal("p1") == {"symbol": "AAPL"}
    repo.save_approval("approval-1", {"decision": Decision.YES.value})
    assert repo.get_approval("approval-1") == {"decision": "YES"}
    repo.save_approval("approval-1", {"decision": Decision.NO.value})
    assert repo.get_approval("approval-1") == {"decision": "YES"}


def test_trade_state_updates():
    repo = InMemoryRepository()
    repo.set_trade_state("t1", TradeState.PROPOSED)
    repo.set_trade_state("t1", TradeState.APPROVED)
    assert repo.get_trade_state("t1") is TradeState.APPROVED
