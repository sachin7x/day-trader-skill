"""Deterministic opportunity ranking. Ranking is evidence-based, not a buy signal."""
from .indicators import atr, ema, rsi


def rank_market(candles_by_symbol, min_quote_volume=0, min_candles=60):
    min_quote_volume = float(min_quote_volume)
    ranked = []
    for symbol, candles in candles_by_symbol.items():
        if len(candles) < min_candles:
            continue
        candles = sorted(candles, key=lambda c: c.timestamp)
        closes = [float(c.close) for c in candles]
        highs = [float(c.high) for c in candles]
        lows = [float(c.low) for c in candles]
        volumes = [float(c.volume) for c in candles]
        last = candles[-1]
        quote_volume = sum(v * c for v, c in zip(volumes[-24:], closes[-24:]))
        if quote_volume < min_quote_volume:
            continue
        e21, e50 = ema(closes, 21), ema(closes, 50)
        rs = rsi(closes, 14)
        av = atr(highs, lows, closes, 14)
        if not e21 or not e50 or rs[-1] is None or av[-1] is None or last.close <= 0:
            continue
        trend = 1 if e21[-1] > e50[-1] else -1
        momentum = (closes[-1] / closes[-8] - 1) if closes[-8] else 0
        volatility = av[-1] / closes[-1]
        # Transparent score components: trend, normalized momentum, liquidity.
        score = (25 if trend > 0 else 0) + max(-25, min(25, momentum * 500))
        score += min(25, quote_volume / max(min_quote_volume, 1) * 2) if min_quote_volume else 0
        ranked.append({
            "symbol": symbol, "timestamp": last.timestamp.isoformat(),
            "last": str(last.close), "quote_volume_24": round(quote_volume, 2),
            "ema21": round(e21[-1], 8), "ema50": round(e50[-1], 8),
            "rsi14": round(rs[-1], 2), "atr14_pct": round(volatility * 100, 3),
            "momentum_7": round(momentum * 100, 3), "score": round(score, 2),
            "score_components": {"trend": trend, "momentum": round(momentum, 6),
                                 "quote_volume_24": round(quote_volume, 2)},
            "decision": "WATCH" if score >= 35 else "NO TRADE"
        })
    return sorted(ranked, key=lambda x: x["score"], reverse=True)
