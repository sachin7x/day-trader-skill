"""Evidence-led trade brief generator; deterministic and confidence-free."""
from datetime import datetime, timezone
import math

from .models import Signal, D


def build_trade_brief(signal, risk_decision, market, oos_performance=None,
                      derivatives=None, news=None, min_oos_trades=30,
                      max_oos_drawdown=0.20, now=None, max_data_age_seconds=30):
    """Build a transparent brief. Missing evidence lowers the decision to WATCH."""
    market = market or {}
    derivatives = derivatives or {}
    news = news or []
    reasons_for, reasons_against, invalidation = [], [], []
    if signal is None:
        return {
            "decision": "NO TRADE", "symbol": market.get("symbol"),
            "reasons_for": [], "reasons_against": ["No deterministic strategy produced a setup."],
            "invalidation_conditions": [], "historical_performance": oos_performance,
            "news": news, "derivatives": derivatives
        }
    if not isinstance(signal, Signal):
        raise TypeError("signal must be a Signal")
    if not market.get("timestamp") or market.get("price") is None:
        return {
            "decision": "BLOCKED BY RISK", "symbol": signal.symbol,
            "reasons_for": list(signal.rationale),
            "reasons_against": ["Current market price or timestamp is missing."],
            "invalidation_conditions": list(signal.invalidation),
            "historical_performance": oos_performance, "news": news,
            "derivatives": derivatives
        }
    try:
        price = float(market["price"])
        stamp = market["timestamp"]
        if isinstance(stamp, str):
            stamp = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if not isinstance(stamp, datetime) or stamp.tzinfo is None:
            raise ValueError("market timestamp must be timezone-aware")
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or max_data_age_seconds <= 0:
            raise ValueError("clock must be timezone-aware and max_data_age_seconds positive")
        age = (now - stamp).total_seconds()
        if not math.isfinite(price) or price <= 0 or age < -5 or age > max_data_age_seconds:
            raise ValueError("market snapshot price is invalid or data is stale")
    except (TypeError, ValueError, OverflowError) as exc:
        return {
            "decision": "BLOCKED BY RISK", "symbol": signal.symbol,
            "reasons_for": list(signal.rationale),
            "reasons_against": [str(exc)],
            "invalidation_conditions": list(signal.invalidation),
            "historical_performance": oos_performance, "news": news,
            "derivatives": derivatives
        }
    if market.get("symbol") and market["symbol"].upper() != signal.symbol:
        return {
            "decision": "BLOCKED BY RISK", "symbol": signal.symbol,
            "reasons_for": list(signal.rationale),
            "reasons_against": ["Market snapshot symbol does not match the strategy signal."],
            "invalidation_conditions": list(signal.invalidation),
            "historical_performance": oos_performance, "news": news,
            "derivatives": derivatives
        }
    if risk_decision is None or not getattr(risk_decision, "allowed", False):
        reasons = list(getattr(risk_decision, "reasons", ()) or ())
        if not reasons:
            reasons = ["A passing pre-trade risk decision is required."]
        return {
            "decision": "BLOCKED BY RISK", "symbol": signal.symbol,
            "reasons_for": list(signal.rationale), "reasons_against": reasons,
            "invalidation_conditions": list(signal.invalidation),
            "historical_performance": oos_performance, "news": news,
            "derivatives": derivatives
        }

    reasons_for.extend(signal.rationale)
    if market.get("regime"):
        reasons_for.append("Market regime: %s" % market["regime"])
    if market.get("trend"):
        reasons_for.append("Observed trend: %s" % market["trend"])
        trend = str(market["trend"]).lower()
        if signal.side == "buy" and trend in ("down", "bearish", "downtrend"):
            reasons_against.append("Observed trend conflicts with the long setup.")
        if signal.side == "sell" and trend in ("up", "bullish", "uptrend"):
            reasons_against.append("Observed trend conflicts with the short setup.")
    regime = str(market.get("regime", "")).lower()
    if "sideways" in regime or "range" in regime:
        reasons_against.append("Market regime is range-bound; breakout/continuation evidence needs extra confirmation.")
    if market.get("volume_confirmed") is True:
        reasons_for.append("Volume confirmation is present in the supplied snapshot.")
    else:
        reasons_against.append("Volume confirmation is absent or unavailable.")

    oos = oos_performance or {}
    sample_is_oos = str(oos.get("sample_type", "")).lower() == "out_of_sample"
    trade_count = int(oos.get("trades", 0) or 0)
    expectancy = oos.get("expectancy")
    profit_factor = oos.get("profit_factor")
    drawdown = oos.get("max_drawdown")
    performance_valid = False
    if sample_is_oos and trade_count >= min_oos_trades:
        try:
            performance_valid = (float(expectancy) > 0 and float(profit_factor) > 1 and
                                 0 <= float(drawdown) <= max_oos_drawdown)
        except (TypeError, ValueError):
            performance_valid = False
    if performance_valid:
        reasons_for.append("Out-of-sample results meet the configured trade-count, expectancy, profit-factor and drawdown gates.")
    else:
        reasons_against.append("No sufficiently large, positive out-of-sample performance record passed the configured gates.")

    flags = set(derivatives.get("flags", []))
    if "funding_extreme" in flags:
        reasons_against.append("Observed funding is extreme versus its supplied history.")
    if signal.side == "buy" and "open_interest_up_price_down" in flags:
        reasons_against.append("Open interest rose while mark price fell, a caution for a long setup.")
    if signal.side == "sell" and "open_interest_up_price_up" in flags:
        reasons_against.append("Open interest rose while mark price rose, a caution for a short setup.")
    for item in news:
        if item.get("reliability") in ("low", "unverified"):
            reasons_against.append("News item has low or unverified source reliability: %s" % item.get("title", "untitled"))

    invalidation.extend(signal.invalidation)
    if not invalidation:
        invalidation.append("Strategy-specific invalidation conditions were not supplied.")
    if reasons_against:
        decision = "WATCH"
    elif performance_valid and market.get("volume_confirmed") is True:
        decision = "STRONG SETUP"
    else:
        decision = "WATCH"

    target = signal.take_profit
    risk_reward = None
    if target is not None:
        risk_reward = str(abs(target - signal.entry_reference) /
                          abs(signal.entry_reference - signal.stop_price))
    return {
        "decision": decision, "symbol": signal.symbol, "side": signal.side,
        "exchange": market.get("exchange"), "price": str(market["price"]),
        "market_timestamp": market["timestamp"], "strategy": signal.strategy,
        "market_regime": market.get("regime"), "trend": market.get("trend"),
        "entry_reference": str(signal.entry_reference), "stop_loss": str(signal.stop_price),
        "take_profit": str(target) if target is not None else None,
        "position_quantity": str(risk_decision.quantity),
        "estimated_max_loss": str(risk_decision.estimated_max_loss),
        "risk_reward": risk_reward, "reasons_for": reasons_for,
        "reasons_against": reasons_against, "invalidation_conditions": invalidation,
        "historical_performance": oos_performance, "news": news,
        "derivatives": derivatives,
        "confidence": None,
        "note": "No probability is generated. STRONG SETUP requires passed risk, volume confirmation and adequate positive out-of-sample evidence."
    }
