from dataclasses import dataclass

from stock_trader.config import Settings


@dataclass(frozen=True)
class Candidate:
    symbol: str
    probability: float
    rationale: str


def rank_candidates(
    scored: dict[str, dict], settings: Settings
) -> list[Candidate]:
    candidates = [
        Candidate(
            symbol=symbol,
            probability=float(data["probability"]),
            rationale=str(data.get("rationale", "")),
        )
        for symbol, data in scored.items()
        if float(data["probability"]) >= settings.confidence_threshold
    ]
    return sorted(candidates, key=lambda c: c.probability, reverse=True)
