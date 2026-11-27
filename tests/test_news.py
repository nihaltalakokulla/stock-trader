from datetime import UTC, datetime, timedelta

from stock_trader.domain.models import Headline
from stock_trader.news import build_news_features, score_sentiment

NOW = datetime(2026, 11, 27, 22, 0, tzinfo=UTC)


def test_positive_headline_scores_positive():
    assert score_sentiment("Company beats estimates and raises guidance") == 1.0


def test_mixed_headline_nets_to_zero():
    assert score_sentiment("Beat expectations but shares plunge") == 0.0


def test_only_headlines_before_as_of_and_inside_window_count():
    headlines = [
        Headline("stock surges on upgrade", NOW - timedelta(days=1)),
        Headline("stock surges on upgrade", NOW - timedelta(days=8)),
        Headline("stock surges on upgrade", NOW + timedelta(hours=1)),
    ]
    features = build_news_features(headlines, as_of=NOW, window_days=7)
    assert features.headline_count == 1
    assert features.sentiment == 1.0


def test_news_shock_needs_both_price_move_and_headline_volume():
    headlines = [Headline("stock surges", NOW - timedelta(hours=i)) for i in range(1, 4)]
    assert build_news_features(headlines, as_of=NOW, price_change_pct=0.06).shock is True
    assert build_news_features(headlines, as_of=NOW, price_change_pct=0.02).shock is False
