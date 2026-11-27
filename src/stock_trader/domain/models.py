from dataclasses import dataclass
from datetime import datetime


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
