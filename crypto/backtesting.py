"""Event-driven OHLCV backtester with next-bar execution and explicit costs.

This is a research simulator, not a broker emulator. If stop and target are both
inside one candle, stop is assumed to execute first. Stop gaps fill at the worse
of the stop and bar open. Strategy decisions only see candles up to the decision
bar; entries cannot fill on that same bar.
"""
from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_DOWN
from statistics import mean, pstdev
from .models import D, RiskLimits, Signal
from .risk import evaluate


@dataclass
class BacktestConfig:
    initial_cash: Decimal = Decimal("10000")
    risk_fraction: Decimal = Decimal("0.0025")
    max_notional_fraction: Decimal = Decimal("0.10")
    fee_rate: Decimal = Decimal("0.001")
    slippage_bps: Decimal = Decimal("5")
    participation_rate: Decimal = Decimal("0.02")
    funding_by_timestamp: dict = None

    def __post_init__(self):
        self.initial_cash = D(self.initial_cash)
        self.risk_fraction = D(self.risk_fraction)
        self.max_notional_fraction = D(self.max_notional_fraction)
        self.fee_rate = D(self.fee_rate)
        self.slippage_bps = D(self.slippage_bps)
        self.participation_rate = D(self.participation_rate)
        if self.initial_cash <= 0 or not (0 < self.participation_rate <= 1):
            raise ValueError("initial_cash must be positive and participation_rate in (0, 1]")
        if min(self.risk_fraction, self.max_notional_fraction, self.fee_rate, self.slippage_bps) < 0:
            raise ValueError("cost and risk parameters cannot be negative")
        if self.risk_fraction > 1 or self.max_notional_fraction > 1 or self.fee_rate >= 1:
            raise ValueError("risk fractions must be <= 1 and fee_rate must be < 1")


def _fill_price(price, side, bps):
    slip = bps / D("10000")
    return price * (D("1") + slip if side == "buy" else D("1") - slip)


def _metrics(trades, equity_curve, initial):
    returns = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]["equity"]
        if prev:
            returns.append(float(equity_curve[i]["equity"] / prev - 1))
    peaks, max_dd = float(initial), 0.0
    for point in equity_curve:
        value = float(point["equity"])
        peaks = max(peaks, value)
        if peaks:
            max_dd = max(max_dd, (peaks - value) / peaks)
    pnls = [float(t["net_pnl"]) for t in trades]
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]
    gross_win, gross_loss = sum(wins), abs(sum(losses))
    avg = mean(returns) if returns else 0.0
    vol = pstdev(returns) if len(returns) > 1 else 0.0
    downside = [x for x in returns if x < 0]
    down_vol = (sum(x * x for x in downside) / len(downside)) ** 0.5 if downside else 0.0
    seconds = []
    for i in range(1, len(equity_curve)):
        try:
            from datetime import datetime
            a = datetime.fromisoformat(equity_curve[i - 1]["timestamp"])
            b = datetime.fromisoformat(equity_curve[i]["timestamp"])
            seconds.append((b - a).total_seconds())
        except (TypeError, ValueError):
            pass
    step = sorted(x for x in seconds if x > 0)
    periods_per_year = (365 * 24 * 60) if not step else (365 * 24 * 60 * 60 / step[len(step) // 2])
    return {
        "trades": len(trades), "win_rate": len(wins) / len(trades) if trades else 0.0,
        "profit_factor": gross_win / gross_loss if gross_loss else None,
        "profit_factor_unbounded": bool(gross_win and not gross_loss),
        "expectancy": mean(pnls) if pnls else 0.0, "max_drawdown": max_dd,
        "sharpe_annualized": (avg / vol * periods_per_year ** 0.5) if vol else 0.0,
        "sortino_annualized": (avg / down_vol * periods_per_year ** 0.5) if down_vol else 0.0,
        "periods_per_year_assumption": periods_per_year,
        "gross_profit": gross_win, "gross_loss": gross_loss,
        "net_profit": sum(pnls), "risk_of_ruin": None,
        "note": "Annualized ratios assume one-minute observations only; interpret cautiously for other timeframes."
    }


def run_backtest(candles, strategy, instrument, config=None, start_index=0):
    cfg = config or BacktestConfig()
    bars = sorted(candles, key=lambda c: c.timestamp)
    if len(bars) < 3:
        raise ValueError("at least three candles are required")
    if start_index < 0 or start_index >= len(bars) - 1:
        raise ValueError("start_index must leave at least one candle for execution")
    if any(bars[i].timestamp == bars[i - 1].timestamp for i in range(1, len(bars))):
        raise ValueError("duplicate candle timestamps")
    cash = cfg.initial_cash
    position = None
    trades, curve = [], []
    i = start_index
    while i < len(bars) - 1:
        bar = bars[i]
        if position is None:
            signal = strategy.evaluate(bars[:i + 1])
            if signal is None:
                curve.append({"timestamp": bar.timestamp.isoformat(), "equity": cash})
                i += 1
                continue
            next_bar = bars[i + 1]
            entry = _fill_price(next_bar.open, signal.side, cfg.slippage_bps)
            # Re-anchor the signal to the actual next-bar opening price. Stop and
            # target stay fixed from the original setup, avoiding look-ahead.
            adjusted = Signal(signal.strategy, signal.symbol, signal.side, next_bar.timestamp,
                              entry, signal.stop_price, signal.take_profit, signal.rationale,
                              signal.invalidation, signal.metadata)
            limits = RiskLimits(risk_fraction=cfg.risk_fraction,
                                max_notional_fraction=cfg.max_notional_fraction,
                                max_data_age_seconds=60 * 60 * 24,
                                slippage_bps=cfg.slippage_bps)
            risk_instrument = replace(instrument, taker_fee=cfg.fee_rate)
            decision = evaluate(adjusted, risk_instrument, cash, limits, now=next_bar.timestamp,
                                available_balance=cash)
            if not decision.allowed:
                curve.append({"timestamp": bar.timestamp.isoformat(), "equity": cash})
                i += 1
                continue
            max_qty = next_bar.volume * cfg.participation_rate
            qty = min(decision.quantity, (max_qty / instrument.quantity_step).to_integral_value(
                rounding=ROUND_DOWN) * instrument.quantity_step)
            if qty < instrument.min_quantity:
                curve.append({"timestamp": bar.timestamp.isoformat(), "equity": cash})
                i += 1
                continue
            notional = qty * entry * instrument.contract_multiplier
            fee = notional * cfg.fee_rate
            is_perpetual = instrument.asset_class == "crypto_perpetual"
            if not is_perpetual and signal.side == "buy" and notional + fee > cash:
                curve.append({"timestamp": bar.timestamp.isoformat(), "equity": cash})
                i += 1
                continue
            cash -= fee
            if not is_perpetual and signal.side == "buy":
                cash -= notional
            position = {"signal": signal, "side": signal.side, "qty": qty,
                        "entry": entry, "entry_fee": fee, "entry_time": next_bar.timestamp,
                        "entry_index": i + 1, "entry_notional": notional,
                        "stop": signal.stop_price, "target": signal.take_profit,
                        "funding_pnl": D("0")}
            i += 1
            continue

        bar = bars[i]
        funding = (cfg.funding_by_timestamp or {}).get(bar.timestamp.isoformat())
        if funding is not None and instrument.asset_class == "crypto_perpetual":
            funding_cash = position["qty"] * bar.close * instrument.contract_multiplier * D(funding)
            funding_pnl = funding_cash if position["side"] == "sell" else -funding_cash
            cash += funding_pnl
            position["funding_pnl"] += funding_pnl
        side = position["side"]
        stop_hit = (bar.low <= position["stop"]) if side == "buy" else (bar.high >= position["stop"])
        target_hit = False
        if position["target"] is not None:
            target_hit = (bar.high >= position["target"]) if side == "buy" else (bar.low <= position["target"])
        exit_reason, raw_exit = None, None
        if stop_hit:
            exit_reason = "stop"
            raw_exit = min(bar.open, position["stop"]) if side == "buy" else max(bar.open, position["stop"])
        elif target_hit:
            exit_reason = "target"
            raw_exit = position["target"]
        if exit_reason:
            exit_side = "sell" if side == "buy" else "buy"
            exit_price = _fill_price(raw_exit, exit_side, cfg.slippage_bps)
            exit_notional = position["qty"] * exit_price * instrument.contract_multiplier
            exit_fee = exit_notional * cfg.fee_rate
            gross = ((exit_price - position["entry"]) if side == "buy"
                     else (position["entry"] - exit_price)) * position["qty"] * instrument.contract_multiplier
            net = gross - position["entry_fee"] - exit_fee + position["funding_pnl"]
            if instrument.asset_class == "crypto_perpetual":
                cash += gross
            elif side == "buy":
                cash += exit_notional
            cash -= exit_fee
            trades.append({
                "strategy": position["signal"].strategy, "symbol": instrument.symbol,
                "side": side, "qty": str(position["qty"]), "entry_time": position["entry_time"].isoformat(),
                "exit_time": bar.timestamp.isoformat(), "entry": str(position["entry"]),
                "exit": str(exit_price), "gross_pnl": str(gross),
                "fees": str(position["entry_fee"] + exit_fee),
                "funding_pnl": str(position["funding_pnl"]), "net_pnl": str(net),
                "reason": exit_reason, "partial_fill": position["qty"] < decision.quantity
            })
            position = None
        mark = cash
        if position is not None:
            if instrument.asset_class == "crypto_perpetual":
                unrealized = ((bar.close - position["entry"]) if position["side"] == "buy"
                              else (position["entry"] - bar.close))
                mark += position["qty"] * unrealized * instrument.contract_multiplier
            elif position["side"] == "buy":
                mark += position["qty"] * bar.close * instrument.contract_multiplier
        curve.append({"timestamp": bar.timestamp.isoformat(), "equity": mark})
        i += 1

    if position is not None:
        last = bars[-1]
        side = position["side"]
        exit_side = "sell" if side == "buy" else "buy"
        exit_price = _fill_price(last.close, exit_side, cfg.slippage_bps)
        notional = position["qty"] * exit_price * instrument.contract_multiplier
        fee = notional * cfg.fee_rate
        gross = ((exit_price - position["entry"]) if side == "buy"
                 else (position["entry"] - exit_price)) * position["qty"] * instrument.contract_multiplier
        net = gross - position["entry_fee"] - fee + position["funding_pnl"]
        if instrument.asset_class == "crypto_perpetual":
            cash += gross
        elif side == "buy":
            cash += notional
        cash -= fee
        trades.append({"strategy": position["signal"].strategy, "symbol": instrument.symbol,
                       "side": side, "qty": str(position["qty"]), "entry_time": position["entry_time"].isoformat(),
                       "exit_time": last.timestamp.isoformat(), "entry": str(position["entry"]),
                       "exit": str(exit_price), "gross_pnl": str(gross), "fees": str(position["entry_fee"] + fee),
                       "funding_pnl": str(position["funding_pnl"]), "net_pnl": str(net),
                       "reason": "end_of_data", "partial_fill": False})
    if not curve or curve[-1]["timestamp"] != bars[-1].timestamp.isoformat():
        curve.append({"timestamp": bars[-1].timestamp.isoformat(), "equity": cash})
    else:
        curve[-1]["equity"] = cash
    return {"instrument": instrument.symbol, "venue": instrument.venue,
            "initial_cash": str(cfg.initial_cash), "final_cash": str(cash),
            "trades": trades, "equity_curve": curve,
            "metrics": _metrics(trades, curve, cfg.initial_cash),
            "disclaimer": "Historical simulation only. Not live performance or a forecast."}
