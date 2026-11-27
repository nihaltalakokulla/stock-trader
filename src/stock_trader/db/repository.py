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
        self._signals: list[dict[str, Any]] = []
        self._settings: dict[str, Any] = {}
        self._positions: dict[str, dict[str, Any]] = {}

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

    def insert_signal(self, data: dict[str, Any]) -> dict[str, Any]:
        self._signals.append(data)
        return data

    def insert_proposal(self, proposal) -> dict[str, Any]:
        data = {
            "id": proposal.id,
            "symbol": proposal.symbol,
            "qty": proposal.qty,
            "entry_price": proposal.entry_price,
            "stop_price": proposal.stop_price,
            "confidence": proposal.confidence,
            "rationale": proposal.rationale,
            "expires_at": proposal.expires_at,
            "state": TradeState.PROPOSED.value,
        }
        self._proposals[proposal.id] = data
        self._states[proposal.id] = TradeState.PROPOSED
        return data

    def pending_proposal_count(self) -> int:
        return sum(
            data.get("state") == TradeState.PROPOSED.value
            for data in self._proposals.values()
        )

    def open_position_symbols(self) -> set[str]:
        return set(self._positions)

    def open_positions(self) -> list[dict[str, Any]]:
        return list(self._positions.values())

    def get_setting(self, key: str) -> Any:
        return self._settings.get(key)

    def set_setting(self, key: str, value: Any) -> None:
        self._settings[key] = value

    def insert_order(self, data: dict[str, Any]) -> dict[str, Any]:
        return data

    def upsert_position(self, data: dict[str, Any]) -> dict[str, Any]:
        self._positions[data["symbol"]] = data
        return data

    def remove_position(self, symbol: str) -> None:
        self._positions.pop(symbol, None)
