"""Optional CCXT public market-data adapter.

Install CCXT separately (see docs/CRYPTO_ENGINE_DESIGN.md). This adapter
intentionally does not accept API keys and cannot read balances or place orders.
Exchange availability and regional permissions must be checked independently.
"""
from datetime import datetime, timezone

from .base import MarketDataAdapter
from ..models import Candle


class CCXTPublicAdapter(MarketDataAdapter):
    def __init__(self, exchange_id, rate_limit=True, options=None):
        try:
            import ccxt.async_support as ccxt
        except ImportError as exc:
            raise RuntimeError("CCXT is optional; install it with: pip install ccxt") from exc
        if not exchange_id or not hasattr(ccxt, exchange_id):
            raise ValueError("unknown CCXT exchange id: %s" % exchange_id)
        exchange_type = getattr(ccxt, exchange_id)
        self.exchange = exchange_type({"enableRateLimit": bool(rate_limit),
                                       "options": options or {}})
        self.exchange_id = exchange_id

    async def load_markets(self):
        return await self.exchange.load_markets()

    async def fetch_ohlcv(self, symbol, timeframe="1m", since=None, limit=500):
        rows = await self.exchange.fetch_ohlcv(symbol, timeframe=timeframe,
                                               since=since, limit=limit)
        candles = []
        for row in rows:
            if len(row) < 6:
                continue
            ts, op, hi, lo, cl, vol = row[:6]
            candles.append(Candle(
                timestamp=datetime.fromtimestamp(ts / 1000.0, timezone.utc),
                open=op, high=hi, low=lo, close=cl, volume=vol,
                symbol=symbol, timeframe=timeframe))
        return candles

    async def fetch_ohlcv_range(self, symbol, timeframe, since, until, limit=500, max_pages=10000):
        """Paginate public OHLCV over a half-open [since, until) UTC range.

        since/until may be timezone-aware datetimes or Unix milliseconds. A
        bounded page count and monotonic cursor prevent infinite pagination.
        """
        from datetime import datetime, timezone
        def milliseconds(value):
            if isinstance(value, datetime):
                if value.tzinfo is None:
                    raise ValueError("date bounds must be timezone-aware")
                return int(value.astimezone(timezone.utc).timestamp() * 1000)
            return int(value)
        start_ms, end_ms = milliseconds(since), milliseconds(until)
        if start_ms < 0 or end_ms <= start_ms:
            raise ValueError("invalid OHLCV date range")
        if limit <= 0 or limit > 1000 or max_pages <= 0:
            raise ValueError("limit must be 1..1000 and max_pages must be positive")
        step_ms = int(self.exchange.parse_timeframe(timeframe) * 1000)
        if step_ms <= 0:
            raise ValueError("exchange returned an invalid timeframe duration")
        cursor, rows = start_ms, []
        for _ in range(max_pages):
            if cursor >= end_ms:
                break
            batch = await self.exchange.fetch_ohlcv(symbol, timeframe=timeframe,
                                                    since=cursor, limit=limit)
            if not batch:
                break
            for row in batch:
                stamp = int(row[0])
                if cursor <= stamp < end_ms:
                    rows.append(row)
            last_stamp = max(int(row[0]) for row in batch)
            next_cursor = last_stamp + step_ms
            if next_cursor <= cursor:
                raise RuntimeError("exchange OHLCV pagination did not advance")
            cursor = next_cursor
        else:
            raise RuntimeError("OHLCV pagination exceeded max_pages")
        candles = []
        for row in rows:
            ts, op, hi, lo, cl, vol = row[:6]
            candles.append(Candle(
                timestamp=datetime.fromtimestamp(int(ts) / 1000.0, timezone.utc),
                open=op, high=hi, low=lo, close=cl, volume=vol,
                symbol=symbol, timeframe=timeframe))
        return candles

    async def fetch_ticker(self, symbol):
        return await self.exchange.fetch_ticker(symbol)

    async def fetch_order_book(self, symbol, limit=20):
        return await self.exchange.fetch_order_book(symbol, limit=limit)

    async def fetch_trades(self, symbol, since=None, limit=100):
        return await self.exchange.fetch_trades(symbol, since=since, limit=limit)

    async def fetch_funding_rate(self, symbol):
        method = getattr(self.exchange, "fetch_funding_rate", None)
        if method is None:
            raise NotImplementedError("this exchange adapter does not expose fetch_funding_rate")
        return await method(symbol)

    async def fetch_open_interest(self, symbol):
        method = getattr(self.exchange, "fetch_open_interest", None)
        if method is None:
            raise NotImplementedError("this exchange adapter does not expose fetch_open_interest")
        return await method(symbol)

    async def close(self):
        await self.exchange.close()
