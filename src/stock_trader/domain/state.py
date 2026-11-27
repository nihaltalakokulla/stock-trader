from enum import StrEnum


class TradeState(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    FILLED = "FILLED"
    OPEN = "OPEN"
    EXIT_SUBMITTED = "EXIT_SUBMITTED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class InvalidTransition(Exception):
    pass


ALLOWED: dict[TradeState, frozenset[TradeState]] = {
    TradeState.PROPOSED: frozenset(
        {TradeState.APPROVED, TradeState.REJECTED, TradeState.EXPIRED}
    ),
    TradeState.APPROVED: frozenset(
        {TradeState.ORDER_SUBMITTED, TradeState.CANCELLED}
    ),
    TradeState.ORDER_SUBMITTED: frozenset(
        {TradeState.FILLED, TradeState.CANCELLED}
    ),
    TradeState.FILLED: frozenset({TradeState.OPEN}),
    TradeState.OPEN: frozenset({TradeState.EXIT_SUBMITTED}),
    TradeState.EXIT_SUBMITTED: frozenset(
        {TradeState.CLOSED, TradeState.OPEN}
    ),
    TradeState.CLOSED: frozenset(),
    TradeState.REJECTED: frozenset(),
    TradeState.EXPIRED: frozenset(),
    TradeState.CANCELLED: frozenset(),
}


def transition(current: TradeState, target: TradeState) -> TradeState:
    if target not in ALLOWED[current]:
        raise InvalidTransition(f"{current} -> {target} is not allowed")
    return target
