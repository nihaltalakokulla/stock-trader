from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)


def next_market_open(now: datetime) -> datetime:
    local = now.astimezone(ET)
    day = local.date()
    while day.weekday() >= 5:
        day += timedelta(days=1)
    candidate = datetime.combine(day, MARKET_OPEN, tzinfo=ET)
    if local < candidate:
        return candidate
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return datetime.combine(day, MARKET_OPEN, tzinfo=ET)
