import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from crypto.models import Candle, Instrument, Signal
from crypto.backtesting import BacktestConfig, run_backtest


class OneShotStrategy:
    name = "one_shot"

    def __init__(self, side="buy"):
        self.side = side

    def evaluate(self, candles):
        if len(candles) != 1:
            return None
        last = candles[-1]
        if self.side == "buy":
            return Signal("one_shot", last.symbol, "buy", last.timestamp, "100", "98", "103")
        return Signal("one_shot", last.symbol, "sell", last.timestamp, "100", "110", "90")


def bars(rows, symbol="BTC/USDT"):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [Candle(start + timedelta(minutes=5 * i), *row, symbol=symbol, timeframe="5m")
            for i, row in enumerate(rows)]


class BacktestTests(unittest.TestCase):
    def test_stop_wins_when_stop_and_target_are_inside_same_bar(self):
        candles = bars([
            ("100", "101", "99", "100", "1000"),
            ("100", "104", "97", "102", "1000"),
            ("102", "103", "100", "101", "1000")
        ])
        instrument = Instrument("BTC/USDT", "paper", quantity_step="0.001",
                                min_quantity="0.001")
        result = run_backtest(candles, OneShotStrategy(), instrument, BacktestConfig())
        self.assertEqual(len(result["trades"]), 1)
        self.assertEqual(result["trades"][0]["reason"], "stop")
        self.assertGreater(Decimal(result["trades"][0]["fees"]), Decimal("0"))

    def test_perpetual_funding_is_included_in_trade_pnl(self):
        candles = bars([
            ("100", "101", "99", "100", "1000"),
            ("100", "102", "98", "100", "1000"),
            ("100", "101", "94", "95", "1000")
        ])
        instrument = Instrument("BTC/USDT", "paper", asset_class="crypto_perpetual",
                                quantity_step="0.001", min_quantity="0.001")
        funding = {candles[1].timestamp.isoformat(): "0.001"}
        result = run_backtest(candles, OneShotStrategy("sell"), instrument,
                              BacktestConfig(funding_by_timestamp=funding))
        trade = result["trades"][0]
        self.assertGreater(Decimal(trade["funding_pnl"]), Decimal("0"))
        self.assertEqual(trade["reason"], "end_of_data")
        self.assertGreater(Decimal(trade["net_pnl"]), Decimal("0"))


if __name__ == "__main__":
    unittest.main()
