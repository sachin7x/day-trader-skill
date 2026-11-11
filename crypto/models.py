"""Shared, validated domain models for crypto research and execution."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional


def D(value):
    """Convert values to Decimal without importing binary float noise."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    symbol: str = ""
    timeframe: str = ""

    def __post_init__(self):
        if self.timestamp.tzinfo is None:
            raise ValueError("candle timestamp must be timezone-aware")
        values = [D(self.open), D(self.high), D(self.low), D(self.close), D(self.volume)]
        if any(v <= 0 for v in values[:4]) or values[4] < 0:
            raise ValueError("OHLC must be positive and volume cannot be negative")
        o, h, l, c, _ = values
        if h < max(o, c, l) or l > min(o, c, h):
            raise ValueError("invalid OHLC range")
        for name, value in zip(("open", "high", "low", "close", "volume"), values):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "symbol", self.symbol.upper())


@dataclass(frozen=True)
class Instrument:
    symbol: str
    venue: str
    asset_class: str = "crypto_spot"
    base: str = ""
    quote: str = "USDT"
    contract_multiplier: Decimal = Decimal("1")
    quantity_step: Decimal = Decimal("0.000001")
    min_quantity: Decimal = Decimal("0.000001")
    price_tick: Decimal = Decimal("0.00000001")
    maker_fee: Decimal = Decimal("0.001")
    taker_fee: Decimal = Decimal("0.001")
    max_leverage: Decimal = Decimal("1")
    is_trading_enabled: bool = True

    def __post_init__(self):
        if self.asset_class not in ("crypto_spot", "crypto_perpetual", "equity"):
            raise ValueError("unsupported asset_class")
        for name in ("contract_multiplier", "quantity_step", "min_quantity",
                     "price_tick", "maker_fee", "taker_fee", "max_leverage"):
            value = D(getattr(self, name))
            if value < 0 or (name in ("contract_multiplier", "quantity_step",
                                      "min_quantity", "price_tick", "max_leverage") and value == 0):
                raise ValueError("%s must be positive" % name)
            object.__setattr__(self, name, value)
        if self.maker_fee >= 1 or self.taker_fee >= 1:
            raise ValueError("fee rates must be fractions below 1")
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "venue", self.venue.lower())


@dataclass(frozen=True)
class Signal:
    strategy: str
    symbol: str
    side: str
    timestamp: datetime
    entry_reference: Decimal
    stop_price: Decimal
    take_profit: Optional[Decimal]
    rationale: List[str] = field(default_factory=list)
    invalidation: List[str] = field(default_factory=list)
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if self.side not in ("buy", "sell"):
            raise ValueError("signal side must be buy or sell")
        if self.timestamp.tzinfo is None:
            raise ValueError("signal timestamp must be timezone-aware")
        for name in ("entry_reference", "stop_price"):
            value = D(getattr(self, name))
            if value <= 0:
                raise ValueError("%s must be positive" % name)
            object.__setattr__(self, name, value)
        if self.take_profit is not None:
            object.__setattr__(self, "take_profit", D(self.take_profit))
        object.__setattr__(self, "symbol", self.symbol.upper())


@dataclass(frozen=True)
class RiskLimits:
    risk_fraction: Decimal = Decimal("0.0025")
    max_notional_fraction: Decimal = Decimal("0.10")
    max_daily_loss_fraction: Decimal = Decimal("0.01")
    max_leverage: Decimal = Decimal("1")
    allow_leverage: bool = False
    max_data_age_seconds: int = 30
    slippage_bps: Decimal = Decimal("5")

    def __post_init__(self):
        for name in ("risk_fraction", "max_notional_fraction", "max_daily_loss_fraction",
                     "max_leverage", "slippage_bps"):
            value = D(getattr(self, name))
            if value < 0:
                raise ValueError("%s cannot be negative" % name)
            object.__setattr__(self, name, value)
        if self.risk_fraction > 1 or self.max_notional_fraction > 1:
            raise ValueError("risk and notional fractions must be <= 1")
        if self.max_data_age_seconds <= 0:
            raise ValueError("max_data_age_seconds must be positive")
        if not self.allow_leverage and self.max_leverage > 1:
            object.__setattr__(self, "max_leverage", Decimal("1"))
