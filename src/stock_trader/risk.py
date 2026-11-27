import math


def risk_amount(equity: float, risk_pct: float) -> float:
    if equity <= 0:
        raise ValueError("equity must be positive")
    if not 0 < risk_pct < 1:
        raise ValueError("risk_pct must be in (0, 1)")
    return equity * risk_pct


def position_size(equity: float, entry: float, stop: float, risk_pct: float) -> int:
    if entry <= 0:
        raise ValueError("entry must be positive")
    if stop <= 0 or stop >= entry:
        raise ValueError("stop must be positive and below entry")
    shares = math.floor(risk_amount(equity, risk_pct) / (entry - stop))
    if shares < 1:
        raise ValueError("stop distance too wide for account size")
    return shares
