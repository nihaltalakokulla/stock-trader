from datetime import UTC, datetime, timedelta

from stock_trader.db.repository import InMemoryRepository
from stock_trader.domain.approvals import Decision
from stock_trader.domain.proposals import Proposal
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


def test_stale_proposals_expire():
    repo = InMemoryRepository()
    now = datetime(2026, 11, 30, 14, 30, tzinfo=UTC)
    repo.insert_proposal(Proposal(
        id="p1", symbol="AAPL", qty=1, entry_price=100.0, stop_price=95.0,
        confidence=0.7, rationale="x",
        created_at=now - timedelta(days=1), expires_at=now,
    ))
    repo.expire_stale_proposals(now)
    assert repo.get_trade_state("p1") is TradeState.EXPIRED


def test_has_order_uses_client_id():
    repo = InMemoryRepository()
    repo.insert_order({"client_id": "c1"})
    assert repo.has_order("c1") is True
    assert repo.has_order("c2") is False
