"""Exchange market-data interface."""
from abc import ABC, abstractmethod


class MarketDataAdapter(ABC):
    @abstractmethod
    async def load_markets(self):
        raise NotImplementedError

    @abstractmethod
    async def fetch_ohlcv(self, symbol, timeframe="1m", since=None, limit=500):
        raise NotImplementedError

    @abstractmethod
    async def fetch_order_book(self, symbol, limit=20):
        raise NotImplementedError

    @abstractmethod
    async def close(self):
        raise NotImplementedError
