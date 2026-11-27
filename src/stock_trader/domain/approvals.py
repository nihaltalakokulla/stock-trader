from enum import StrEnum


class Decision(StrEnum):
    YES = "YES"
    NO = "NO"
    STOP = "STOP"
    UNKNOWN = "UNKNOWN"


_BY_TEXT = {
    "yes": Decision.YES,
    "no": Decision.NO,
    "stop": Decision.STOP,
}


def parse_reply(text: str) -> Decision:
    return _BY_TEXT.get(text.strip().casefold(), Decision.UNKNOWN)
