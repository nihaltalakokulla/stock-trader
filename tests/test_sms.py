from datetime import UTC, datetime

from stock_trader.domain.proposals import Proposal
from stock_trader.notifications.sms import compose_proposal_message

NOW = datetime(2026, 11, 27, 22, 0, tzinfo=UTC)


def proposal():
    return Proposal(
        id="p1", symbol="AAPL", qty=40, entry_price=100.0, stop_price=95.0,
        confidence=0.72, rationale="Above trend; positive news",
        created_at=NOW, expires_at=datetime(2026, 11, 30, 14, 30, tzinfo=UTC),
    )


def test_proposal_message_contains_action_and_levels():
    message = compose_proposal_message(proposal())
    assert "BUY 40 AAPL" in message
    assert "Entry 100.00" in message
    assert "Stop 95.00" in message
    assert "Reply YES to approve" in message
    assert "p1" in message
