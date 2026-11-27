from datetime import datetime
from zoneinfo import ZoneInfo

from stock_trader.market import next_market_open

ET = ZoneInfo("America/New_York")


def test_after_close_on_friday_expires_monday_open():
    friday_night = datetime(2026, 11, 27, 18, 0, tzinfo=ET)
    assert next_market_open(friday_night) == datetime(
        2026, 11, 30, 9, 30, tzinfo=ET
    )


def test_weekend_expires_monday_open():
    saturday = datetime(2026, 11, 28, 10, 0, tzinfo=ET)
    assert next_market_open(saturday) == datetime(
        2026, 11, 30, 9, 30, tzinfo=ET
    )


def test_before_open_stays_same_day():
    tuesday_morning = datetime(2026, 12, 1, 8, 0, tzinfo=ET)
    assert next_market_open(tuesday_morning) == datetime(
        2026, 12, 1, 9, 30, tzinfo=ET
    )


def test_during_market_expires_next_session_open():
    tuesday_midday = datetime(2026, 12, 1, 12, 0, tzinfo=ET)
    assert next_market_open(tuesday_midday) == datetime(
        2026, 12, 2, 9, 30, tzinfo=ET
    )
