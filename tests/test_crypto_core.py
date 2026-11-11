import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from crypto.indicators import ema, rsi, atr, bollinger
from crypto.models import Candle, Instrument, RiskLimits, Signal
from crypto.risk import evaluate
from crypto.execution import PaperBroker


class IndicatorTests(unittest.TestCase):
    def test_ema_seed_and_length(self):
        out = ema([1, 2, 3, 4, 5], 3)
        self.assertEqual(len(out), 5)
        self.assertIsNone(out[1])
        self.assertAlmostEqual(out[2], 2.0)

    def test_rsi_flat_series_is_neutral(self):
        out = rsi([10] * 20, 14)
        self.assertEqual(out[-1], 50.0)

    def test_atr_requires_enough_bars(self):
        self.assertEqual(atr([2], [1], [1.5], 14), [])

    def test_bollinger_no_lookback_value_before_period(self):
        out = bollinger([1, 2, 3, 4], 3)
        self.assertIsNone(out[1])
        self.assertIsNotNone(out[2])


class RiskTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.instrument = Instrument("BTC/USDT", "example", maker_fee="0.001",
                                      taker_fee="0.001", quantity_step="0.001",
                                      min_quantity="0.001")

    def signal(self, side="buy", age=0):
        ts = self.now - timedelta(seconds=age)
        return Signal("test", "BTC/USDT", side, ts, "100", "98", "104")

    def test_risk_sizing_includes_fees_and_slippage(self):
        result = evaluate(self.signal(), self.instrument, "10000",
                          RiskLimits(max_data_age_seconds=60), now=self.now)
        self.assertTrue(result.allowed)
        self.assertGreater(result.estimated_max_loss, Decimal("0"))
        self.assertLessEqual(result.estimated_max_loss, Decimal("25"))

    def test_stale_signal_is_blocked(self):
        result = evaluate(self.signal(age=120), self.instrument, "10000",
                          RiskLimits(max_data_age_seconds=30), now=self.now)
        self.assertFalse(result.allowed)

    def test_spot_short_is_blocked(self):
        result = evaluate(self.signal("sell"), self.instrument, "10000",
                          RiskLimits(max_data_age_seconds=60), now=self.now)
        self.assertFalse(result.allowed)

    def test_leverage_defaults_off(self):
        limits = RiskLimits()
        self.assertFalse(limits.allow_leverage)
        self.assertEqual(limits.max_leverage, Decimal("1"))

    def test_naive_clock_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(self.signal(), self.instrument, "10000",
                     RiskLimits(max_data_age_seconds=60), now=datetime(2026, 1, 1))

    def test_daily_loss_fraction_cannot_exceed_equity(self):
        with self.assertRaises(ValueError):
            RiskLimits(max_daily_loss_fraction="1.1")

    def test_slippage_cannot_make_a_fill_non_positive(self):
        with self.assertRaises(ValueError):
            RiskLimits(slippage_bps="10000")


class PaperExecutionTests(unittest.TestCase):
    def test_idempotent_submit_and_partial_fill(self):
        instrument = Instrument("BTC/USDT", "paper", quantity_step="0.001",
                                min_quantity="0.001")
        broker = PaperBroker()
        first = broker.submit(instrument, "buy", "1", client_order_id="stable-id")
        again = broker.submit(instrument, "buy", "1", client_order_id="stable-id")
        self.assertIs(first, again)
        broker.fill("stable-id", "0.4", "100")
        self.assertEqual(first.status, "partially_filled")
        broker.fill("stable-id", "0.6", "101")
        self.assertEqual(first.status, "filled")

    def test_duplicate_fill_over_quantity_is_rejected(self):
        instrument = Instrument("BTC/USDT", "paper", quantity_step="0.001",
                                min_quantity="0.001")
        broker = PaperBroker()
        broker.submit(instrument, "buy", "1", client_order_id="stable-id")
        broker.fill("stable-id", "0.8", "100")
        with self.assertRaises(ValueError):
            broker.fill("stable-id", "0.3", "100")


if __name__ == "__main__":
    unittest.main()
