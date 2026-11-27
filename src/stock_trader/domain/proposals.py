from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Proposal:
    id: str
    symbol: str
    qty: int
    entry_price: float
    stop_price: float
    confidence: float
    rationale: str
    created_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at
