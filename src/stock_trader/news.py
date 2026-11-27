import re
from collections.abc import Sequence
from datetime import datetime, timedelta

from stock_trader.domain.models import Headline, NewsFeatures

POSITIVE = frozenset(
    "beat beats upgrade upgraded growth grows record surge surges rally "
    "outperform raise raises profit wins approval".split()
)
NEGATIVE = frozenset(
    "miss misses downgrade downgraded lawsuit probe plunge plunges fall "
    "falls cut cuts fraud recall layoffs warning".split()
)


def score_sentiment(text: str) -> float:
    words = re.findall(r"[a-z]+", text.casefold())
    positives = sum(word in POSITIVE for word in words)
    negatives = sum(word in NEGATIVE for word in words)
    total = positives + negatives
    return 0.0 if total == 0 else (positives - negatives) / total


def build_news_features(
    headlines: Sequence[Headline],
    *,
    as_of: datetime,
    window_days: int = 7,
    price_change_pct: float = 0.0,
    shock_price_pct: float = 0.05,
    shock_min_headlines: int = 3,
) -> NewsFeatures:
    cutoff = as_of - timedelta(days=window_days)
    usable = [h for h in headlines if cutoff <= h.published_at < as_of]
    if not usable:
        return NewsFeatures(sentiment=0.0, headline_count=0, shock=False)
    sentiment = sum(score_sentiment(h.title) for h in usable) / len(usable)
    shock = (
        len(usable) >= shock_min_headlines
        and abs(price_change_pct) >= shock_price_pct
    )
    return NewsFeatures(
        sentiment=sentiment, headline_count=len(usable), shock=shock
    )
