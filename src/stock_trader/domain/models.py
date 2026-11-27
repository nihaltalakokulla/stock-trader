from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


@dataclass(frozen=True)
class StockSnapshot:
    symbol: str
    price: float
    avg_dollar_volume: float
    sma_long: float
    days_to_earnings: int

    @property
    def close_below_sma(self) -> bool:
        return self.price < self.sma_long


@dataclass(frozen=True)
class Headline:
    title: str
    published_at: datetime


@dataclass(frozen=True)
class NewsFeatures:
    sentiment: float
    headline_count: int
    shock: bool


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(StrEnum):
    FILLED = "FILLED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class Order:
    id: str
    symbol: str
    side: Side
    qty: int
    fill_price: float
    status: OrderStatus
    client_id: str | None = None


@dataclass(frozen=True)
class Account:
    cash: float
    equity: float
