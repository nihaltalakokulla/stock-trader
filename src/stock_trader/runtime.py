import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pandas as pd

from stock_trader.brokers.paper import PaperBroker
from stock_trader.config import Settings
from stock_trader.data.news import fetch_company_news
from stock_trader.data.prices import fetch_yfinance_frame, load_price_history
from stock_trader.db.repository import InMemoryRepository
from stock_trader.domain.approvals import Decision
from stock_trader.domain.models import Headline, Side
from stock_trader.domain.proposals import Proposal
from stock_trader.domain.state import TradeState
from stock_trader.engine.execute import execute_approval
from stock_trader.engine.signals import rank_candidates
from stock_trader.market import next_market_open
from stock_trader.model import FEATURE_COLUMNS, RankingModel, train_ranker
from stock_trader.news import build_news_features
from stock_trader.notifications.sms import compose_proposal_message
from stock_trader.notifications.twilio import TwilioSender
from stock_trader.pipeline import atr, build_feature_row, build_snapshot, build_training_panel
from stock_trader.risk import position_size
from stock_trader.screener import passes_screener
from stock_trader.universe import BENCHMARK, DEFAULT_UNIVERSE

MODEL_PATH = Path("models/latest.joblib")


def _env(name: str) -> str | None:
    return os.environ.get(name)


@dataclass
class Runtime:
    settings: Settings
    repo: object
    model_path: Path = MODEL_PATH
    fetcher: Callable[[str], pd.DataFrame] = fetch_yfinance_frame
    news_fetcher: Callable[[str], list[Headline]] | None = None
    sender: TwilioSender | None = None
    now: Callable[[], datetime] = lambda: datetime.now(UTC)
    output: Callable[[str], None] = print

    def train(self) -> None:
        frames = load_price_history(self.fetcher, DEFAULT_UNIVERSE)
        if len(frames) < 5:
            raise RuntimeError("not enough price histories to train")
        panel = build_training_panel(frames, benchmark=None)
        panel = panel.dropna(subset=list(FEATURE_COLUMNS) + ["label"])
        model = train_ranker(
            panel.loc[:, list(FEATURE_COLUMNS)], panel["label"]
        )
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        model.save(self.model_path)
        self.output(
            f"trained ranker on {len(panel)} rows from {len(frames)} symbols"
        )

    def nightly(self, dry_run: bool = False) -> None:
        if not self.model_path.exists():
            raise RuntimeError("model missing; run `python -m stock_trader.cli train`")
        self.review_positions(dry_run=dry_run)
        model = RankingModel.load(self.model_path)
        frames = load_price_history(self.fetcher, DEFAULT_UNIVERSE)
        benchmark = frames.get(BENCHMARK) or self.fetcher(BENCHMARK)
        now = self.now()
        open_symbols = self.repo.open_position_symbols()
        pending = self.repo.pending_proposal_count()

        scored: dict[str, dict] = {}
        for symbol, frame in frames.items():
            if symbol == BENCHMARK:
                continue
            try:
                snapshot = build_snapshot(symbol, frame)
            except ValueError:
                continue
            if not passes_screener(snapshot, self.settings):
                continue
            headlines = self.news_fetcher(symbol) if self.news_fetcher else []
            daily_change = float(frame["Close"].pct_change().iloc[-1])
            news = build_news_features(
                headlines,
                as_of=now,
                window_days=self.settings.news_window_days,
                price_change_pct=daily_change,
            )
            feature_row = build_feature_row(frame, news, benchmark=benchmark)
            scored[symbol] = feature_row

        if not scored:
            self.output("No stocks passed the safety screener.")
            return

        matrix = pd.DataFrame.from_dict(scored, orient="index")
        probabilities = model.predict_proba(matrix)
        ranked = rank_candidates(
            {
                symbol: {
                    "probability": float(probability),
                    "rationale": (
                        f"momentum {matrix.loc[symbol, 'momentum_21']:+.1%}; "
                        f"news {matrix.loc[symbol, 'news_sentiment']:+.2f}"
                    ),
                }
                for symbol, probability in zip(matrix.index, probabilities)
            },
            self.settings,
        )
        if not ranked:
            self.output("No candidate cleared the confidence bar.")
            return
        if pending:
            self.output("A proposal is already awaiting a reply.")
            return
        if len(open_symbols) >= self.settings.max_positions:
            self.output("Position cap reached.")
            return

        candidate = next(
            (item for item in ranked if item.symbol not in open_symbols), None
        )
        if candidate is None:
            self.output("Every strong candidate is already held.")
            return

        frame = frames[candidate.symbol]
        price = float(frame["Close"].iloc[-1])
        stop = price - self.settings.stop_atr_multiple * atr(frame)
        if stop <= 0 or stop >= price:
            self.output("Volatility stop is invalid; skipping.")
            return
        equity = self._paper_equity()
        qty = position_size(
            equity, price, stop, self.settings.risk_per_trade
        )
        proposal = Proposal(
            id=uuid.uuid4().hex,
            symbol=candidate.symbol,
            qty=qty,
            entry_price=price,
            stop_price=stop,
            confidence=candidate.probability,
            rationale=candidate.rationale,
            created_at=now,
            expires_at=next_market_open(now),
        )
        self.repo.insert_signal(
            {
                "symbol": candidate.symbol,
                "probability": candidate.probability,
                "features": scored[candidate.symbol],
                "rationale": candidate.rationale,
            }
        )
        self.repo.insert_proposal(proposal)
        message = compose_proposal_message(proposal)
        if dry_run or self.sender is None:
            self.output(message)
        else:
            self.sender.send(_env("USER_PHONE") or "", message)
            self.output(f"Proposal text sent for {candidate.symbol}.")

    def execute(self, approval_key: str) -> None:
        approval = self.repo.get_approval(approval_key)
        if approval is None:
            raise RuntimeError(f"approval not found: {approval_key}")
        proposal_row = self.repo.get_proposal(approval["proposal_id"])
        if proposal_row is None:
            raise RuntimeError("proposal not found for approval")
        proposal = Proposal(
            id=proposal_row["id"],
            symbol=proposal_row["symbol"],
            qty=int(proposal_row["qty"]),
            entry_price=float(proposal_row["entry_price"]),
            stop_price=float(proposal_row["stop_price"]),
            confidence=float(proposal_row["confidence"]),
            rationale=proposal_row["rationale"],
            created_at=_parse_time(proposal_row["created_at"]),
            expires_at=_parse_time(proposal_row["expires_at"]),
        )
        quote_cache: dict[str, float] = {}

        def quote(symbol: str) -> float:
            if symbol not in quote_cache:
                quote_cache[symbol] = float(
                    self.fetcher(symbol)["Close"].iloc[-1]
                )
            return quote_cache[symbol]

        state = self.repo.get_setting("paper_account") or {
            "cash": self.settings.paper_starting_cash
        }
        broker = PaperBroker(
            float(state["cash"]), quote, self.settings.slippage_pct
        )
        status = execute_approval(
            proposal,
            Decision(approval["decision"]),
            broker,
            self.now(),
            approval_key,
        )
        self.output(str(status))
        if status.value != "FILLED":
            return
        fill = broker._fills[-1]
        account = broker.get_account()
        self.repo.set_setting(
            "paper_account",
            {"cash": account.cash, "equity": account.equity},
        )
        self.repo.insert_order(
            {
                "proposal_id": proposal.id,
                "client_id": approval_key,
                "symbol": fill.symbol,
                "side": fill.side.value,
                "qty": fill.qty,
                "fill_price": fill.fill_price,
                "status": "FILLED",
            }
        )
        self.repo.upsert_position(
            {
                "symbol": proposal.symbol,
                "proposal_id": proposal.id,
                "qty": proposal.qty,
                "avg_price": fill.fill_price,
                "stop_price": proposal.stop_price,
                "opened_at": self.now().isoformat(),
            }
        )
        self.repo.set_trade_state(proposal.id, TradeState.OPEN)
        if self.sender is not None and _env("USER_PHONE"):
            self.sender.send(
                _env("USER_PHONE") or "",
                f"FILLED: BUY {proposal.qty} {proposal.symbol} @ {fill.fill_price:.2f}",
            )

    def review_positions(self, dry_run: bool = False) -> None:
        now = self.now()
        for position in self.repo.open_positions():
            symbol = position["symbol"]
            qty = int(position["qty"])
            stop = float(position["stop_price"])
            frame = self.fetcher(symbol)
            price = float(frame["Close"].iloc[-1])
            opened_at = _parse_time(position["opened_at"])
            held_days = (now - opened_at).days
            trailing_stop = price - self.settings.stop_atr_multiple * atr(frame)

            stop_hit = price <= stop
            time_exit = held_days >= self.settings.max_hold_days
            if not (stop_hit or time_exit):
                if trailing_stop > stop:
                    updated = dict(position)
                    updated["stop_price"] = trailing_stop
                    self.repo.upsert_position(updated)
                continue

            state = self.repo.get_setting("paper_account") or {
                "cash": self.settings.paper_starting_cash
            }
            broker = PaperBroker(
                float(state["cash"]),
                lambda ticker: float(self.fetcher(ticker)["Close"].iloc[-1]),
                self.settings.slippage_pct,
                positions={symbol: qty},
            )
            fill = broker.submit_order(
                symbol,
                Side.SELL,
                qty,
                client_id=f"exit:{symbol}:{now.date().isoformat()}",
            )
            account = broker.get_account()
            self.repo.set_setting(
                "paper_account",
                {"cash": account.cash, "equity": account.equity},
            )
            self.repo.insert_order(
                {
                    "proposal_id": position.get("proposal_id", position["symbol"]),
                    "client_id": fill.client_id,
                    "symbol": symbol,
                    "side": fill.side.value,
                    "qty": qty,
                    "fill_price": fill.fill_price,
                    "status": "FILLED",
                }
            )
            self.repo.remove_position(symbol)
            reason = "stop hit" if stop_hit else "time cap"
            self.output(
                f"SELL {qty} {symbol} at {fill.fill_price:.2f} ({reason})"
            )
            if not dry_run and self.sender is not None and _env("USER_PHONE"):
                self.sender.send(
                    _env("USER_PHONE") or "",
                    f"EXIT: SELL {qty} {symbol} @ {fill.fill_price:.2f} ({reason})",
                )

    def paper_report(self) -> None:
        state = self.repo.get_setting("paper_account") or {}
        if not state:
            self.output("No paper account state yet.")
            return
        self.output(
            f"Paper cash: ${float(state.get('cash', 0)):,.2f} | "
            f"equity: ${float(state.get('equity', 0)):,.2f}"
        )

    def _paper_equity(self) -> float:
        state = self.repo.get_setting("paper_account") or {}
        return float(state.get("equity", self.settings.paper_starting_cash))


def _parse_time(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _default_news_fetcher() -> Callable[[str], list[Headline]] | None:
    token = _env("FINNHUB_TOKEN")
    if not token:
        return None

    def fetch(symbol: str) -> list[Headline]:
        end = date.today()
        start = end - timedelta(days=7)
        with httpx.Client() as client:
            return fetch_company_news(client, symbol, start, end, token)

    return fetch


def build_runtime(*, dry_run: bool = False) -> Runtime:
    settings = Settings()
    supabase_url = _env("SUPABASE_URL")
    supabase_key = _env("SUPABASE_SERVICE_KEY")
    if supabase_url and supabase_key:
        from stock_trader.db.supabase_repo import SupabaseRepository

        repo = SupabaseRepository(supabase_url, supabase_key)
    elif dry_run:
        repo = InMemoryRepository()
    else:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")
    sender = None
    sid = _env("TWILIO_ACCOUNT_SID")
    token = _env("TWILIO_AUTH_TOKEN")
    from_number = _env("TWILIO_FROM_NUMBER")
    if sid and token and from_number and not dry_run:
        sender = TwilioSender(sid, token, from_number)
    return Runtime(
        settings=settings,
        repo=repo,
        news_fetcher=_default_news_fetcher(),
        sender=sender,
    )
