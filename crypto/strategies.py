"""Small deterministic strategies. No LLM-generated trade decisions live here."""
from .indicators import ema, rsi, vwap, bollinger
from .models import Signal


class Strategy:
    name = "base"

    def evaluate(self, candles):
        raise NotImplementedError


class EmaCross(Strategy):
    name = "ema_cross"

    def __init__(self, fast=9, slow=21, stop_fraction=0.015, reward_risk=2.0):
        if fast <= 0 or slow <= fast or stop_fraction <= 0 or reward_risk <= 0:
            raise ValueError("invalid EMA strategy parameters")
        self.fast, self.slow = fast, slow
        self.stop_fraction, self.reward_risk = stop_fraction, reward_risk

    def evaluate(self, candles):
        if len(candles) < self.slow + 1:
            return None
        closes = [float(c.close) for c in candles]
        f, s = ema(closes, self.fast), ema(closes, self.slow)
        if f[-2] is None or s[-2] is None or f[-1] is None or s[-1] is None:
            return None
        if not (f[-2] <= s[-2] and f[-1] > s[-1]):
            return None
        last = candles[-1]
        entry = last.close
        stop = entry * (1 - self.stop_fraction)
        target = entry + (entry - stop) * self.reward_risk
        return Signal(self.name, last.symbol, "buy", last.timestamp, entry, stop, target,
                      ["fast EMA crossed above slow EMA on the completed candle"],
                      ["fast EMA crosses back below slow EMA", "price closes below stop"],
                      {"fast_ema": f[-1], "slow_ema": s[-1]})


class RsiMeanReversion(Strategy):
    name = "rsi_mean_reversion"

    def __init__(self, period=14, oversold=30, stop_fraction=0.02, reward_risk=1.5):
        self.period, self.oversold = period, oversold
        self.stop_fraction, self.reward_risk = stop_fraction, reward_risk

    def evaluate(self, candles):
        values = rsi([float(c.close) for c in candles], self.period)
        if len(values) < 2 or values[-2] is None or values[-1] is None:
            return None
        if not (values[-2] < self.oversold and values[-1] >= self.oversold):
            return None
        last = candles[-1]
        entry = last.close
        stop = entry * (1 - self.stop_fraction)
        target = entry + (entry - stop) * self.reward_risk
        return Signal(self.name, last.symbol, "buy", last.timestamp, entry, stop, target,
                      ["RSI recovered above oversold threshold"],
                      ["RSI makes a new low or price closes below stop"],
                      {"rsi": values[-1]})


class VwapBreakout(Strategy):
    name = "vwap_breakout"

    def __init__(self, stop_fraction=0.012, reward_risk=2.0):
        self.stop_fraction, self.reward_risk = stop_fraction, reward_risk

    def evaluate(self, candles):
        if len(candles) < 3:
            return None
        vw = vwap([float(c.high) for c in candles], [float(c.low) for c in candles],
                  [float(c.close) for c in candles], [float(c.volume) for c in candles])
        if vw[-2] is None or vw[-1] is None:
            return None
        if not (float(candles[-2].close) <= vw[-2] and float(candles[-1].close) > vw[-1]):
            return None
        last = candles[-1]
        entry = last.close
        stop = entry * (1 - self.stop_fraction)
        target = entry + (entry - stop) * self.reward_risk
        return Signal(self.name, last.symbol, "buy", last.timestamp, entry, stop, target,
                      ["completed candle crossed above cumulative VWAP"],
                      ["price closes back below VWAP or stop"],
                      {"vwap": vw[-1]})


class BollingerBreakout(Strategy):
    name = "bollinger_breakout"

    def __init__(self, period=20, deviations=2.0, stop_fraction=0.015, reward_risk=2.0):
        self.period, self.deviations = period, deviations
        self.stop_fraction, self.reward_risk = stop_fraction, reward_risk

    def evaluate(self, candles):
        bands = bollinger([float(c.close) for c in candles], self.period, self.deviations)
        if len(bands) < 2 or bands[-2] is None or bands[-1] is None:
            return None
        if not (float(candles[-2].close) <= bands[-2]["upper"] and
                float(candles[-1].close) > bands[-1]["upper"]):
            return None
        last = candles[-1]
        entry = last.close
        stop = entry * (1 - self.stop_fraction)
        target = entry + (entry - stop) * self.reward_risk
        return Signal(self.name, last.symbol, "buy", last.timestamp, entry, stop, target,
                      ["completed close broke above the upper Bollinger band"],
                      ["price closes back inside the band or below stop"],
                      {"upper_band": bands[-1]["upper"]})
