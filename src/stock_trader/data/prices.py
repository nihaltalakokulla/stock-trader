from collections.abc import Callable, Sequence

import pandas as pd


def load_price_history(
    fetch: Callable[[str], pd.DataFrame], symbols: Sequence[str]
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        frame = fetch(symbol)
        if frame is not None and not frame.empty:
            frames[symbol] = frame
    return frames


def fetch_yfinance_frame(symbol: str, period: str = "2y") -> pd.DataFrame:
    import yfinance as yf

    frame = yf.download(
        symbol,
        period=period,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    return frame.dropna()
