from datetime import UTC, datetime

from stock_trader.domain.proposals import Proposal

NOW = datetime(2026, 11, 27, 22, 0, tzinfo=UTC)


def proposal():
    return Proposal(
        id="p1", symbol="AAPL", qty=40, entry_price=100.0, stop_price=95.0,
        confidence=0.72, rationale="Above trend; positive news",
        created_at=NOW, expires_at=datetime(2026, 11, 30, 14, 30, tzinfo=UTC),
    )


def test_proposal_expires_at_or_after_open():
    assert proposal().is_expired(datetime(2026, 11, 30, 14, 30, tzinfo=UTC)) is True
    assert proposal().is_expired(datetime(2026, 11, 30, 14, 29, tzinfo=UTC)) is False
