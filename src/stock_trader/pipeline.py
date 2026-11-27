import pandas as pd

from stock_trader.domain.models import NewsFeatures, StockSnapshot
from stock_trader.features import price_features


def _require_columns(frame: pd.DataFrame) -> None:
    missing = [column for column in ("Close", "Volume") if column not in frame.columns]
    if missing:
        raise ValueError(f"frame missing columns: {missing}")
    if len(frame) < 22:
        raise ValueError("need at least 22 rows of price history")


def build_snapshot(
    symbol: str,
    frame: pd.DataFrame,
    *,
    days_to_earnings: int = 999,
) -> StockSnapshot:
    _require_columns(frame)
    closes = frame["Close"].astype(float)
    volumes = frame["Volume"].astype(float)
    price = float(closes.iloc[-1])
    dollar_volume = float((closes.iloc[-21:] * volumes.iloc[-21:]).mean())
    sma_long = float(closes.iloc[-min(200, len(closes)):].mean())
    return StockSnapshot(
        symbol=symbol,
        price=price,
        avg_dollar_volume=dollar_volume,
        sma_long=sma_long,
        days_to_earnings=days_to_earnings,
    )


def build_feature_row(
    frame: pd.DataFrame,
    news: NewsFeatures,
    *,
    benchmark: pd.DataFrame | None = None,
) -> dict[str, float]:
    _require_columns(frame)
    benchmark_close = None
    if benchmark is not None:
        _require_columns(benchmark)
        benchmark_close = benchmark["Close"].astype(float)
    row = price_features(
        frame["Close"].astype(float),
        frame["Volume"].astype(float),
        benchmark_close,
    )
    row.setdefault("relative_strength_63", 0.0)
    row["news_sentiment"] = float(news.sentiment)
    row["news_count"] = float(news.headline_count)
    row["news_shock"] = 1.0 if news.shock else 0.0
    return row


def build_training_panel(
    frames: dict[str, pd.DataFrame],
    *,
    benchmark: pd.DataFrame | None = None,
    forward_days: int = 21,
    step: int = 21,
    min_history: int = 220,
) -> pd.DataFrame:
    rows: list[dict[str, float | str | int]] = []
    empty_news = NewsFeatures(sentiment=0.0, headline_count=0, shock=False)
    for symbol, frame in frames.items():
        _require_columns(frame)
        if len(frame) <= min_history + forward_days:
            continue
        closes = frame["Close"].astype(float)
        for end in range(min_history, len(frame) - forward_days, step):
            history = frame.iloc[: end + 1]
            row = build_feature_row(history, empty_news, benchmark=benchmark)
            forward_return = float(
                closes.iloc[end + forward_days] / closes.iloc[end] - 1.0
            )
            row["symbol"] = symbol
            row["label"] = int(forward_return > 0)
            row["forward_return"] = forward_return
            rows.append(row)
    return pd.DataFrame(rows)


def atr(frame: pd.DataFrame, period: int = 14) -> float:
    _require_columns(frame)
    close = frame["Close"].astype(float)
    high = frame["High"].astype(float) if "High" in frame else close
    low = frame["Low"].astype(float) if "Low" in frame else close
    previous = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous).abs(), (low - previous).abs()],
        axis=1,
    ).max(axis=1)
    return float(true_range.iloc[-period:].mean())
