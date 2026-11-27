import numpy as np
import pandas as pd
import pytest

from stock_trader.features import price_features


def make_prices(values):
    return pd.Series(values, dtype=float)


def test_flat_prices_have_zero_momentum_and_volatility():
    prices = make_prices([100.0] * 70)
    volumes = make_prices([1_000_000.0] * 70)
    features = price_features(prices, volumes)
    assert features["momentum_21"] == 0.0
    assert features["volatility_21"] == 0.0
    assert features["drawdown_63"] == 0.0


def test_momentum_uses_21_session_lookback():
    prices = make_prices([100.0] * 50 + [110.0] * 21)
    volumes = make_prices([1_000_000.0] * 71)
    features = price_features(prices, volumes)
    # prices[-1]/prices[-22] - 1 = 110/100 - 1
    assert features["momentum_21"] == pytest.approx(0.10)


def test_volume_trend_compares_recent_to_21_session_average():
    prices = make_prices([100.0] * 70)
    volumes = make_prices([1_000_000.0] * 65 + [2_000_000.0] * 5)
    features = price_features(prices, volumes)
    expected = 2_000_000.0 / np.mean(
        [1_000_000.0] * 16 + [2_000_000.0] * 5
    ) - 1.0
    assert features["volume_trend"] == pytest.approx(expected)


def test_short_history_rejected():
    with pytest.raises(ValueError):
        price_features(make_prices([100.0] * 10), make_prices([1.0] * 10))
