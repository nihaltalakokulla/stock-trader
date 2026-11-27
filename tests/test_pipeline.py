import numpy as np
import pandas as pd

from stock_trader.domain.models import NewsFeatures
from stock_trader.pipeline import build_feature_row, build_snapshot, build_training_panel


def frame(rows=250, start=100.0, step=0.1, volume=2_000_000.0):
    closes = start + np.arange(rows) * step
    return pd.DataFrame({
        "Close": closes,
        "Volume": np.full(rows, volume, dtype=float),
    })


def test_snapshot_uses_latest_price_and_liquidity():
    snapshot = build_snapshot("AAPL", frame())
    latest = 100.0 + 249 * 0.1
    assert snapshot.symbol == "AAPL"
    assert snapshot.price == latest
    assert snapshot.avg_dollar_volume > 20_000_000.0
    assert snapshot.sma_long < latest
    assert snapshot.days_to_earnings == 999


def test_feature_row_merges_price_and_news_features():
    data = frame()
    news = NewsFeatures(sentiment=0.5, headline_count=4, shock=True)
    row = build_feature_row(data, news, benchmark=frame(start=100.0, step=0.05))
    assert set(row) == {
        "momentum_21",
        "volatility_21",
        "volume_trend",
        "drawdown_63",
        "relative_strength_63",
        "news_sentiment",
        "news_count",
        "news_shock",
    }
    assert row["news_sentiment"] == 0.5
    assert row["news_shock"] == 1.0


def test_training_panel_labels_forward_returns():
    rising = frame(rows=600, start=100.0, step=0.2)
    falling = frame(rows=600, start=200.0, step=-0.15)
    panel = build_training_panel(
        {"UP": rising, "DOWN": falling},
        benchmark=None,
        forward_days=21,
        step=21,
    )
    assert len(panel) > 20
    assert set(panel["symbol"]) == {"UP", "DOWN"}
    up_labels = panel.loc[panel["symbol"] == "UP", "label"]
    down_labels = panel.loc[panel["symbol"] == "DOWN", "label"]
    assert up_labels.mean() > 0.9
    assert down_labels.mean() < 0.1
