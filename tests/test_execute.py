from datetime import UTC, datetime, timedelta

from stock_trader.brokers.paper import PaperBroker
from stock_trader.domain.approvals import Decision
from stock_trader.domain.proposals import Proposal
from stock_trader.engine.execute import ExecutionStatus, execute_approval

NOW = datetime(2026, 11, 27, 22, 0, tzinfo=UTC)


def proposal(expires_at=None):
    return Proposal(
        id="p1", symbol="AAPL", qty=10, entry_price=100.0, stop_price=95.0,
        confidence=0.7, rationale="test",
        created_at=NOW - timedelta(hours=1),
        expires_at=expires_at or NOW + timedelta(hours=12),
    )


def test_yes_fills_once():
    broker = PaperBroker(20_000.0, lambda s: 100.0)
    assert execute_approval(proposal(), Decision.YES, broker, NOW, "c1") is ExecutionStatus.FILLED
    assert execute_approval(proposal(), Decision.YES, broker, NOW, "c1") is ExecutionStatus.DUPLICATE
    assert broker.get_positions()["AAPL"] == 10


def test_no_rejects():
    broker = PaperBroker(20_000.0, lambda s: 100.0)
    assert execute_approval(proposal(), Decision.NO, broker, NOW, "c1") is ExecutionStatus.REJECTED
    assert broker.get_positions() == {}


def test_expired_proposal_is_not_executed():
    broker = PaperBroker(20_000.0, lambda s: 100.0)
    expired = proposal(expires_at=NOW)
    assert execute_approval(expired, Decision.YES, broker, NOW, "c1") is ExecutionStatus.EXPIRED
    assert broker.get_positions() == {}
