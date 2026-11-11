"""Candle normalization, completion filtering and data-quality checks."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


TIMEFRAME_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900,
    "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400,
    "6h": 21600, "12h": 43200, "1d": 86400
}


@dataclass(frozen=True)
class DataQuality:
    input_count: int
    output_count: int
    duplicates_removed: int
    gaps: tuple
    incomplete_removed: int
    latest_timestamp: str = None


def normalize_candles(candles, timeframe, now=None, require_contiguous=False):
    """Sort, de-duplicate and remove unfinished/future bars.

    Candle timestamps represent interval start times. Conflicting duplicate
    timestamps are rejected instead of silently choosing a data source.
    """
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError("unsupported timeframe: %s" % timeframe)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    step = timedelta(seconds=TIMEFRAME_SECONDS[timeframe])
    rows = sorted(candles, key=lambda c: c.timestamp)
    unique, seen = [], {}
    duplicates = 0
    for candle in rows:
        if candle.timestamp.tzinfo is None:
            raise ValueError("candle timestamp must be timezone-aware")
        key = candle.timestamp.astimezone(timezone.utc)
        signature = (candle.open, candle.high, candle.low, candle.close, candle.volume)
        if key in seen:
            duplicates += 1
            if seen[key] != signature:
                raise ValueError("conflicting candle data for timestamp %s" % key.isoformat())
            continue
        seen[key] = signature
        if key + step > now.astimezone(timezone.utc):
            continue
        unique.append(candle)
    gaps = []
    for i in range(1, len(unique)):
        delta = unique[i].timestamp - unique[i - 1].timestamp
        if delta > step:
            gaps.append({"from": unique[i - 1].timestamp.isoformat(),
                         "to": unique[i].timestamp.isoformat(),
                         "missing_intervals": int(delta.total_seconds() // step.total_seconds()) - 1})
    if require_contiguous and gaps:
        raise ValueError("candle series contains %d time gaps" % len(gaps))
    incomplete_removed = len(rows) - duplicates - len(unique)
    latest = unique[-1].timestamp.isoformat() if unique else None
    return unique, DataQuality(len(rows), len(unique), duplicates, tuple(gaps),
                               incomplete_removed, latest)
