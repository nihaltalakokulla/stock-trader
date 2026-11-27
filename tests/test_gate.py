from stock_trader.config import Settings
from stock_trader.gate import GateContext, confidence_gate


def ctx(**overrides):
    base = dict(probability=0.70, holding=False, open_positions=1, pending_proposals=0)
    base.update(overrides)
    return GateContext(**base)


def test_strong_unheld_candidate_passes():
    assert confidence_gate(ctx(), Settings()) is True


def test_low_confidence_is_blocked():
    assert confidence_gate(ctx(probability=0.64), Settings()) is False


def test_already_held_ticker_is_blocked():
    assert confidence_gate(ctx(holding=True), Settings()) is False


def test_full_book_is_blocked():
    assert confidence_gate(ctx(open_positions=5), Settings()) is False


def test_pending_proposal_blocks_a_second_pick():
    assert confidence_gate(ctx(pending_proposals=1), Settings()) is False
