import pytest

from stock_trader.domain.approvals import Decision, parse_reply


@pytest.mark.parametrize("text,expected", [
    ("YES", Decision.YES),
    ("  yes ", Decision.YES),
    ("No", Decision.NO),
    ("stop", Decision.STOP),
    ("maybe", Decision.UNKNOWN),
    ("", Decision.UNKNOWN),
])
def test_parse_reply(text, expected):
    assert parse_reply(text) is expected
