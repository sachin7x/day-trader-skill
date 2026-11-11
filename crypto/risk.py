"""Conservative, instrument-aware position sizing and pre-trade risk gate."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone

from .models import D, Instrument, RiskLimits, Signal


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    quantity: Decimal
    notional: Decimal
    estimated_max_loss: Decimal
    risk_fraction: Decimal
    reasons: tuple
    warnings: tuple = ()


def _floor_step(value, step):
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def evaluate(signal, instrument, equity, limits=None, now=None, current_daily_pnl=0,
             available_balance=None):
    """Size one signal. Returns BLOCK rather than guessing on missing/invalid data.

    Fees and slippage are charged on both entry and exit. Perpetual funding and
    liquidation buffers are not guessed here; those require venue-specific data.
    """
    limits = limits or RiskLimits()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    equity = D(equity)
    daily_pnl = D(current_daily_pnl)
    balance = equity if available_balance is None else D(available_balance)
    reasons, warnings = [], []
    if not isinstance(signal, Signal) or not isinstance(instrument, Instrument):
        raise TypeError("signal and instrument must use crypto domain models")
    if not instrument.is_trading_enabled:
        reasons.append("instrument is not enabled for trading")
    age = (now - signal.timestamp).total_seconds()
    if age < -5 or age > limits.max_data_age_seconds:
        reasons.append("signal timestamp is stale or in the future")
    if equity <= 0:
        reasons.append("account equity must be positive")
    if balance < 0:
        reasons.append("available balance cannot be negative")
    if instrument.asset_class == "crypto_spot" and signal.side != "buy":
        reasons.append("spot short selling is unsupported by this risk profile")
    if instrument.asset_class == "crypto_perpetual" and not limits.allow_leverage and limits.max_leverage > 1:
        warnings.append("leverage disabled; sizing is capped at 1x")
    if signal.side == "buy" and signal.stop_price >= signal.entry_reference:
        reasons.append("long stop must be below entry")
    if signal.side == "sell" and signal.stop_price <= signal.entry_reference:
        reasons.append("short stop must be above entry")
    if signal.take_profit is not None:
        if signal.side == "buy" and signal.take_profit <= signal.entry_reference:
            reasons.append("long target must be above entry")
        if signal.side == "sell" and signal.take_profit >= signal.entry_reference:
            reasons.append("short target must be below entry")
    if reasons:
        return RiskDecision(False, D("0"), D("0"), D("0"), D("0"), tuple(reasons), tuple(warnings))

    entry, stop = signal.entry_reference, signal.stop_price
    multiplier = instrument.contract_multiplier
    slip = limits.slippage_bps / D("10000")
    entry_fill = entry * (D("1") + slip if signal.side == "buy" else D("1") - slip)
    exit_fill = stop * (D("1") - slip if signal.side == "buy" else D("1") + slip)
    fee_rate = instrument.taker_fee
    per_unit_loss = abs(entry_fill - exit_fill) * multiplier
    per_unit_loss += (entry_fill + exit_fill) * multiplier * fee_rate
    if per_unit_loss <= 0:
        return RiskDecision(False, D("0"), D("0"), D("0"), D("0"),
                            ("computed per-unit loss is not positive",), tuple(warnings))

    risk_budget = equity * limits.risk_fraction
    daily_limit = equity * limits.max_daily_loss_fraction
    if daily_pnl <= -daily_limit:
        return RiskDecision(False, D("0"), D("0"), D("0"), D("0"),
                            ("daily loss limit has already been reached",), tuple(warnings))
    daily_remaining = max(D("0"), daily_limit + min(daily_pnl, D("0")))
    risk_budget = min(risk_budget, daily_remaining)
    max_notional = equity * limits.max_notional_fraction
    leverage = D("1") if not limits.allow_leverage else min(limits.max_leverage, instrument.max_leverage)
    max_notional = min(max_notional, balance * leverage)
    per_unit_notional = entry_fill * multiplier
    qty_by_risk = risk_budget / per_unit_loss
    qty_by_notional = max_notional / per_unit_notional
    qty = _floor_step(min(qty_by_risk, qty_by_notional), instrument.quantity_step)
    notional = qty * per_unit_notional
    estimated_loss = qty * per_unit_loss
    if qty < instrument.min_quantity:
        return RiskDecision(False, D("0"), D("0"), D("0"), D("0"),
                            ("risk budget or notional cap is below the venue minimum quantity",),
                            tuple(warnings))
    if estimated_loss > risk_budget or notional > max_notional:
        return RiskDecision(False, D("0"), D("0"), D("0"), D("0"),
                            ("rounded quantity exceeds a risk or notional limit",), tuple(warnings))
    if instrument.asset_class == "crypto_perpetual":
        warnings.append("funding, maintenance margin and liquidation distance require live venue metadata; not included")
    return RiskDecision(True, qty, notional, estimated_loss,
                        estimated_loss / equity, tuple(), tuple(warnings))
