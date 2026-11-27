from stock_trader.domain.proposals import Proposal


def compose_proposal_message(proposal: Proposal) -> str:
    return (
        f"SWING PICK {proposal.symbol}\n"
        f"BUY {proposal.qty} {proposal.symbol} | "
        f"Entry {proposal.entry_price:.2f} | Stop {proposal.stop_price:.2f}\n"
        f"Confidence {proposal.confidence:.0%} | {proposal.rationale}\n"
        f"Reply YES to approve, NO to skip. ID {proposal.id}"
    )
