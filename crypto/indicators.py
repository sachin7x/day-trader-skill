"""Dependency-free technical indicators. Inputs are chronological (oldest first)."""
from decimal import Decimal
from math import sqrt


def _values(values):
    out = [float(x) for x in values]
    if any(x != x or abs(x) == float("inf") for x in out):
        raise ValueError("indicator input contains a non-finite value")
    return out


def ema(values, period):
    xs = _values(values)
    if period <= 0:
        raise ValueError("period must be positive")
    if len(xs) < period:
        return []
    alpha = 2.0 / (period + 1.0)
    current = sum(xs[:period]) / period
    out = [None] * (period - 1) + [current]
    for x in xs[period:]:
        current = alpha * x + (1.0 - alpha) * current
        out.append(current)
    return out


def rsi(values, period=14):
    xs = _values(values)
    if period <= 0:
        raise ValueError("period must be positive")
    if len(xs) <= period:
        return []
    gains = [max(xs[i] - xs[i - 1], 0.0) for i in range(1, len(xs))]
    losses = [max(xs[i - 1] - xs[i], 0.0) for i in range(1, len(xs))]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out = [None] * period
    def value(g, l):
        if l == 0:
            return 100.0 if g > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + g / l)
    out.append(value(avg_gain, avg_loss))
    for i in range(period, len(gains)):
        avg_gain = ((period - 1) * avg_gain + gains[i]) / period
        avg_loss = ((period - 1) * avg_loss + losses[i]) / period
        out.append(value(avg_gain, avg_loss))
    return out


def true_range(highs, lows, closes):
    h, l, c = _values(highs), _values(lows), _values(closes)
    if not (len(h) == len(l) == len(c)):
        raise ValueError("high, low and close lengths differ")
    out = []
    for i in range(len(h)):
        out.append(h[i] - l[i] if i == 0 else max(
            h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    return out


def atr(highs, lows, closes, period=14):
    trs = true_range(highs, lows, closes)
    if len(trs) < period or period <= 0:
        return []
    current = sum(trs[:period]) / period
    out = [None] * (period - 1) + [current]
    for tr in trs[period:]:
        current = ((period - 1) * current + tr) / period
        out.append(current)
    return out


def macd(values, fast=12, slow=26, signal=9):
    if fast >= slow:
        raise ValueError("fast period must be below slow period")
    f, s = ema(values, fast), ema(values, slow)
    if not s:
        return {"macd": [], "signal": [], "histogram": []}
    line = [None if a is None or b is None else a - b for a, b in zip(f, s)]
    valid = [x for x in line if x is not None]
    sig = ema(valid, signal)
    offset = len(line) - len(sig)
    aligned = [None] * offset + sig
    hist = [None if a is None or b is None else a - b for a, b in zip(line, aligned)]
    return {"macd": line, "signal": aligned, "histogram": hist}


def vwap(highs, lows, closes, volumes):
    h, l, c, v = map(_values, (highs, lows, closes, volumes))
    if not (len(h) == len(l) == len(c) == len(v)):
        raise ValueError("OHLCV lengths differ")
    numerator = denominator = 0.0
    out = []
    for hi, lo, cl, vol in zip(h, l, c, v):
        numerator += ((hi + lo + cl) / 3.0) * vol
        denominator += vol
        out.append(numerator / denominator if denominator else None)
    return out


def bollinger(values, period=20, deviations=2.0):
    xs = _values(values)
    if period <= 0 or deviations <= 0:
        raise ValueError("period and deviations must be positive")
    out = []
    for i in range(len(xs)):
        if i + 1 < period:
            out.append(None)
            continue
        window = xs[i + 1 - period:i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        sd = sqrt(variance)
        out.append({"middle": mean, "upper": mean + deviations * sd,
                    "lower": mean - deviations * sd})
    return out
