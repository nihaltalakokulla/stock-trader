import dataclasses

import pytest

from stock_trader.config import Settings


def test_settings_defaults_match_spec():
    settings = Settings()
    assert settings.paper_starting_cash == 20_000.0
    assert settings.risk_per_trade == 0.01
    assert settings.max_positions == 5
    assert settings.confidence_threshold == 0.65
    assert settings.max_hold_days == 30


def test_settings_reject_out_of_range_risk():
    with pytest.raises(ValueError):
        Settings(risk_per_trade=1.5)


def test_settings_are_immutable():
    settings = Settings()
    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.risk_per_trade = 0.02
