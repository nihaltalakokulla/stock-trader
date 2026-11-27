from dataclasses import dataclass


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
