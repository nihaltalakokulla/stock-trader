import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from stock_trader.config import Settings
from stock_trader.data.prices import fetch_yfinance_frame
from stock_trader.domain.models import NewsFeatures
from stock_trader.model import FEATURE_COLUMNS, RankingModel, train_ranker
from stock_trader.pipeline import build_feature_row, build_snapshot, build_training_panel
from stock_trader.screener import passes_screener
from stock_trader.strategy_backtest import Signal, simulate_portfolio, split_indices
from stock_trader.universe import BENCHMARK, DEFAULT_UNIVERSE

THRESHOLDS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75)
EMPTY_NEWS = NewsFeatures(sentiment=0.0, headline_count=0, shock=False)


def fetch_frames(period: str, max_symbols: int | None) -> dict[str, pd.DataFrame]:
    symbols = list(DEFAULT_UNIVERSE[:max_symbols] if max_symbols else DEFAULT_UNIVERSE)
    symbols.append(BENCHMARK)
    frames: dict[str, pd.DataFrame] = {}
    for position, symbol in enumerate(symbols, start=1):
        try:
            frame = fetch_yfinance_frame(symbol, period=period)
        except Exception as error:
            print(f"skip {symbol}: {error}", flush=True)
            continue
        if len(frame) > 260:
            frames[symbol] = frame
        print(
            f"fetched {symbol} ({len(frame)} rows, {position}/{len(symbols)})",
            flush=True,
        )
    if BENCHMARK not in frames:
        raise RuntimeError("benchmark data unavailable")
    return frames


def train_on(frames: dict[str, pd.DataFrame], end: pd.Timestamp) -> RankingModel:
    truncated = {
        symbol: frame.loc[:end]
        for symbol, frame in frames.items()
        if symbol != BENCHMARK
    }
    panel = build_training_panel(
        truncated, benchmark=None, forward_days=21, step=21, min_history=220
    )
    panel = panel.replace([float("inf"), float("-inf")], pd.NA).dropna(
        subset=list(FEATURE_COLUMNS) + ["label"]
    )
    if panel["label"].nunique() < 2 or len(panel) < 100:
        raise RuntimeError(f"not enough training rows: {len(panel)}")
    return train_ranker(panel.loc[:, list(FEATURE_COLUMNS)], panel["label"])


def score_dates(
    frames: dict[str, pd.DataFrame],
    model: RankingModel,
    start: pd.Timestamp,
    end: pd.Timestamp,
    settings: Settings,
) -> pd.DataFrame:
    benchmark = frames[BENCHMARK]
    dates = benchmark.loc[start:end].index
    scores: dict[pd.Timestamp, dict[str, float]] = {}
    for current in dates:
        rows: dict[str, dict] = {}
        bench_history = benchmark.loc[:current]
        for symbol, frame in frames.items():
            if symbol == BENCHMARK:
                continue
            history = frame.loc[:current]
            if len(history) < 230:
                continue
            try:
                snapshot = build_snapshot(symbol, history)
            except ValueError:
                continue
            if not passes_screener(snapshot, settings):
                continue
            rows[symbol] = build_feature_row(
                history, EMPTY_NEWS, benchmark=bench_history
            )
        if not rows:
            continue
        matrix = pd.DataFrame.from_dict(rows, orient="index")
        probabilities = model.predict_proba(matrix)
        scores[current] = {
            symbol: float(probability)
            for symbol, probability in zip(matrix.index, probabilities)
        }
    return pd.DataFrame.from_dict(scores, orient="index")


def signals_from_scores(
    scores: pd.DataFrame, threshold: float
) -> list[Signal]:
    signals: list[Signal] = []
    for current, row in scores.iterrows():
        row = row.dropna()
        if row.empty:
            continue
        symbol = row.idxmax()
        probability = float(row.max())
        if probability >= threshold:
            signals.append(Signal(symbol, current, probability))
    return signals


def warm_slice(
    frames: dict[str, pd.DataFrame], start: pd.Timestamp, end: pd.Timestamp
) -> dict[str, pd.DataFrame]:
    warm_start = start - timedelta(days=60)
    return {
        symbol: frame.loc[warm_start:end]
        for symbol, frame in frames.items()
        if len(frame.loc[warm_start:end]) > 0
    }


def run(period: str, max_symbols: int | None, output: Path) -> dict:
    settings = Settings()
    frames = fetch_frames(period, max_symbols)
    calendar = frames[BENCHMARK].index
    _, train_end, val_end, total = split_indices(len(calendar))
    train_date = calendar[train_end - 1]
    val_start = calendar[train_end]
    val_date = calendar[val_end - 1]
    test_start = calendar[val_end]
    test_date = calendar[-1]
    print(
        f"split: train through {train_date.date()} | "
        f"validate {val_start.date()}..{val_date.date()} | "
        f"test {test_start.date()}..{test_date.date()} ({total} sessions)",
        flush=True,
    )

    train_model = train_on(frames, train_date)
    print("scoring validation dates once...", flush=True)
    validation_scores = score_dates(
        frames, train_model, val_start, val_date, settings
    )
    validation_rows = []
    best = None
    for threshold in THRESHOLDS:
        signals = signals_from_scores(validation_scores, threshold)
        report = simulate_portfolio(
            warm_slice(frames, val_start, val_date),
            signals,
            starting_cash=settings.paper_starting_cash,
            risk_pct=settings.risk_per_trade,
            max_positions=settings.max_positions,
            hold_days=21,
        )
        row = {"threshold": threshold, **report.metrics}
        validation_rows.append(row)
        print(
            f"validate {threshold:.2f}: return {row['total_return']:+.2%}, "
            f"trades {int(row['trades'])}, maxDD {row['max_drawdown']:.2%}",
            flush=True,
        )
        if best is None or (
            report.metrics["total_return"], report.metrics["sharpe"]
        ) > (
            best[1].metrics["total_return"], best[1].metrics["sharpe"]
        ):
            best = (threshold, report)

    chosen_threshold = best[0]
    print(
        f"chosen threshold from validation: {chosen_threshold:.2f}",
        flush=True,
    )

    retrained = train_on(frames, val_date)
    print("scoring held-out test dates...", flush=True)
    test_scores = score_dates(
        frames, retrained, test_start, test_date, settings
    )
    test_signals = signals_from_scores(test_scores, chosen_threshold)
    test_report = simulate_portfolio(
        warm_slice(frames, test_start, test_date),
        test_signals,
        starting_cash=settings.paper_starting_cash,
        risk_pct=settings.risk_per_trade,
        max_positions=settings.max_positions,
        hold_days=21,
    )
    spy = frames[BENCHMARK].loc[test_start:test_date]["Close"]
    benchmark_return = float(spy.iloc[-1] / spy.iloc[0] - 1.0)

    daily = test_report.equity_curve.pct_change().dropna()
    result = {
        "generated": date.today().isoformat(),
        "period": period,
        "data_source": "yfinance (10s timeout) with Yahoo chart fallback",
        "symbols": len([s for s in frames if s != BENCHMARK]),
        "split": {
            "train_end": train_date.date().isoformat(),
            "validation_start": val_start.date().isoformat(),
            "validation_end": val_date.date().isoformat(),
            "test_start": test_start.date().isoformat(),
            "test_end": test_date.date().isoformat(),
        },
        "validation": validation_rows,
        "chosen_threshold": chosen_threshold,
        "test": {
            **test_report.metrics,
            "benchmark_return": benchmark_return,
            "excess_return": test_report.metrics["total_return"] - benchmark_return,
            "annualized_volatility": (
                float(daily.std(ddof=0) * (252 ** 0.5))
                if len(daily) > 1
                else 0.0
            ),
        },
        "caveats": [
            "News features are zero in this backtest: free historical news was not "
            "available, so the news half of the hybrid model is not validated here.",
            "Universe is today's liquid large caps (survivorship bias).",
            "Fixed 21-session hold with ATR stop approximates the live exit rules.",
            "Close-price fills with 0.1% cost per side; real slippage may be worse.",
            "Threshold was selected on validation and reported once on the held-out "
            "test window; still one sample, not a guarantee.",
            "Predicted probabilities cluster high: thresholds 0.50-0.65 produced "
            "identical portfolios, so the confidence gate is not yet calibrated.",
        ],
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    output.write_text(render_markdown(result, test_report), encoding="utf-8")
    print(f"wrote {output}", flush=True)
    return result


def render_markdown(result: dict, report) -> str:
    test = result["test"]
    lines = [
        "# Stock Trader Walk-Forward Backtest",
        "",
        f"Generated {result['generated']} · {result['symbols']} symbols · "
        f"{result['period']} daily data",
        f"Data source: {result['data_source']}",
        "",
        "## Split",
        "",
        f"- Train through **{result['split']['train_end']}**",
        f"- Validation **{result['split']['validation_start']} → "
        f"{result['split']['validation_end']}**",
        f"- Held-out test **{result['split']['test_start']} → "
        f"{result['split']['test_end']}**",
        "",
        "## Validation threshold sweep",
        "",
        "| Threshold | Return | Sharpe | Max DD | Trades |",
        "|---|---|---|---|---|",
    ]
    for row in result["validation"]:
        lines.append(
            f"| {row['threshold']:.2f} | {row['total_return']:+.2%} | "
            f"{row['sharpe']:.2f} | {row['max_drawdown']:.2%} | "
            f"{int(row['trades'])} |"
        )
    lines += [
        "",
        f"Chosen on validation: **{result['chosen_threshold']:.2f}**",
        "",
        "## Held-out test",
        "",
        "| Metric | Strategy | SPY buy-and-hold |",
        "|---|---|---|",
        f"| Total return | {test['total_return']:+.2%} | "
        f"{test['benchmark_return']:+.2%} |",
        f"| Excess return | {test['excess_return']:+.2%} | — |",
        f"| Sharpe (daily→annualized) | {test['sharpe']:.2f} | — |",
        f"| Max drawdown | {test['max_drawdown']:.2%} | — |",
        f"| Win rate | {test['win_rate']:.1%} | — |",
        f"| Profit factor | {test['profit_factor']:.2f} | — |",
        f"| Trades | {int(test['trades'])} | — |",
        f"| Max concurrent positions | {int(test['max_open_positions'])} | — |",
        "",
        "## Caveats",
        "",
    ]
    lines += [f"- {caveat}" for caveat in result["caveats"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="5y")
    parser.add_argument("--max-symbols", type=int, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(f"docs/backtests/{date.today().isoformat()}-backtest.md"),
    )
    args = parser.parse_args()
    run(args.period, args.max_symbols, args.output)


if __name__ == "__main__":
    main()
