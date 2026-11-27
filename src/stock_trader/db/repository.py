from typing import Any, Protocol

from stock_trader.domain.state import TradeState


class Repository(Protocol):
    def save_proposal(self, proposal_id: str, data: dict[str, Any]) -> None: ...

    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None: ...

    def save_approval(self, key: str, data: dict[str, Any]) -> None: ...

    def get_approval(self, key: str) -> dict[str, Any] | None: ...

    def set_trade_state(self, trade_id: str, state: TradeState) -> None: ...

    def get_trade_state(self, trade_id: str) -> TradeState: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self._proposals: dict[str, dict[str, Any]] = {}
        self._approvals: dict[str, dict[str, Any]] = {}
        self._states: dict[str, TradeState] = {}

    def save_proposal(self, proposal_id: str, data: dict[str, Any]) -> None:
        self._proposals[proposal_id] = data

    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        return self._proposals.get(proposal_id)

    def save_approval(self, key: str, data: dict[str, Any]) -> None:
        self._approvals.setdefault(key, data)

    def get_approval(self, key: str) -> dict[str, Any] | None:
        return self._approvals.get(key)

    def set_trade_state(self, trade_id: str, state: TradeState) -> None:
        self._states[trade_id] = state

    def get_trade_state(self, trade_id: str) -> TradeState:
        return self._states[trade_id]
