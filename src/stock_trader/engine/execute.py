from enum import StrEnum

from stock_trader.domain.approvals import Decision
from stock_trader.domain.models import Side
from stock_trader.domain.proposals import Proposal


class ExecutionStatus(StrEnum):
    FILLED = "FILLED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"


def execute_approval(
    proposal: Proposal,
    decision: Decision,
    broker,
    now,
    client_id: str,
) -> ExecutionStatus:
    if decision is not Decision.YES:
        return ExecutionStatus.REJECTED
    if proposal.is_expired(now):
        return ExecutionStatus.EXPIRED
    fills_before = len(getattr(broker, "_fills", []))
    broker.submit_order(
        proposal.symbol, Side.BUY, proposal.qty, client_id=client_id
    )
    fills_after = len(getattr(broker, "_fills", []))
    return (
        ExecutionStatus.FILLED
        if fills_after > fills_before
        else ExecutionStatus.DUPLICATE
    )
