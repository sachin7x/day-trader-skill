import unittest
from datetime import datetime, timezone
from decimal import Decimal

from crypto.analyst import build_trade_brief
from crypto.models import Signal
from crypto.risk import RiskDecision


class AnalystTests(unittest.TestCase):
    def setUp(self):
        stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.signal = Signal("ema_cross", "BTC/USDT", "buy", stamp,
                             "100", "98", "104", ["EMA crossed up"], ["close below stop"])
        self.market = {"symbol": "BTC/USDT", "exchange": "paper", "price": "101",
                       "timestamp": stamp.isoformat(), "regime": "bullish",
                       "trend": "up", "volume_confirmed": True}
        self.risk = RiskDecision(True, Decimal("1"), Decimal("100"),
                                 Decimal("2"), Decimal("0.002"), tuple())

    def test_no_trade_when_no_signal(self):
        brief = build_trade_brief(None, None, self.market)
        self.assertEqual(brief["decision"], "NO TRADE")

    def test_risk_failure_blocks_signal(self):
        denied = RiskDecision(False, Decimal("0"), Decimal("0"), Decimal("0"),
                              Decimal("0"), ("daily loss limit reached",))
        brief = build_trade_brief(self.signal, denied, self.market)
        self.assertEqual(brief["decision"], "BLOCKED BY RISK")
        self.assertIn("daily loss limit reached", brief["reasons_against"])

    def test_strong_setup_requires_oos_evidence(self):
        oos = {"sample_type": "out_of_sample", "trades": 50, "expectancy": 0.2,
               "profit_factor": 1.4, "max_drawdown": 0.1}
        brief = build_trade_brief(self.signal, self.risk, self.market, oos)
        self.assertEqual(brief["decision"], "STRONG SETUP")
        self.assertIsNone(brief["confidence"])
        self.assertEqual(brief["estimated_max_loss"], "2")

    def test_missing_oos_performance_only_watches(self):
        brief = build_trade_brief(self.signal, self.risk, self.market)
        self.assertEqual(brief["decision"], "WATCH")

    def test_derivatives_conflict_adds_caution(self):
        oos = {"sample_type": "out_of_sample", "trades": 50, "expectancy": 0.2,
               "profit_factor": 1.4, "max_drawdown": 0.1}
        brief = build_trade_brief(self.signal, self.risk, self.market, oos,
                                  derivatives={"flags": ["open_interest_up_price_down"]})
        self.assertEqual(brief["decision"], "WATCH")
        self.assertTrue(brief["reasons_against"])


if __name__ == "__main__":
    unittest.main()
