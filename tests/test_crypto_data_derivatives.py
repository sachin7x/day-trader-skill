import unittest
import asyncio
from datetime import datetime, timezone, timedelta

from crypto.models import Candle
from crypto.data import normalize_candles
from crypto.derivatives import DerivativesSnapshot, analyze
from crypto.exchanges.ccxt_public import CCXTPublicAdapter


class DataQualityTests(unittest.TestCase):
    def candle(self, minutes, close="100"):
        return Candle(datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minutes),
                      close, close, close, close, "1", symbol="BTC/USDT", timeframe="1m")

    def test_duplicate_and_incomplete_candles(self):
        now = datetime(2026, 1, 1, 0, 4, tzinfo=timezone.utc)
        candles, quality = normalize_candles(
            [self.candle(0), self.candle(0), self.candle(1), self.candle(4)],
            "1m", now=now)
        self.assertEqual(len(candles), 2)
        self.assertEqual(quality.duplicates_removed, 1)
        self.assertEqual(quality.incomplete_removed, 1)

    def test_conflicting_duplicate_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_candles([self.candle(0, "100"), self.candle(0, "101")],
                              "1m", now=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc))


class FakeExchange:
    def __init__(self):
        self.rows = [[0, 100, 101, 99, 100, 10],
                     [60000, 100, 101, 99, 100, 10],
                     [120000, 100, 101, 99, 100, 10],
                     [180000, 100, 101, 99, 100, 10]]

    def parse_timeframe(self, timeframe):
        return 60

    async def fetch_ohlcv(self, symbol, timeframe, since, limit):
        return [row for row in self.rows if row[0] >= since][:limit]


class ExchangePaginationTests(unittest.TestCase):
    def test_ohlcv_range_paginates_and_excludes_end_timestamp(self):
        adapter = CCXTPublicAdapter.__new__(CCXTPublicAdapter)
        adapter.exchange = FakeExchange()
        candles = asyncio.run(adapter.fetch_ohlcv_range("BTC/USDT", "1m", 0, 180000, limit=2))
        self.assertEqual(len(candles), 3)
        self.assertEqual([int(c.timestamp.timestamp() * 1000) for c in candles],
                         [0, 60000, 120000])


class DerivativesTests(unittest.TestCase):
    def test_open_interest_price_divergence_is_labelled_hypothesis(self):
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        prev = DerivativesSnapshot("x", "BTC/USDT", t0, "100", "100", "1000", "0.0001")
        curr = DerivativesSnapshot("x", "BTC/USDT", t0 + timedelta(hours=1),
                                   "95", "95", "1100", "0.0002")
        result = analyze(curr, previous=prev)
        self.assertIn("open_interest_up_price_down", result["flags"])
        self.assertIn("hypotheses", result)
        self.assertIn("not inferred", result["warning"])


if __name__ == "__main__":
    unittest.main()
