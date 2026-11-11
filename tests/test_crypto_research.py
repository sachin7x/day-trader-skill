import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from crypto.models import Candle, Instrument, Signal
from crypto.backtesting import BacktestConfig
from crypto.research import monte_carlo, walk_forward


class OneShot:
    def evaluate(self, candles):
        if len(candles) not in (11, 16):
            return None
        bar = candles[-1]
        return Signal("one", bar.symbol, "buy", bar.timestamp, bar.close,
                      bar.close * Decimal('0.98'), bar.close * Decimal('1.04'))


class ResearchTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.candles = []
        for i in range(20):
            p = 100 + i
            self.candles.append(Candle(start + timedelta(minutes=5 * i),
                                       p, p + 1, p - 1, p, 1000,
                                       symbol="BTC/USDT", timeframe="5m"))
        self.instrument = Instrument("BTC/USDT", "paper", quantity_step="0.001",
                                     min_quantity="0.001")

    def test_walk_forward_starts_after_warmup(self):
        result = walk_forward(self.candles, OneShot, self.instrument,
                              BacktestConfig(), warmup_bars=10, test_bars=5)
        self.assertEqual(result["fold_count"], 2)
        self.assertEqual(result["folds"][0]["warmup_bars"], 10)
        self.assertEqual(result["folds"][0]["test_bars"], 5)
        self.assertEqual(len(result["folds"][0]["trades"]), 1)
        self.assertEqual(result["folds"][0]["trades"][0]["entry_time"],
                         self.candles[11].timestamp.isoformat())

    def test_monte_carlo_is_reproducible(self):
        trades = [{"net_pnl": "10"}, {"net_pnl": "-5"}, {"net_pnl": "2"}]
        a = monte_carlo(trades, "1000", paths=100, seed=7)
        b = monte_carlo(trades, "1000", paths=100, seed=7)
        self.assertEqual(a, b)
        self.assertEqual(a["paths"], 100)
        self.assertIn("not predictive", a["warning"])

    def test_monte_carlo_requires_completed_trades(self):
        with self.assertRaises(ValueError):
            monte_carlo([], "1000")


if __name__ == "__main__":
    unittest.main()
