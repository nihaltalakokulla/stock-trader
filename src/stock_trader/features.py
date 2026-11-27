import numpy as np
import pandas as pd


def _return_over(prices: pd.Series, sessions: int) -> float:
    return float(prices.iloc[-1] / prices.iloc[-1 - sessions] - 1.0)


def price_features(
    prices: pd.Series,
    volumes: pd.Series,
    benchmark: pd.Series | None = None,
) -> dict[str, float]:
    if len(prices) < 22 or len(volumes) != len(prices):
        raise ValueError("need at least 22 aligned price/volume observations")
    returns = prices.pct_change().dropna()
    drawdown_window = min(63, len(prices))
    recent_volume = volumes.iloc[-5:].mean()
    trailing_volume = volumes.iloc[-21:].mean()
    features = {
        "momentum_21": _return_over(prices, 21),
        "volatility_21": float(returns.iloc[-21:].std(ddof=0) * np.sqrt(252)),
        "volume_trend": float(recent_volume / trailing_volume - 1.0),
        "drawdown_63": float(
            prices.iloc[-1] / prices.iloc[-drawdown_window:].max() - 1.0
        ),
    }
    if benchmark is not None:
        if len(benchmark) != len(prices):
            raise ValueError("benchmark must align with prices")
        sessions = min(63, len(prices) - 1)
        features["relative_strength_63"] = (
            _return_over(prices, sessions) - _return_over(benchmark, sessions)
        )
    return features
