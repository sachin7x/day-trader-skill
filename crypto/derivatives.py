"""Perpetual-market diagnostics from explicitly observed exchange data.

This module does not manufacture liquidation clusters or infer exact leverage
levels. Any pattern beyond raw fields is labelled as a hypothesis.
"""
from dataclasses import dataclass
from datetime import datetime
from statistics import mean, pstdev
from .models import D


@dataclass(frozen=True)
class DerivativesSnapshot:
    exchange: str
    symbol: str
    timestamp: datetime
    mark_price: D
    index_price: D
    open_interest: D
    funding_rate: D
    long_short_ratio: object = None
    observed_liquidation_count: int = None

    def __post_init__(self):
        if self.timestamp.tzinfo is None:
            raise ValueError("derivatives timestamp must be timezone-aware")
        for name in ("mark_price", "index_price", "open_interest", "funding_rate"):
            object.__setattr__(self, name, D(getattr(self, name)))
        if self.mark_price <= 0 or self.index_price <= 0 or self.open_interest < 0:
            raise ValueError("invalid derivatives snapshot values")


def analyze(snapshot, previous=None, funding_history=None, extreme_z=2.0):
    """Return observed metrics and carefully labelled hypotheses."""
    basis_pct = (snapshot.mark_price / snapshot.index_price - 1) * 100
    observed = {
        "exchange": snapshot.exchange, "symbol": snapshot.symbol,
        "timestamp": snapshot.timestamp.isoformat(),
        "mark_price": str(snapshot.mark_price), "index_price": str(snapshot.index_price),
        "open_interest": str(snapshot.open_interest), "funding_rate": str(snapshot.funding_rate),
        "basis_pct": str(basis_pct), "long_short_ratio": snapshot.long_short_ratio,
        "observed_liquidation_count": snapshot.observed_liquidation_count
    }
    flags, evidence = [], []
    if funding_history and len(funding_history) >= 10:
        hist = [float(x) for x in funding_history]
        sd = pstdev(hist)
        z = (float(snapshot.funding_rate) - mean(hist)) / sd if sd else 0.0
        observed["funding_zscore"] = round(z, 3)
        if abs(z) >= extreme_z:
            flags.append("funding_extreme")
            evidence.append("current funding is statistically unusual versus supplied history")
    if previous is not None:
        if previous.timestamp >= snapshot.timestamp:
            raise ValueError("previous snapshot must be older")
        oi_change = snapshot.open_interest / previous.open_interest - 1 if previous.open_interest else None
        price_change = snapshot.mark_price / previous.mark_price - 1
        observed["open_interest_change_pct"] = str(oi_change * 100) if oi_change is not None else None
        observed["mark_price_change_pct"] = str(price_change * 100)
        if oi_change is not None and oi_change > 0 and price_change < 0:
            flags.append("open_interest_up_price_down")
            evidence.append("open interest rose while mark price fell")
        elif oi_change is not None and oi_change > 0 and price_change > 0:
            flags.append("open_interest_up_price_up")
            evidence.append("open interest and mark price rose together")
    if snapshot.observed_liquidation_count is not None:
        evidence.append("liquidation count is an observed exchange/provider field")
    return {
        "observed": observed,
        "flags": flags,
        "hypotheses": evidence,
        "warning": "Flags are context, not trade signals. Exact liquidation clusters and leverage concentrations are not inferred."
    }
