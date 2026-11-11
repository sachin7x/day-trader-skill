"""Out-of-sample walk-forward evaluation and bootstrap Monte Carlo diagnostics."""
from random import Random
from statistics import mean
from decimal import Decimal

from .models import D
from .backtesting import run_backtest


def _percentile(values, pct):
    ordered = sorted(values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * pct
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def monte_carlo(trades, initial_equity, paths=10000, seed=42, ruin_fraction=0.5):
    """Bootstrap trade PnL with replacement; outputs scenario frequencies, not forecasts."""
    pnls = [float(D(t["net_pnl"])) for t in trades]
    equity0 = float(D(initial_equity))
    ruin_fraction = float(ruin_fraction)
    if not pnls:
        raise ValueError("at least one completed trade is required")
    if equity0 <= 0 or paths <= 0 or not 0 < ruin_fraction < 1:
        raise ValueError("invalid Monte Carlo configuration")
    rng = Random(seed)
    terminal, drawdowns = [], []
    ruined = 0
    for _ in range(paths):
        equity = peak = equity0
        max_dd = 0.0
        hit_ruin = False
        for _ in range(len(pnls)):
            equity += rng.choice(pnls)
            peak = max(peak, equity)
            if peak > 0:
                max_dd = max(max_dd, (peak - equity) / peak)
            if equity <= equity0 * ruin_fraction:
                hit_ruin = True
        terminal.append(equity)
        drawdowns.append(max_dd)
        ruined += int(hit_ruin)
    return {
        "paths": paths, "seed": seed, "trade_count": len(pnls),
        "terminal_equity_p05": _percentile(terminal, 0.05),
        "terminal_equity_median": _percentile(terminal, 0.50),
        "terminal_equity_p95": _percentile(terminal, 0.95),
        "max_drawdown_p95": _percentile(drawdowns, 0.95),
        "empirical_ruin_frequency": ruined / paths,
        "ruin_threshold_equity": equity0 * ruin_fraction,
        "method": "bootstrap completed trade net PnL with replacement",
        "warning": "Scenario frequencies are conditional on the supplied trade sample; they are not predictive probabilities."
    }


def walk_forward(candles, strategy_factory, instrument, config=None,
                 warmup_bars=200, test_bars=100, step_bars=None):
    """Evaluate fixed strategy rules on rolling unseen segments.

    No parameter optimization is performed. Each fold uses preceding candles
    only as indicator warmup and resets its paper equity to the config's
    initial_cash. Use a strategy factory to create a fresh strategy per fold.
    """
    bars = sorted(candles, key=lambda c: c.timestamp)
    step = test_bars if step_bars is None else step_bars
    if not callable(strategy_factory):
        raise TypeError("strategy_factory must be callable")
    if warmup_bars < 1 or test_bars < 1 or step < 1:
        raise ValueError("warmup_bars, test_bars and step_bars must be positive")
    if len(bars) <= warmup_bars + 1:
        raise ValueError("not enough candles for warmup and out-of-sample testing")
    folds, start = [], warmup_bars
    while start < len(bars) - 1:
        end = min(start + test_bars - 1, len(bars) - 1)
        result = run_backtest(bars[:end + 1], strategy_factory(), instrument,
                              config=config, start_index=start)
        folds.append({
            "fold": len(folds) + 1,
            "out_of_sample_start": bars[start].timestamp.isoformat(),
            "out_of_sample_end": bars[end].timestamp.isoformat(),
            "warmup_bars": start, "test_bars": end - start + 1,
            "metrics": result["metrics"], "trades": result["trades"],
            "initial_cash": result["initial_cash"], "final_cash": result["final_cash"]
        })
        start += step
    all_trades = [trade for fold in folds for trade in fold["trades"]]
    return {
        "folds": folds,
        "fold_count": len(folds),
        "out_of_sample_trade_count": len(all_trades),
        "aggregate_net_pnl": str(sum((D(t["net_pnl"]) for t in all_trades), Decimal("0"))),
        "warning": "Fold equity resets independently. Aggregate PnL is a sum of fold results, not a continuously compounded portfolio curve."
    }
