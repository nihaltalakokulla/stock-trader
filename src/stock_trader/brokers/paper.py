from collections.abc import Callable

from stock_trader.domain.models import Account, Order, OrderStatus, Side


class InsufficientFunds(Exception):
    pass


class PaperBroker:
    def __init__(
        self,
        starting_cash: float,
        quote_provider: Callable[[str], float],
        slippage_pct: float = 0.001,
        positions: dict[str, int] | None = None,
    ) -> None:
        self._cash = starting_cash
        self._quotes = quote_provider
        self._slippage = slippage_pct
        self._positions: dict[str, int] = dict(positions or {})
        self._fills: list[Order] = []
        self._by_client_id: dict[str, Order] = {}

    def get_quote(self, symbol: str) -> float:
        return float(self._quotes(symbol))

    def submit_order(
        self,
        symbol: str,
        side: Side,
        qty: int,
        order_type: str = "market",
        client_id: str | None = None,
    ) -> Order:
        if client_id and client_id in self._by_client_id:
            return self._by_client_id[client_id]
        if qty <= 0:
            raise ValueError("qty must be positive")
        quote = self.get_quote(symbol)
        if side is Side.BUY:
            price = quote * (1 + self._slippage)
            cost = price * qty
            if cost > self._cash:
                raise InsufficientFunds(
                    f"need {cost:.2f}, have {self._cash:.2f}"
                )
            self._cash -= cost
            self._positions[symbol] = self._positions.get(symbol, 0) + qty
        else:
            held = self._positions.get(symbol, 0)
            if qty > held:
                raise ValueError(f"cannot sell {qty} {symbol}, holding {held}")
            price = quote * (1 - self._slippage)
            self._cash += price * qty
            self._positions[symbol] = held - qty
        order = Order(
            id=f"paper-{len(self._fills) + 1}",
            symbol=symbol,
            side=side,
            qty=qty,
            fill_price=price,
            status=OrderStatus.FILLED,
            client_id=client_id,
        )
        self._fills.append(order)
        if client_id:
            self._by_client_id[client_id] = order
        return order

    def cancel_order(self, order_id: str) -> None:
        return None

    def get_positions(self) -> dict[str, int]:
        return {symbol: qty for symbol, qty in self._positions.items() if qty > 0}

    def get_account(self) -> Account:
        equity = self._cash + sum(
            qty * self.get_quote(symbol)
            for symbol, qty in self._positions.items()
        )
        return Account(cash=self._cash, equity=equity)
