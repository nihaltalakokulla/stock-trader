from typing import Protocol

from stock_trader.domain.models import Account, Order, Side


class Broker(Protocol):
    def get_quote(self, symbol: str) -> float: ...

    def submit_order(
        self,
        symbol: str,
        side: Side,
        qty: int,
        order_type: str = "market",
        client_id: str | None = None,
    ) -> Order: ...

    def cancel_order(self, order_id: str) -> None: ...

    def get_positions(self) -> dict[str, int]: ...

    def get_account(self) -> Account: ...
