from dataclasses import dataclass

from stock_trader.config import Settings


@dataclass(frozen=True)
class GateContext:
    probability: float
    holding: bool
    open_positions: int
    pending_proposals: int


def confidence_gate(context: GateContext, settings: Settings) -> bool:
    return (
        context.probability >= settings.confidence_threshold
        and not context.holding
        and context.open_positions < settings.max_positions
        and context.pending_proposals == 0
    )
