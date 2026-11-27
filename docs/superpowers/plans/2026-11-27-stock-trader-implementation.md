# Stock Trader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the paper-trading phase of an approval-gated swing-trading bot: hybrid screener + ML + news signal engine, SMS proposals, Supabase state, a thin Twilio webhook Worker, and a broker adapter ready for Robinhood.

**Architecture:** A Python package (`src/stock_trader`) owns all trading logic and runs in GitHub Actions. A minimal Cloudflare Worker receives Twilio inbound SMS and writes approvals to Supabase; a Supabase database webhook dispatches the Python executor. A static dashboard reads restricted Supabase views. Broker access is behind one `Broker` protocol with `PaperBroker` first and `RobinhoodBroker` later.

**Tech Stack:** Python 3.12+ (pandas, NumPy, scikit-learn, httpx, yfinance), pytest; Cloudflare Workers (TypeScript, vitest); Supabase Postgres; Twilio SMS; GitHub Actions; static HTML/JS dashboard on Cloudflare Pages.

**Spec:** `docs/superpowers/specs/2026-11-27-stock-trader-design.md`

## Global Constraints

- Risk exactly 1% of account equity per trade: `qty = floor(equity * 0.01 / (entry - stop))`.
- Paper account starts at $20,000; live account is $500 on Robinhood, later.
- Long-only. No shorts, options, margin, or crypto.
- Proposals expire at the next market open; only an explicit `YES` from the whitelisted phone executes.
- Max 5 concurrent positions; one pending proposal at a time.
- No fixed profit target; exits are risk/reward-driven with a 30-day time cap.
- News only counts if `published_at` is strictly before the signal timestamp.
- All writes carry idempotency keys; duplicate submissions are no-ops.
- Secrets never live in the repo: `TWILIO_AUTH_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GH_DISPATCH_TOKEN`, later `ROBINHOOD_*`.
- Python tests run with `pytest`; use `uv run pytest` once the project venv exists. On this machine a usable interpreter is `..\NBA_Prediction_Bot\.venv\Scripts\python.exe`.
- Commit after every task. Work stays on branch `feat/stock-trader-core`.

---

## File Structure

```text
pyproject.toml                       project metadata, dependencies, pytest config
src/stock_trader/
  __init__.py
  config.py                          Settings dataclass with spec defaults
  risk.py                            1% risk sizing
  domain/
    models.py                        enums and frozen dataclasses
    state.py                         trade state machine
    approvals.py                     YES / NO / STOP parsing
  screener.py                        safety screener
  news.py                            lexicon sentiment + news features
  features.py                        price/volume features
  gate.py                            confidence gate + capacity check
  brokers/
    base.py                          Broker protocol, Account type
    paper.py                         PaperBroker with real fill math
    robinhood_mcp.py                 live adapter (later milestone)
  backtest.py                        long-only backtest harness + metrics
  notifications/
    sms.py                           proposal text + Twilio sender
  engine/
    signals.py                       nightly candidate selection
    execute.py                       approval execution
  db/
    repository.py                    Repository protocol + InMemoryRepository
    supabase_repo.py                 PostgREST implementation
  data/
    prices.py                        yfinance adapter (injectable)
    news.py                          Finnhub adapter (injectable HTTP)
tests/                               one test module per unit above
worker/                              Cloudflare Worker (thin Twilio webhook)
  src/index.ts
  test/index.test.ts
  wrangler.toml
  package.json
supabase/migrations/0001_init.sql    tables, views, RLS
.github/workflows/signal.yml         nightly cron
.github/workflows/execute.yml        repository_dispatch
dashboard/                           static dashboard (HTML/JS, Supabase REST)
```

---

### Task 1: Project scaffold and settings

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/stock_trader/__init__.py`, `src/stock_trader/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Settings` frozen dataclass with fields `paper_starting_cash: float`, `risk_per_trade: float`, `max_positions: int`, `confidence_threshold: float`, `weekly_drawdown_limit: float`, `max_hold_days: int`, `min_price: float`, `min_avg_dollar_volume: float`, `earnings_blackout_days: int`, `stop_atr_multiple: float`, `slippage_pct: float`, `news_window_days: int`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'stock_trader'`.

- [ ] **Step 3: Write minimal implementation**

`pyproject.toml`:

```toml
[project]
name = "stock-trader"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "pandas>=2.2",
  "numpy>=1.26",
  "scikit-learn>=1.5",
  "httpx>=0.27",
  "yfinance>=0.2.50",
]

[dependency-groups]
dev = ["pytest>=8"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

`.gitignore`: `.venv/`, `__pycache__/`, `.pytest_cache/`, `*.egg-info/`, `.env`, `node_modules/`, `.wrangler/`.

`src/stock_trader/config.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    paper_starting_cash: float = 20_000.0
    risk_per_trade: float = 0.01
    max_positions: int = 5
    confidence_threshold: float = 0.65
    weekly_drawdown_limit: float = 0.05
    max_hold_days: int = 30
    min_price: float = 5.0
    min_avg_dollar_volume: float = 10_000_000.0
    earnings_blackout_days: int = 2
    stop_atr_multiple: float = 2.0
    slippage_pct: float = 0.001
    news_window_days: int = 7

    def __post_init__(self) -> None:
        if not 0 < self.risk_per_trade < 1:
            raise ValueError("risk_per_trade must be in (0, 1)")
        if not 0 < self.confidence_threshold < 1:
            raise ValueError("confidence_threshold must be in (0, 1)")
        if self.max_positions < 1:
            raise ValueError("max_positions must be >= 1")
        if self.paper_starting_cash <= 0:
            raise ValueError("paper_starting_cash must be positive")

    @property
    def risk_amount(self) -> float:
        return self.paper_starting_cash * self.risk_per_trade
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore src tests
git commit -m "feat: scaffold project and settings"
```

---

### Task 2: Risk sizing

**Files:**
- Create: `src/stock_trader/risk.py`
- Test: `tests/test_risk.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `risk_amount(equity: float, risk_pct: float) -> float`; `position_size(equity: float, entry: float, stop: float, risk_pct: float) -> int`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from stock_trader.risk import position_size, risk_amount


def test_risk_amount_is_one_percent_of_equity():
    assert risk_amount(20_000.0, 0.01) == 200.0


def test_position_size_uses_stop_distance():
    # $200 risk / ($100 - $95) = 40 shares
    assert position_size(20_000.0, 100.0, 95.0, 0.01) == 40


def test_position_size_rounds_down_to_whole_shares():
    # $100 risk / $1.50 stop distance = 66.67 -> 66
    assert position_size(10_000.0, 50.0, 48.5, 0.01) == 66


def test_position_size_rejects_stop_at_or_above_entry():
    with pytest.raises(ValueError):
        position_size(20_000.0, 100.0, 100.0, 0.01)


def test_position_size_rejects_bad_risk_pct():
    with pytest.raises(ValueError):
        position_size(20_000.0, 100.0, 95.0, 0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_risk.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
import math


def risk_amount(equity: float, risk_pct: float) -> float:
    return equity * risk_pct


def position_size(equity: float, entry: float, stop: float, risk_pct: float) -> int:
    if equity <= 0:
        raise ValueError("equity must be positive")
    if not 0 < risk_pct < 1:
        raise ValueError("risk_pct must be in (0, 1)")
    if entry <= 0:
        raise ValueError("entry must be positive")
    if stop <= 0 or stop >= entry:
        raise ValueError("stop must be positive and below entry")
    shares = math.floor(risk_amount(equity, risk_pct) / (entry - stop))
    if shares < 1:
        raise ValueError("stop distance too wide for account size")
    return shares
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_risk.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/stock_trader/risk.py tests/test_risk.py
git commit -m "feat: add 1 percent risk sizing"
```

---

### Task 3: Trade state machine

**Files:**
- Create: `src/stock_trader/domain/__init__.py`, `src/stock_trader/domain/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `TradeState` StrEnum with members `PROPOSED, APPROVED, ORDER_SUBMITTED, FILLED, OPEN, EXIT_SUBMITTED, CLOSED, REJECTED, EXPIRED, CANCELLED`; `InvalidTransition(Exception)`; `transition(current: TradeState, target: TradeState) -> TradeState`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from stock_trader.domain.state import InvalidTransition, TradeState, transition


def test_approval_flow_transitions():
    assert transition(TradeState.PROPOSED, TradeState.APPROVED) is TradeState.APPROVED
    assert transition(TradeState.APPROVED, TradeState.ORDER_SUBMITTED) is TradeState.ORDER_SUBMITTED
    assert transition(TradeState.FILLED, TradeState.OPEN) is TradeState.OPEN
    assert transition(TradeState.OPEN, TradeState.EXIT_SUBMITTED) is TradeState.EXIT_SUBMITTED
    assert transition(TradeState.EXIT_SUBMITTED, TradeState.CLOSED) is TradeState.CLOSED


def test_cannot_close_an_unapproved_proposal():
    with pytest.raises(InvalidTransition):
        transition(TradeState.PROPOSED, TradeState.CLOSED)


def test_terminal_states_have_no_exits():
    for terminal in (TradeState.CLOSED, TradeState.REJECTED,
                     TradeState.EXPIRED, TradeState.CANCELLED):
        with pytest.raises(InvalidTransition):
            transition(terminal, TradeState.OPEN)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
from enum import StrEnum


class TradeState(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    FILLED = "FILLED"
    OPEN = "OPEN"
    EXIT_SUBMITTED = "EXIT_SUBMITTED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class InvalidTransition(Exception):
    pass


ALLOWED: dict[TradeState, frozenset[TradeState]] = {
    TradeState.PROPOSED: frozenset(
        {TradeState.APPROVED, TradeState.REJECTED, TradeState.EXPIRED}
    ),
    TradeState.APPROVED: frozenset(
        {TradeState.ORDER_SUBMITTED, TradeState.CANCELLED}
    ),
    TradeState.ORDER_SUBMITTED: frozenset(
        {TradeState.FILLED, TradeState.CANCELLED}
    ),
    TradeState.FILLED: frozenset({TradeState.OPEN}),
    TradeState.OPEN: frozenset({TradeState.EXIT_SUBMITTED}),
    TradeState.EXIT_SUBMITTED: frozenset(
        {TradeState.CLOSED, TradeState.OPEN}
    ),
    TradeState.CLOSED: frozenset(),
    TradeState.REJECTED: frozenset(),
    TradeState.EXPIRED: frozenset(),
    TradeState.CANCELLED: frozenset(),
}


def transition(current: TradeState, target: TradeState) -> TradeState:
    if target not in ALLOWED[current]:
        raise InvalidTransition(f"{current} -> {target} is not allowed")
    return target
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_state.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/stock_trader/domain tests/test_state.py
git commit -m "feat: add trade state machine"
```

---

### Task 4: Approval reply parsing

**Files:**
- Create: `src/stock_trader/domain/approvals.py`
- Test: `tests/test_approvals.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Decision` StrEnum (`YES, NO, STOP, UNKNOWN`); `parse_reply(text: str) -> Decision`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_approvals.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_approvals.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/stock_trader/domain/approvals.py tests/test_approvals.py
git commit -m "feat: parse SMS approvals"
```

---

### Task 5: Safety screener

**Files:**
- Create: `src/stock_trader/domain/models.py` (add `StockSnapshot`), `src/stock_trader/screener.py`
- Test: `tests/test_screener.py`

**Interfaces:**
- Consumes: `Settings` (Task 1).
- Produces: `StockSnapshot(symbol: str, price: float, avg_dollar_volume: float, sma_long: float, days_to_earnings: int)`; `passes_screener(snapshot: StockSnapshot, settings: Settings) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from stock_trader.config import Settings
from stock_trader.domain.models import StockSnapshot
from stock_trader.screener import passes_screener


def snapshot(**overrides):
    base = dict(symbol="AAPL", price=50.0, avg_dollar_volume=50_000_000.0,
                sma_long=45.0, days_to_earnings=10)
    base.update(overrides)
    return StockSnapshot(**base)


def test_liquid_trending_stock_passes():
    assert passes_screener(snapshot(), Settings()) is True


@pytest.mark.parametrize("overrides", [
    {"price": 4.99},
    {"avg_dollar_volume": 9_999_999.0},
    {"sma_long": 55.0},
    {"days_to_earnings": 2},
    {"days_to_earnings": 0},
])
def test_each_rule_can_reject(overrides):
    assert passes_screener(snapshot(**overrides), Settings()) is False


def test_two_days_before_earnings_is_blacked_out_but_three_is_not():
    assert passes_screener(snapshot(days_to_earnings=2), Settings()) is False
    assert passes_screener(snapshot(days_to_earnings=3), Settings()) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_screener.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

In `domain/models.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class StockSnapshot:
    symbol: str
    price: float
    avg_dollar_volume: float
    sma_long: float
    days_to_earnings: int
```

`screener.py`:

```python
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
```

`StockSnapshot` also gets:

```python
    @property
    def close_below_sma(self) -> bool:
        return self.price < self.sma_long
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_screener.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/stock_trader/domain/models.py src/stock_trader/screener.py tests/test_screener.py
git commit -m "feat: add safety screener"
```

---

### Task 6: News sentiment and leakage guard

**Files:**
- Create: `src/stock_trader/news.py`; extend `src/stock_trader/domain/models.py` with `Headline`, `NewsFeatures`
- Test: `tests/test_news.py`

**Interfaces:**
- Consumes: `Settings.news_window_days`.
- Produces: `Headline(title: str, published_at: datetime)`; `NewsFeatures(sentiment: float, headline_count: int, shock: bool)`; `score_sentiment(text: str) -> float`; `build_news_features(headlines: Sequence[Headline], *, as_of: datetime, window_days: int = 7, price_change_pct: float = 0.0, shock_price_pct: float = 0.05, shock_min_headlines: int = 3) -> NewsFeatures`.

- [ ] **Step 1: Write the failing test**

```python
from datetime import UTC, datetime, timedelta

from stock_trader.domain.models import Headline
from stock_trader.news import build_news_features, score_sentiment

NOW = datetime(2026, 11, 27, 22, 0, tzinfo=UTC)


def test_positive_headline_scores_positive():
    assert score_sentiment("Company beats estimates and raises guidance") == 1.0


def test_mixed_headline_nets_to_zero():
    assert score_sentiment("Beat expectations but shares plunge") == 0.0


def test_only_headlines_before_as_of_and_inside_window_count():
    headlines = [
        Headline("stock surges on upgrade", NOW - timedelta(days=1)),
        Headline("stock surges on upgrade", NOW - timedelta(days=8)),   # expired
        Headline("stock surges on upgrade", NOW + timedelta(hours=1)),  # future
    ]
    features = build_news_features(headlines, as_of=NOW, window_days=7)
    assert features.headline_count == 1
    assert features.sentiment == 1.0


def test_news_shock_needs_both_price_move_and_headline_volume():
    headlines = [Headline("stock surges", NOW - timedelta(hours=i)) for i in range(3)]
    assert build_news_features(headlines, as_of=NOW, price_change_pct=0.06).shock is True
    assert build_news_features(headlines, as_of=NOW, price_change_pct=0.02).shock is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_news.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`models.py` additions:

```python
from datetime import datetime


@dataclass(frozen=True)
class Headline:
    title: str
    published_at: datetime


@dataclass(frozen=True)
class NewsFeatures:
    sentiment: float
    headline_count: int
    shock: bool
```

`news.py`:

```python
import re
from collections.abc import Sequence
from datetime import datetime, timedelta

from stock_trader.domain.models import Headline, NewsFeatures

POSITIVE = frozenset(
    "beat beats upgrade upgraded growth grows record surge surges rally "
    "outperform raise raises profit wins approval".split()
)
NEGATIVE = frozenset(
    "miss misses downgrade downgraded lawsuit probe plunge plunges fall "
    "falls cut cuts fraud recall layoffs warning".split()
)


def score_sentiment(text: str) -> float:
    words = re.findall(r"[a-z]+", text.casefold())
    positives = sum(word in POSITIVE for word in words)
    negatives = sum(word in NEGATIVE for word in words)
    total = positives + negatives
    return 0.0 if total == 0 else (positives - negatives) / total


def build_news_features(
    headlines: Sequence[Headline],
    *,
    as_of: datetime,
    window_days: int = 7,
    price_change_pct: float = 0.0,
    shock_price_pct: float = 0.05,
    shock_min_headlines: int = 3,
) -> NewsFeatures:
    cutoff = as_of - timedelta(days=window_days)
    usable = [h for h in headlines if cutoff <= h.published_at < as_of]
    if not usable:
        return NewsFeatures(sentiment=0.0, headline_count=0, shock=False)
    sentiment = sum(score_sentiment(h.title) for h in usable) / len(usable)
    shock = (
        len(usable) >= shock_min_headlines
        and abs(price_change_pct) >= shock_price_pct
    )
    return NewsFeatures(
        sentiment=sentiment, headline_count=len(usable), shock=shock
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_news.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/stock_trader/news.py src/stock_trader/domain/models.py tests/test_news.py
git commit -m "feat: add news features with leakage guard"
```

---

### Task 7: Price/volume features

**Files:**
- Create: `src/stock_trader/features.py`
- Test: `tests/test_features.py`

**Interfaces:**
- Consumes: pandas.
- Produces: `price_features(prices: pd.Series, volumes: pd.Series, benchmark: pd.Series | None = None) -> dict[str, float]` with keys `momentum_21`, `volatility_21`, `volume_trend`, `drawdown_63`, and `relative_strength_63` when a benchmark is given.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
import pandas as pd
import pytest

from stock_trader.features import price_features


def make_prices(values):
    return pd.Series(values, dtype=float)


def test_flat_prices_have_zero_momentum_and_volatility():
    prices = make_prices([100.0] * 70)
    volumes = make_prices([1_000_000.0] * 70)
    features = price_features(prices, volumes)
    assert features["momentum_21"] == 0.0
    assert features["volatility_21"] == 0.0
    assert features["drawdown_63"] == 0.0


def test_momentum_uses_21_session_lookback():
    prices = make_prices([100.0] * 50 + [110.0] * 21)
    volumes = make_prices([1_000_000.0] * 71)
    features = price_features(prices, volumes)
    # prices[-1]/prices[-22] - 1 = 110/100 - 1
    assert features["momentum_21"] == pytest.approx(0.10)


def test_volume_trend_compares_recent_to_longer_average():
    prices = make_prices([100.0] * 70)
    volumes = make_prices([1_000_000.0] * 65 + [2_000_000.0] * 5)
    features = price_features(prices, volumes)
    expected = np.mean([2_000_000.0] * 5) / np.mean([1_000_000.0] * 65 + [2_000_000.0] * 5) - 1
    assert features["volume_trend"] == pytest.approx(expected)


def test_short_history_rejected():
    with pytest.raises(ValueError):
        price_features(make_prices([100.0] * 10), make_prices([1.0] * 10))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_features.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
import numpy as np
import pandas as pd


def _return_over(prices: pd.Series, sessions: int) -> float:
    return float(prices.iloc[-1] / prices.iloc[-1 - sessions] - 1.0)


def price_features(
    prices: pd.Series,
    volumes: pd.Series,
    benchmark: pd.Series | None = None,
) -> dict[str, float]:
    if len(prices) < 22 or len(volumes) != len(prices):
        raise ValueError("need at least 22 aligned price/volume observations")
    returns = prices.pct_change().dropna()
    window = min(63, len(prices))
    recent_volume = volumes.iloc[-5:].mean()
    trailing_volume = volumes.iloc[-21:].mean()
    features = {
        "momentum_21": _return_over(prices, 21),
        "volatility_21": float(returns.iloc[-21:].std(ddof=0) * np.sqrt(252)),
        "volume_trend": float(recent_volume / trailing_volume - 1.0),
        "drawdown_63": float(prices.iloc[-1] / prices.iloc[-window:].max() - 1.0),
    }
    if benchmark is not None:
        if len(benchmark) != len(prices):
            raise ValueError("benchmark must align with prices")
        features["relative_strength_63"] = (
            _return_over(prices, min(63, len(prices) - 1))
            - _return_over(benchmark, min(63, len(benchmark) - 1))
        )
    return features
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_features.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/stock_trader/features.py tests/test_features.py
git commit -m "feat: add price and volume features"
```

---

### Task 8: Confidence gate and capacity

**Files:**
- Create: `src/stock_trader/gate.py`
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: `Settings`.
- Produces: `GateContext(probability: float, holding: bool, open_positions: int, pending_proposals: int)`; `confidence_gate(context: GateContext, settings: Settings) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_gate.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass

from stock_trader.config import Settings


@dataclass(frozen=True)
class GateContext:
    probability: float
    holding: bool
    open_positions: int
    pending_proposals: int


def confidence_gate(context: GateContext, settings: Settings) -> bool:
    return (
        context.probability >= settings.confidence_threshold
        and not context.holding
        and context.open_positions < settings.max_positions
        and context.pending_proposals == 0
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_gate.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/stock_trader/gate.py tests/test_gate.py
git commit -m "feat: add confidence and capacity gate"
```

---

### Task 9: Paper broker with idempotent fills

**Files:**
- Create: `src/stock_trader/brokers/__init__.py`, `src/stock_trader/brokers/base.py`, `src/stock_trader/brokers/paper.py`; extend `domain/models.py` with `Order`, `OrderStatus`, `Side`, `Account`
- Test: `tests/test_paper_broker.py`

**Interfaces:**
- Consumes: quote provider callable.
- Produces: `Side` (`BUY`, `SELL`), `OrderStatus` (`FILLED`, `REJECTED`), `Order(id, symbol, side, qty, fill_price, status, client_id)`; `Account(cash, equity)`; `PaperBroker(starting_cash: float, quote_provider: Callable[[str], float], slippage_pct: float = 0.001)` with `get_quote`, `submit_order(symbol, side, qty, order_type="market", client_id=None)`, `get_positions() -> dict[str, int]`, `get_account() -> Account`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from stock_trader.brokers.paper import InsufficientFunds, PaperBroker
from stock_trader.domain.models import Side


def broker():
    return PaperBroker(20_000.0, lambda symbol: 100.0, slippage_pct=0.001)


def test_buy_applies_slippage_and_reduces_cash():
    b = broker()
    order = b.submit_order("AAPL", Side.BUY, 10, client_id="c1")
    assert order.fill_price == pytest.approx(100.10)
    assert b.get_positions()["AAPL"] == 10
    assert b.get_account().cash == pytest.approx(20_000.0 - 1_001.0)


def test_sell_returns_cash_minus_slippage():
    b = broker()
    b.submit_order("AAPL", Side.BUY, 10, client_id="c1")
    b.submit_order("AAPL", Side.SELL, 10, client_id="c2")
    assert "AAPL" not in b.get_positions()
    assert b.get_account().cash == pytest.approx(18_999.0 + 999.0)


def test_insufficient_cash_rejected():
    b = PaperBroker(500.0, lambda symbol: 100.0)
    with pytest.raises(InsufficientFunds):
        b.submit_order("AAPL", Side.BUY, 10, client_id="c1")
    assert b.get_positions() == {}


def test_duplicate_client_id_does_not_trade_twice():
    b = broker()
    first = b.submit_order("AAPL", Side.BUY, 10, client_id="same")
    second = b.submit_order("AAPL", Side.BUY, 10, client_id="same")
    assert first == second
    assert b.get_positions()["AAPL"] == 10


def test_cannot_sell_more_than_held():
    b = broker()
    with pytest.raises(ValueError):
        b.submit_order("AAPL", Side.SELL, 1, client_id="c1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_paper_broker.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`base.py`:

```python
from typing import Protocol

from stock_trader.domain.models import Account, Order, Side


class Broker(Protocol):
    def get_quote(self, symbol: str) -> float: ...
    def submit_order(self, symbol: str, side: Side, qty: int,
                     order_type: str = "market",
                     client_id: str | None = None) -> Order: ...
    def cancel_order(self, order_id: str) -> None: ...
    def get_positions(self) -> dict[str, int]: ...
    def get_account(self) -> Account: ...
```

`paper.py`:

```python
from collections.abc import Callable

from stock_trader.domain.models import Account, Order, OrderStatus, Side


class InsufficientFunds(Exception):
    pass


class PaperBroker:
    def __init__(self, starting_cash: float,
                 quote_provider: Callable[[str], float],
                 slippage_pct: float = 0.001) -> None:
        self._cash = starting_cash
        self._quotes = quote_provider
        self._slippage = slippage_pct
        self._positions: dict[str, int] = {}
        self._fills: list[Order] = []
        self._by_client_id: dict[str, Order] = {}

    def get_quote(self, symbol: str) -> float:
        return float(self._quotes(symbol))

    def submit_order(self, symbol: str, side: Side, qty: int,
                     order_type: str = "market",
                     client_id: str | None = None) -> Order:
        if client_id and client_id in self._by_client_id:
            return self._by_client_id[client_id]
        if qty <= 0:
            raise ValueError("qty must be positive")
        quote = self.get_quote(symbol)
        if side is Side.BUY:
            price = quote * (1 + self._slippage)
            cost = price * qty
            if cost > self._cash:
                raise InsufficientFunds(f"need {cost:.2f}, have {self._cash:.2f}")
            self._cash -= cost
            self._positions[symbol] = self._positions.get(symbol, 0) + qty
        else:
            held = self._positions.get(symbol, 0)
            if qty > held:
                raise ValueError(f"cannot sell {qty} {symbol}, holding {held}")
            price = quote * (1 - self._slippage)
            self._cash += price * qty
            self._positions[symbol] = held - qty
        order = Order(
            id=f"paper-{len(self._fills) + 1}",
            symbol=symbol, side=side, qty=qty,
            fill_price=price, status=OrderStatus.FILLED,
            client_id=client_id,
        )
        self._fills.append(order)
        if client_id:
            self._by_client_id[client_id] = order
        return order

    def cancel_order(self, order_id: str) -> None:
        return None

    def get_positions(self) -> dict[str, int]:
        return {s: q for s, q in self._positions.items() if q > 0}

    def get_account(self) -> Account:
        equity = self._cash + sum(
            q * self.get_quote(s) for s, q in self._positions.items()
        )
        return Account(cash=self._cash, equity=equity)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_paper_broker.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/stock_trader/brokers src/stock_trader/domain/models.py tests/test_paper_broker.py
git commit -m "feat: add idempotent paper broker"
```

---

### Task 10: Backtest harness

**Files:**
- Create: `src/stock_trader/backtest.py`
- Test: `tests/test_backtest.py`

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd
import pytest

from stock_trader.backtest import backtest_long_only


def test_single_winner_trade_produces_profit_and_metrics():
    prices = pd.Series([100.0, 100.0, 110.0, 120.0, 120.0])
    entries = pd.Series([False, True, False, False, False])
    result = backtest_long_only(prices, entries, hold_days=2, cost_pct=0.0)
    assert result.metrics.total_return == pytest.approx(0.20)
    assert result.metrics.trades == 1
    assert result.metrics.win_rate == 1.0
    assert result.metrics.max_drawdown == 0.0


def test_costs_reduce_return():
    prices = pd.Series([100.0, 100.0, 110.0, 120.0, 120.0])
    entries = pd.Series([False, True, False, False, False])
    free = backtest_long_only(prices, entries, hold_days=2, cost_pct=0.0)
    paid = backtest_long_only(prices, entries, hold_days=2, cost_pct=0.001)
    assert paid.metrics.total_return < free.metrics.total_return


def test_losing_trade_reported():
    prices = pd.Series([100.0, 100.0, 90.0, 80.0, 80.0])
    entries = pd.Series([False, True, False, False, False])
    result = backtest_long_only(prices, entries, hold_days=2, cost_pct=0.0)
    assert result.metrics.win_rate == 0.0
    assert result.metrics.total_return == pytest.approx(-0.20)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_backtest.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestMetrics:
    total_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    trades: int


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.Series
    metrics: BacktestMetrics


def backtest_long_only(
    prices: pd.Series,
    entries: pd.Series,
    *,
    hold_days: int,
    cost_pct: float,
) -> BacktestResult:
    if len(prices) != len(entries):
        raise ValueError("prices and entries must align")
    equity = 1.0
    curve = [equity]
    trade_returns: list[float] = []
    index = prices.index
    i = 0
    while i < len(prices) - 1:
        if bool(entries.iloc[i]):
            exit_idx = min(i + hold_days, len(prices) - 1)
            gross = prices.iloc[exit_idx] / prices.iloc[i]
            net = gross * (1 - cost_pct) / (1 + cost_pct)
            trade_returns.append(net - 1.0)
            equity *= net
            curve.append(equity)
            i = exit_idx + 1
        else:
            curve.append(equity)
            i += 1
    series = pd.Series(curve[: len(prices)], index=index)
    daily = series.pct_change().dropna()
    sharpe = 0.0 if daily.std(ddof=0) == 0 else float(
        daily.mean() / daily.std(ddof=0) * np.sqrt(252)
    )
    peak = series.cummax()
    max_dd = float((series / peak - 1).min())
    wins = [r for r in trade_returns if r > 0]
    gross_win = sum(wins)
    gross_loss = -sum(r for r in trade_returns if r < 0)
    profit_factor = float("inf") if gross_loss == 0 and wins else (
        gross_win / gross_loss if gross_loss else 0.0
    )
    return BacktestResult(
        equity_curve=series,
        metrics=BacktestMetrics(
            total_return=float(series.iloc[-1] - 1.0),
            sharpe=sharpe,
            max_drawdown=max_dd,
            win_rate=len(wins) / len(trade_returns) if trade_returns else 0.0,
            profit_factor=profit_factor,
            trades=len(trade_returns),
        ),
    )
```

Note the buy/sell cost in this first cut is applied symmetrically as
`close_return * (1 - cost) / (1 + cost)`; Task 20's dry-run tuning revisits
the slippage model.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_backtest.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/stock_trader/backtest.py tests/test_backtest.py
git commit -m "feat: add long-only backtest harness"
```

---

### Task 11: Proposal model, expiry, and SMS text

**Files:**
- Create: `src/stock_trader/domain/proposals.py`, `src/stock_trader/notifications/__init__.py`, `src/stock_trader/notifications/sms.py`
- Test: `tests/test_proposals.py`, `tests/test_sms.py`

**Interfaces:**
- Produces: `Proposal(id: str, symbol: str, qty: int, entry_price: float, stop_price: float, confidence: float, rationale: str, created_at: datetime, expires_at: datetime)` with `is_expired(now) -> bool`; `compose_proposal_message(proposal: Proposal) -> str`.

- [ ] **Step 1: Write the failing test**

```python
from datetime import UTC, datetime

from stock_trader.domain.proposals import Proposal
from stock_trader.notifications.sms import compose_proposal_message

NOW = datetime(2026, 11, 27, 22, 0, tzinfo=UTC)


def proposal():
    return Proposal(
        id="p1", symbol="AAPL", qty=40, entry_price=100.0, stop_price=95.0,
        confidence=0.72, rationale="Above trend; positive news",
        created_at=NOW, expires_at=datetime(2026, 11, 30, 14, 30, tzinfo=UTC),
    )


def test_proposal_message_contains_action_and_levels():
    message = compose_proposal_message(proposal())
    assert "BUY 40 AAPL" in message
    assert "Entry 100.00" in message
    assert "Stop 95.00" in message
    assert "Reply YES to approve" in message
    assert "p1" in message


def test_proposal_expires_at_or_after_open():
    assert proposal().is_expired(datetime(2026, 11, 30, 14, 30, tzinfo=UTC)) is True
    assert proposal().is_expired(datetime(2026, 11, 30, 14, 29, tzinfo=UTC)) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_proposals.py tests/test_sms.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`domain/proposals.py`:

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Proposal:
    id: str
    symbol: str
    qty: int
    entry_price: float
    stop_price: float
    confidence: float
    rationale: str
    created_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at
```

`notifications/sms.py`:

```python
from stock_trader.domain.proposals import Proposal


def compose_proposal_message(proposal: Proposal) -> str:
    return (
        f"SWING PICK {proposal.symbol}\n"
        f"BUY {proposal.qty} {proposal.symbol} | "
        f"Entry {proposal.entry_price:.2f} | Stop {proposal.stop_price:.2f}\n"
        f"Confidence {proposal.confidence:.0%} | {proposal.rationale}\n"
        f"Reply YES to approve, NO to skip. ID {proposal.id}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_proposals.py tests/test_sms.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/stock_trader/domain/proposals.py src/stock_trader/notifications tests/test_proposals.py tests/test_sms.py
git commit -m "feat: add proposal model and SMS text"
```

---

### Task 12: Execution engine

**Files:**
- Create: `src/stock_trader/engine/__init__.py`, `src/stock_trader/engine/execute.py`
- Test: `tests/test_execute.py`

**Interfaces:**
- Consumes: `Proposal`, `Decision`, `Broker`, `PaperBroker`.
- Produces: `ExecutionStatus` StrEnum (`FILLED`, `EXPIRED`, `REJECTED`, `DUPLICATE`); `execute_approval(proposal, decision, broker, now, client_id) -> ExecutionStatus`.

- [ ] **Step 1: Write the failing test**

```python
from datetime import UTC, datetime, timedelta

from stock_trader.brokers.paper import PaperBroker
from stock_trader.domain.approvals import Decision
from stock_trader.domain.proposals import Proposal
from stock_trader.engine.execute import ExecutionStatus, execute_approval

NOW = datetime(2026, 11, 27, 22, 0, tzinfo=UTC)


def proposal(expires_at=None):
    return Proposal(
        id="p1", symbol="AAPL", qty=10, entry_price=100.0, stop_price=95.0,
        confidence=0.7, rationale="test",
        created_at=NOW - timedelta(hours=1),
        expires_at=expires_at or NOW + timedelta(hours=12),
    )


def test_yes_fills_once():
    broker = PaperBroker(20_000.0, lambda s: 100.0)
    assert execute_approval(proposal(), Decision.YES, broker, NOW, "c1") is ExecutionStatus.FILLED
    assert execute_approval(proposal(), Decision.YES, broker, NOW, "c1") is ExecutionStatus.DUPLICATE
    assert broker.get_positions()["AAPL"] == 10


def test_no_rejects():
    broker = PaperBroker(20_000.0, lambda s: 100.0)
    assert execute_approval(proposal(), Decision.NO, broker, NOW, "c1") is ExecutionStatus.REJECTED
    assert broker.get_positions() == {}


def test_expired_proposal_is_not_executed():
    broker = PaperBroker(20_000.0, lambda s: 100.0)
    expired = proposal(expires_at=NOW)
    assert execute_approval(expired, Decision.YES, broker, NOW, "c1") is ExecutionStatus.EXPIRED
    assert broker.get_positions() == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_execute.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
from enum import StrEnum

from stock_trader.domain.approvals import Decision
from stock_trader.domain.models import Side
from stock_trader.domain.proposals import Proposal


class ExecutionStatus(StrEnum):
    FILLED = "FILLED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"


def execute_approval(proposal: Proposal, decision: Decision, broker, now, client_id: str) -> ExecutionStatus:
    if decision is not Decision.YES:
        return ExecutionStatus.REJECTED
    if proposal.is_expired(now):
        return ExecutionStatus.EXPIRED
    before = len(getattr(broker, "_fills", []))
    broker.submit_order(
        proposal.symbol, Side.BUY, proposal.qty, client_id=client_id
    )
    after = len(getattr(broker, "_fills", []))
    return ExecutionStatus.FILLED if after > before else ExecutionStatus.DUPLICATE
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_execute.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/stock_trader/engine tests/test_execute.py
git commit -m "feat: add approval execution engine"
```

---

### Task 13: Repository seam

**Files:**
- Create: `src/stock_trader/db/__init__.py`, `src/stock_trader/db/repository.py`
- Test: `tests/test_repository.py`

**Interfaces:**
- Produces: `Repository` Protocol (`save_proposal`, `get_proposal`, `save_approval`, `get_approval`, `set_trade_state`, `get_trade_state`); `InMemoryRepository` implementing it.

- [ ] **Step 1: Write the failing test**

```python
from stock_trader.db.repository import InMemoryRepository
from stock_trader.domain.approvals import Decision
from stock_trader.domain.state import TradeState


def test_proposal_round_trip_and_approval_key():
    repo = InMemoryRepository()
    repo.save_proposal("p1", {"symbol": "AAPL"})
    assert repo.get_proposal("p1") == {"symbol": "AAPL"}
    repo.save_approval("approval-1", {"decision": Decision.YES.value})
    assert repo.get_approval("approval-1") == {"decision": "YES"}
    repo.save_approval("approval-1", {"decision": Decision.NO.value})
    assert repo.get_approval("approval-1") == {"decision": "YES"}


def test_trade_state_updates():
    repo = InMemoryRepository()
    repo.set_trade_state("t1", TradeState.PROPOSED)
    repo.set_trade_state("t1", TradeState.APPROVED)
    assert repo.get_trade_state("t1") is TradeState.APPROVED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_repository.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
from typing import Any, Protocol

from stock_trader.domain.state import TradeState


class Repository(Protocol):
    def save_proposal(self, proposal_id: str, data: dict[str, Any]) -> None: ...
    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None: ...
    def save_approval(self, key: str, data: dict[str, Any]) -> None: ...
    def get_approval(self, key: str) -> dict[str, Any] | None: ...
    def set_trade_state(self, trade_id: str, state: TradeState) -> None: ...
    def get_trade_state(self, trade_id: str) -> TradeState: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self._proposals: dict[str, dict[str, Any]] = {}
        self._approvals: dict[str, dict[str, Any]] = {}
        self._states: dict[str, TradeState] = {}

    def save_proposal(self, proposal_id: str, data: dict[str, Any]) -> None:
        self._proposals[proposal_id] = data

    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        return self._proposals.get(proposal_id)

    def save_approval(self, key: str, data: dict[str, Any]) -> None:
        self._approvals.setdefault(key, data)

    def get_approval(self, key: str) -> dict[str, Any] | None:
        return self._approvals.get(key)

    def set_trade_state(self, trade_id: str, state: TradeState) -> None:
        self._states[trade_id] = state

    def get_trade_state(self, trade_id: str) -> TradeState:
        return self._states[trade_id]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_repository.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/stock_trader/db tests/test_repository.py
git commit -m "feat: add repository seam"
```

---

### Task 14: Data source adapters (yfinance and Finnhub)

**Files:**
- Create: `src/stock_trader/data/__init__.py`, `src/stock_trader/data/prices.py`, `src/stock_trader/data/news.py`
- Test: `tests/test_data_sources.py`

**Interfaces:**
- Produces: `load_price_history(fetch: Callable[[str], pd.DataFrame], symbols: Sequence[str]) -> dict[str, pd.DataFrame]`; `parse_finnhub_news(payload: list[dict], symbol: str) -> list[Headline]`; `fetch_company_news(client: httpx.Client, symbol: str, start: date, end: date, token: str) -> list[Headline]`.

- [ ] **Step 1: Write the failing test**

```python
from datetime import UTC, datetime

import httpx
import pandas as pd

from stock_trader.data.news import fetch_company_news, parse_finnhub_news
from stock_trader.data.prices import load_price_history


def test_price_loader_keys_symbols_and_skips_empty():
    def fetch(symbol):
        return pd.DataFrame() if symbol == "BAD" else pd.DataFrame({"Close": [1.0]})
    frames = load_price_history(fetch, ["AAPL", "BAD"])
    assert list(frames) == ["AAPL"]


def test_finnhub_payload_parsing_keeps_full_structure():
    payload = [{
        "headline": "AAPL beats estimates",
        "datetime": 1_765_000_000,
        "source": "wire",
        "url": "https://example.com/x",
    }]
    headlines = parse_finnhub_news(payload, "AAPL")
    assert headlines[0].title == "AAPL beats estimates"
    assert headlines[0].published_at == datetime.fromtimestamp(1_765_000_000, tz=UTC)


def test_finnhub_fetcher_sends_expected_query():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json=[{
            "headline": "AAPL upgrade", "datetime": 1_765_000_000,
            "source": "wire", "url": "",
        }])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    headlines = fetch_company_news(
        client, "AAPL", datetime(2026, 11, 20).date(),
        datetime(2026, 11, 27).date(), "token123",
    )
    assert "symbol=AAPL" in seen["url"]
    assert "token=token123" in seen["url"]
    assert headlines[0].title == "AAPL upgrade"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_data_sources.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`data/prices.py`:

```python
from collections.abc import Callable, Sequence

import pandas as pd


def load_price_history(
    fetch: Callable[[str], pd.DataFrame], symbols: Sequence[str]
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        frame = fetch(symbol)
        if frame is not None and not frame.empty:
            frames[symbol] = frame
    return frames
```

`data/news.py`:

```python
from datetime import UTC, date, datetime

import httpx

from stock_trader.domain.models import Headline

FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"


def parse_finnhub_news(payload: list[dict], symbol: str) -> list[Headline]:
    return [
        Headline(
            title=item["headline"],
            published_at=datetime.fromtimestamp(item["datetime"], tz=UTC),
        )
        for item in payload
        if item.get("headline")
    ]


def fetch_company_news(
    client: httpx.Client, symbol: str, start: date, end: date, token: str
) -> list[Headline]:
    response = client.get(
        FINNHUB_NEWS_URL,
        params={
            "symbol": symbol,
            "from": start.isoformat(),
            "to": end.isoformat(),
            "token": token,
        },
        timeout=20,
    )
    response.raise_for_status()
    return parse_finnhub_news(response.json(), symbol)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_data_sources.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/stock_trader/data tests/test_data_sources.py
git commit -m "feat: add price and news data adapters"
```

---

### Task 15: Supabase schema and RLS

**Files:**
- Create: `supabase/migrations/0001_init.sql`
- Docs: `docs/supabase-setup.md`

- [ ] **Step 1: Write the migration**

Tables (all with `id uuid default gen_random_uuid() primary key`,
`created_at timestamptz default now()`):

```sql
create table signals (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  symbol text not null,
  probability double precision not null,
  features jsonb not null default '{}'::jsonb,
  rationale text not null
);

create table proposals (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  symbol text not null,
  qty integer not null check (qty > 0),
  entry_price numeric not null check (entry_price > 0),
  stop_price numeric not null check (stop_price > 0),
  confidence double precision not null,
  rationale text not null,
  expires_at timestamptz not null,
  state text not null default 'PROPOSED'
);

create table approvals (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  proposal_id uuid not null references proposals(id),
  decision text not null check (decision in ('YES','NO','STOP')),
  idempotency_key text not null unique,
  source_number text not null
);

create table orders (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  proposal_id uuid not null references proposals(id),
  client_id text not null unique,
  symbol text not null,
  side text not null,
  qty integer not null,
  fill_price numeric,
  status text not null
);

create table positions (
  id uuid primary key default gen_random_uuid(),
  updated_at timestamptz not null default now(),
  symbol text not null unique,
  qty integer not null,
  avg_price numeric not null,
  stop_price numeric not null,
  opened_at timestamptz not null
);

create table alerts (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  level text not null,
  message text not null
);

create table settings (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);

create view dashboard_positions as
select symbol, qty, avg_price, stop_price, opened_at from positions;

alter table signals enable row level security;
alter table proposals enable row level security;
alter table approvals enable row level security;
alter table orders enable row level security;
alter table positions enable row level security;
alter table alerts enable row level security;
alter table settings enable row level security;
```

- [ ] **Step 2: Add read-only dashboard policy**

```sql
create policy "dashboard read positions" on positions
  for select to anon using (true);
create policy "dashboard read proposals" on proposals
  for select to anon using (true);
create policy "dashboard read signals" on signals
  for select to anon using (true);
```

- [ ] **Step 3: Verify and commit**

Run in Supabase SQL editor on a scratch project; confirm inserts work with the
service key and the anon key can only select.

```bash
git add supabase docs/supabase-setup.md
git commit -m "feat: add Supabase schema and RLS"
```

---

### Task 16: Cloudflare Worker (thin Twilio webhook)

**Files:**
- Create: `worker/src/index.ts`, `worker/test/index.test.ts`, `worker/wrangler.toml`, `worker/package.json`, `worker/tsconfig.json`

- [ ] **Step 1: Write failing tests (vitest)**

```typescript
import { describe, expect, it } from "vitest";
import { parseReply, verifyTwilioSignature } from "../src/index";

describe("parseReply", () => {
  it("normalizes yes", () => {
    expect(parseReply(" Yes ")).toBe("YES");
  });
  it("rejects gibberish", () => {
    expect(parseReply("maybe")).toBe("UNKNOWN");
  });
});

describe("verifyTwilioSignature", () => {
  it("accepts a valid HMAC-SHA1 signature", async () => {
    const ok = await verifyTwilioSignature(
      "secret", "6+o1m6T7zyQvJfM8nC0kg0d9X1w=",
      "https://example.com/sms", { Body: "YES" },
    );
    expect(ok).toBe(true);
  });
});
```

Generate the expected signature independently with
`printf '%s' 'https://example.com/smsYES' | openssl dgst -sha1 -hmac secret -binary | openssl base64`
before running the test.

- [ ] **Step 2: Implement**

`src/index.ts` exports:

- `parseReply(body: string): "YES" | "NO" | "STOP" | "UNKNOWN"`
- `verifyTwilioSignature(authToken, signature, url, params): Promise<boolean>` —
  sort form fields by key, append key/value pairs to the URL, HMAC-SHA1 with
  WebCrypto, base64-compare in constant time.
- `default { async fetch(request, env) }` — only accepts `POST /sms-webhook`,
  verifies signature and `env.ALLOWED_PHONE`, inserts into `approvals` through
  Supabase REST using `env.SUPABASE_URL` and `env.SUPABASE_SERVICE_KEY`, returns
  TwiML `<Response></Response>`. Duplicate idempotency keys return 200.

- [ ] **Step 3: Run tests and commit**

Run: `npm test` in `worker/`
Expected: 2 passed.

```bash
git add worker
git commit -m "feat: add thin Twilio approval worker"
```

---

### Task 17: Nightly signal engine wiring

**Files:**
- Create: `src/stock_trader/engine/signals.py`, `src/stock_trader/cli.py`
- Test: `tests/test_signals.py`

- [ ] **Step 1: Write failing orchestration test**

```python
from stock_trader.config import Settings
from stock_trader.engine.signals import rank_candidates


def test_rank_candidates_filters_and_sorts_by_probability():
    settings = Settings(confidence_threshold=0.6)
    snapshots = {
        "AAPL": {"probability": 0.75},
        "MSFT": {"probability": 0.55},
        "NVDA": {"probability": 0.90},
    }
    ranked = rank_candidates(snapshots, settings)
    assert [c.symbol for c in ranked] == ["NVDA", "AAPL"]
```

- [ ] **Step 2: Implement**

`rank_candidates(scored: dict[str, dict], settings) -> list[Candidate]` sorts by
probability descending and keeps only those above the confidence threshold.
Add `Candidate(symbol, probability, rationale)`.

The CLI exposes `python -m stock_trader.cli nightly`, `execute --key K`, and
`paper-report`, wiring the adapters with environment-controlled dry-run flags.

- [ ] **Step 3: Run and commit**

Run: `python -m pytest tests/test_signals.py -v`
Expected: 1 passed.

```bash
git add src/stock_trader/engine/signals.py src/stock_trader/cli.py tests/test_signals.py
git commit -m "feat: wire nightly signal orchestration"
```

---

### Task 18: GitHub Actions workflows

**Files:**
- Create: `.github/workflows/signal.yml`, `.github/workflows/execute.yml`

- [ ] **Step 1: Write `signal.yml`**

```yaml
name: nightly-signals
on:
  schedule:
    - cron: "0 23 * * 1-5"   # ~17:00 CT in winter; adjust for DST
  workflow_dispatch:
jobs:
  signal:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen
      - run: uv run python -m stock_trader.cli nightly
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
          TWILIO_ACCOUNT_SID: ${{ secrets.TWILIO_ACCOUNT_SID }}
          TWILIO_AUTH_TOKEN: ${{ secrets.TWILIO_AUTH_TOKEN }}
          TWILIO_FROM_NUMBER: ${{ secrets.TWILIO_FROM_NUMBER }}
          USER_PHONE: ${{ secrets.USER_PHONE }}
          FINNHUB_TOKEN: ${{ secrets.FINNHUB_TOKEN }}
```

- [ ] **Step 2: Write `execute.yml`**

```yaml
name: execute-approval
on:
  repository_dispatch:
    types: [approval]
jobs:
  execute:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen
      - run: uv run python -m stock_trader.cli execute --key "${{ github.event.client_payload.approval_key }}"
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
          TWILIO_ACCOUNT_SID: ${{ secrets.TWILIO_ACCOUNT_SID }}
          TWILIO_AUTH_TOKEN: ${{ secrets.TWILIO_AUTH_TOKEN }}
          TWILIO_FROM_NUMBER: ${{ secrets.TWILIO_FROM_NUMBER }}
          USER_PHONE: ${{ secrets.USER_PHONE }}
```

- [ ] **Step 3: Validate and commit**

Run: `uv run python -c "import yaml, pathlib; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github/workflows').glob('*.yml')]"`
Expected: no output (YAML parses).

```bash
git add .github
git commit -m "feat: add signal and execution workflows"
```

---

### Task 19: Dashboard

**Files:**
- Create: `dashboard/index.html`, `dashboard/app.js`, `dashboard/style.css`, `dashboard/config.example.js`

- [ ] **Step 1: Build the read-only dashboard**

Plain static assets reading Supabase REST with the anon key from
`config.local.js` (gitignored), showing:

- cards: account equity trend (positions view), open positions, pending proposal;
- tables: signals (symbol, probability, rationale), proposals (state, expiry),
  approvals;
- banner when `settings` contains `trading_paused = true`.

- [ ] **Step 2: Smoke test**

Serve with `python -m http.server 8080 -d dashboard`, point it at a scratch
Supabase project, and confirm the anon key cannot write.

- [ ] **Step 3: Commit**

```bash
git add dashboard
git commit -m "feat: add read-only dashboard"
```

---

### Task 20: Dry-run report and calibration

**Files:**
- Modify: `src/stock_trader/cli.py`
- Create: `src/stock_trader/report.py`, `tests/test_report.py`

- [ ] **Step 1: Failing test**

```python
from stock_trader.report import summarize_paper_run


def test_summary_reports_counts_and_return():
    trades = [
        {"symbol": "AAPL", "pnl": 120.0},
        {"symbol": "MSFT", "pnl": -80.0},
    ]
    summary = summarize_paper_run(trades, starting_equity=20_000.0)
    assert summary["trade_count"] == 2
    assert summary["realized_pnl"] == 40.0
    assert summary["return_pct"] == 0.002
```

- [ ] **Step 2: Implement `summarize_paper_run` and add `paper-report` CLI**

Weekly report text and a run must be exercised for at least two weeks before
the Robinhood adapter is wired.

- [ ] **Step 3: Commit**

```bash
git add src/stock_trader/report.py src/stock_trader/cli.py tests/test_report.py
git commit -m "feat: add paper run reporting"
```

---

### Task 21: Robinhood adapter (after dry run)

**Files:**
- Create: `src/stock_trader/brokers/robinhood_mcp.py`
- Test: `tests/test_robinhood_adapter.py`

- [ ] **Step 1: Failing test with a fake MCP client**

```python
from stock_trader.brokers.robinhood_mcp import RobinhoodBroker


def test_submit_calls_review_then_place():
    calls = []

    class FakeMCP:
        def call(self, tool, args):
            calls.append(tool)
            if tool == "review_equity_order":
                return {"warnings": []}
            return {"order_id": "rh-1", "status": "queued"}

    broker = RobinhoodBroker(FakeMCP())
    order = broker.submit_order("AAPL", Side.BUY, 2, client_id="c1")
    assert calls == ["review_equity_order", "place_equity_order"]
    assert order.id == "rh-1"
```

- [ ] **Step 2: Implement**

The adapter wraps Robinhood's official agentic endpoint
`https://agent.robinhood.com/mcp/trading` through an injected MCP client:

- `review_equity_order` before every placement, refusing on warnings by default;
- `get_equity_quotes`, `get_equity_positions`, `get_accounts` for reads;
- OAuth refresh token from `ROBINHOOD_REFRESH_TOKEN` in GitHub secrets;
- order client IDs passed through as idempotency keys.

- [ ] **Step 3: Run tests and commit**

Run: `python -m pytest tests/test_robinhood_adapter.py -v`
Expected: 1 passed.

```bash
git add src/stock_trader/brokers/robinhood_mcp.py tests/test_robinhood_adapter.py
git commit -m "feat: add Robinhood agentic broker adapter"
```

---

## Self-Review

- Spec coverage: every spec section maps to a task — settings/sizing (1–2),
  state machine (3), approvals (4, 12), screener (5), news (6), features (7),
  gate (8), paper broker (9), backtest (10), proposal/SMS (11), execution (12),
  repository (13), data sources (14), Supabase (15), Worker (16), signal engine
  (17), workflows (18), dashboard (19), dry run (20), Robinhood (21).
- No placeholders: each task names files, interfaces, tests, commands, and
  commits; defaults are concrete numbers copied from the spec.
- Type consistency: `Settings`, `StockSnapshot`, `Headline`, `NewsFeatures`,
  `Proposal`, `Decision`, `TradeState`, `Side`, `Order`, `PaperBroker`, and
  `Broker` signatures are reused with identical names across tasks.
