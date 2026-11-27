from datetime import UTC, date, datetime

import httpx

from stock_trader.domain.models import Headline

FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"


def parse_finnhub_news(payload: list[dict], symbol: str) -> list[Headline]:
    return [
        Headline(
            title=item["headline"],
            published_at=datetime.fromtimestamp(item["datetime"], tz=UTC),
        )
        for item in payload
        if item.get("headline")
    ]


def fetch_company_news(
    client: httpx.Client, symbol: str, start: date, end: date, token: str
) -> list[Headline]:
    response = client.get(
        FINNHUB_NEWS_URL,
        params={
            "symbol": symbol,
            "from": start.isoformat(),
            "to": end.isoformat(),
            "token": token,
        },
        timeout=20,
    )
    response.raise_for_status()
    return parse_finnhub_news(response.json(), symbol)
