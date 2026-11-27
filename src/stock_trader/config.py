from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    paper_starting_cash: float = 20_000.0
    risk_per_trade: float = 0.01
    max_positions: int = 5
    confidence_threshold: float = 0.65
    weekly_drawdown_limit: float = 0.05
    max_hold_days: int = 30
    min_price: float = 5.0
    min_avg_dollar_volume: float = 10_000_000.0
    earnings_blackout_days: int = 2
    stop_atr_multiple: float = 2.0
    slippage_pct: float = 0.001
    news_window_days: int = 7

    def __post_init__(self) -> None:
        if not 0 < self.risk_per_trade < 1:
            raise ValueError("risk_per_trade must be in (0, 1)")
        if not 0 < self.confidence_threshold < 1:
            raise ValueError("confidence_threshold must be in (0, 1)")
        if self.max_positions < 1:
            raise ValueError("max_positions must be >= 1")
        if self.paper_starting_cash <= 0:
            raise ValueError("paper_starting_cash must be positive")

    @property
    def risk_amount(self) -> float:
        return self.paper_starting_cash * self.risk_per_trade
