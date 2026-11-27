from datetime import UTC, datetime

import httpx
import pandas as pd
import pytest

from stock_trader.data.news import fetch_company_news, parse_finnhub_news
from stock_trader.data.prices import (
    fetch_yahoo_frame,
    fetch_yfinance_frame,
    load_price_history,
)


def test_price_loader_keys_symbols_and_skips_empty():
    def fetch(symbol):
        return pd.DataFrame() if symbol == "BAD" else pd.DataFrame({"Close": [1.0]})

    frames = load_price_history(fetch, ["AAPL", "BAD"])
    assert list(frames) == ["AAPL"]


def test_finnhub_payload_parsing_keeps_full_structure():
    payload = [{
        "headline": "AAPL beats estimates",
        "datetime": 1_765_000_000,
        "source": "wire",
        "url": "https://example.com/x",
    }]
    headlines = parse_finnhub_news(payload, "AAPL")
    assert headlines[0].title == "AAPL beats estimates"
    assert headlines[0].published_at == datetime.fromtimestamp(1_765_000_000, tz=UTC)


def test_finnhub_fetcher_sends_expected_query():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json=[{
            "headline": "AAPL upgrade", "datetime": 1_765_000_000,
            "source": "wire", "url": "",
        }])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    headlines = fetch_company_news(
        client, "AAPL", datetime(2026, 11, 20).date(),
        datetime(2026, 11, 27).date(), "token123",
    )
    assert "symbol=AAPL" in seen["url"]
    assert "token=token123" in seen["url"]
    assert headlines[0].title == "AAPL upgrade"


def test_yahoo_chart_payload_becomes_adjusted_ohlcv():
    payload = {
        "chart": {
            "result": [{
                "timestamp": [1_790_000_000, 1_790_086_400],
                "indicators": {
                    "quote": [{
                        "open": [100.0, 101.0],
                        "high": [102.0, 103.0],
                        "low": [99.0, 100.0],
                        "close": [101.0, 102.0],
                        "volume": [1000, 2000],
                    }],
                    "adjclose": [{"adjclose": [50.5, 51.0]}],
                },
            }],
            "error": None,
        }
    }

    def handler(request):
        assert "range=1y" in str(request.url)
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    frame = fetch_yahoo_frame("AAPL", "1y", client=client)
    assert list(frame.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert frame["Close"].iloc[0] == 50.5
    assert frame["High"].iloc[0] == pytest.approx(51.0)
    assert frame["Volume"].iloc[1] == 2000


def test_yfinance_uses_timeout_and_adjusts(monkeypatch):
    seen = {}

    def fake_download(symbol, **kwargs):
        seen.update(kwargs)
        return pd.DataFrame({
            "Open": [99.0], "High": [101.0], "Low": [98.0],
            "Close": [100.0], "Volume": [1000.0],
        })

    monkeypatch.setattr("yfinance.download", fake_download)
    frame = fetch_yfinance_frame("AAPL", "1y")
    assert seen["timeout"] == 10
    assert seen["auto_adjust"] is True
    assert frame["Close"].iloc[0] == 100.0


def test_yfinance_falls_back_to_yahoo(monkeypatch):
    fallback = pd.DataFrame({"Close": [123.0]})

    def boom(*args, **kwargs):
        raise RuntimeError("blocked")

    monkeypatch.setattr("yfinance.download", boom)
    monkeypatch.setattr(
        "stock_trader.data.prices.fetch_yahoo_frame",
        lambda symbol, period: fallback,
    )
    assert fetch_yfinance_frame("AAPL", "5y") is fallback
