from stock_trader.config import Settings
from stock_trader.engine.signals import rank_candidates


def test_rank_candidates_filters_and_sorts_by_probability():
    settings = Settings(confidence_threshold=0.6)
    scored = {
        "AAPL": {"probability": 0.75, "rationale": "trend"},
        "MSFT": {"probability": 0.55, "rationale": "trend"},
        "NVDA": {"probability": 0.90, "rationale": "news"},
    }
    ranked = rank_candidates(scored, settings)
    assert [c.symbol for c in ranked] == ["NVDA", "AAPL"]
    assert ranked[0].rationale == "news"
