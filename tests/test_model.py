import numpy as np
import pandas as pd
import pytest

from stock_trader.model import FEATURE_COLUMNS, RankingModel, train_ranker


def make_features(rows=160, seed=7):
    rng = np.random.default_rng(seed)
    momentum = rng.uniform(-0.1, 0.2, rows)
    return pd.DataFrame({
        "momentum_21": momentum,
        "volatility_21": rng.uniform(0.1, 0.6, rows),
        "volume_trend": rng.uniform(-0.3, 0.3, rows),
        "drawdown_63": rng.uniform(-0.3, 0.0, rows),
        "relative_strength_63": rng.uniform(-0.2, 0.2, rows),
        "news_sentiment": rng.uniform(-1.0, 1.0, rows),
        "news_count": rng.integers(0, 8, rows).astype(float),
        "news_shock": rng.integers(0, 2, rows).astype(float),
    })


def test_feature_columns_are_fixed():
    assert FEATURE_COLUMNS == (
        "momentum_21",
        "volatility_21",
        "volume_trend",
        "drawdown_63",
        "relative_strength_63",
        "news_sentiment",
        "news_count",
        "news_shock",
    )


def test_ranker_learns_momentum_signal():
    features = make_features()
    labels = (features["momentum_21"] > 0).astype(int)
    model = train_ranker(features, labels)
    test = features.iloc[[0]].copy()
    test.loc[:, "momentum_21"] = -0.5
    low = model.predict_proba(test)[0]
    test.loc[:, "momentum_21"] = 0.5
    high = model.predict_proba(test)[0]
    assert high > low
    assert high > 0.5


def test_model_round_trips_through_disk(tmp_path):
    features = make_features()
    labels = (features["momentum_21"] > 0).astype(int)
    model = train_ranker(features, labels)
    path = tmp_path / "ranker.joblib"
    model.save(path)
    loaded = RankingModel.load(path)
    np.testing.assert_allclose(
        model.predict_proba(features.iloc[:20]),
        loaded.predict_proba(features.iloc[:20]),
    )


def test_prediction_rejects_missing_features():
    features = make_features()
    labels = (features["momentum_21"] > 0).astype(int)
    model = train_ranker(features, labels)
    with pytest.raises(ValueError, match="missing features"):
        model.predict_proba(features.drop(columns=["news_shock"]))
