from datetime import UTC, datetime

import numpy as np
import pandas as pd

from stock_trader.config import Settings
from stock_trader.db.repository import InMemoryRepository
from stock_trader.model import FEATURE_COLUMNS, train_ranker
from stock_trader.runtime import Runtime


def rising_frame(rows=320):
    closes = 100.0 + np.arange(rows) * 0.25
    return pd.DataFrame({
        "Close": closes,
        "Volume": np.full(rows, 5_000_000.0),
        "High": closes + 1.0,
        "Low": closes - 1.0,
    })


def test_nightly_dry_run_creates_proposal_and_prints_text(tmp_path):
    rng = np.random.default_rng(3)
    rows = 120
    features = pd.DataFrame({
        "momentum_21": rng.uniform(-0.1, 0.2, rows),
        "volatility_21": rng.uniform(0.1, 0.6, rows),
        "volume_trend": rng.uniform(-0.2, 0.2, rows),
        "drawdown_63": rng.uniform(-0.2, 0.0, rows),
        "relative_strength_63": rng.uniform(-0.1, 0.1, rows),
        "news_sentiment": rng.uniform(-1.0, 1.0, rows),
        "news_count": rng.integers(0, 5, rows).astype(float),
        "news_shock": rng.integers(0, 2, rows).astype(float),
    })
    labels = (features["momentum_21"] > 0).astype(int)
    model_path = tmp_path / "ranker.joblib"
    train_ranker(features.loc[:, list(FEATURE_COLUMNS)], labels).save(model_path)

    data = rising_frame()
    outputs: list[str] = []
    repo = InMemoryRepository()
    runtime = Runtime(
        settings=Settings(confidence_threshold=0.01),
        repo=repo,
        model_path=model_path,
        fetcher=lambda symbol: data,
        now=lambda: datetime(2026, 11, 27, 23, 0, tzinfo=UTC),
        output=outputs.append,
    )

    runtime.nightly(dry_run=True)

    assert repo.pending_proposal_count() == 1
    assert any("Reply YES to approve" in text for text in outputs)
