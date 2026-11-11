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
