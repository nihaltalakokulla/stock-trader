from collections.abc import Callable, Sequence

import httpx
import pandas as pd

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"


def load_price_history(
    fetch: Callable[[str], pd.DataFrame], symbols: Sequence[str]
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        frame = fetch(symbol)
        if frame is not None and not frame.empty:
            frames[symbol] = frame
    return frames


def fetch_yahoo_frame(
    symbol: str,
    range_: str = "2y",
    *,
    client: httpx.Client | None = None,
) -> pd.DataFrame:
    owns_client = client is None
    client = client or httpx.Client(
        timeout=20, headers={"User-Agent": "Mozilla/5.0"}
    )
    try:
        response = client.get(
            f"{YAHOO_CHART_URL}/{symbol}",
            params={"range": range_, "interval": "1d"},
        )
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            client.close()
    result = payload["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    adjusted = result["indicators"].get("adjclose", [{}])[0].get("adjclose")
    index = pd.to_datetime(result["timestamp"], unit="s", utc=True)
    index = index.tz_convert("America/New_York").normalize().tz_localize(None)
    close = pd.Series(quote["close"], index=index, dtype=float)
    raw_close = close.copy()
    if adjusted is not None:
        close = pd.Series(adjusted, index=index, dtype=float)
    factor = close / raw_close
    frame = pd.DataFrame(
        {
            "Open": pd.Series(quote["open"], index=index, dtype=float) * factor,
            "High": pd.Series(quote["high"], index=index, dtype=float) * factor,
            "Low": pd.Series(quote["low"], index=index, dtype=float) * factor,
            "Close": close,
            "Volume": pd.Series(quote["volume"], index=index, dtype=float),
        }
    )
    return frame.dropna()


def fetch_yfinance_frame(symbol: str, period: str = "2y") -> pd.DataFrame:
    return fetch_yahoo_frame(symbol, period)
