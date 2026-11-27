from stock_trader.config import Settings
from stock_trader.domain.models import StockSnapshot


def passes_screener(snapshot: StockSnapshot, settings: Settings) -> bool:
    if snapshot.price < settings.min_price:
        return False
    if snapshot.avg_dollar_volume < settings.min_avg_dollar_volume:
        return False
    if snapshot.close_below_sma:
        return False
    if snapshot.days_to_earnings <= settings.earnings_blackout_days:
        return False
    return True
