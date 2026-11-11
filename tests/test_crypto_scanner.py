import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from crypto.models import Candle
from crypto.scanner import rank_market


class ScannerTests(unittest.TestCase):
    def test_decimal_volume_threshold_is_supported(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        candles = []
        for i in range(60):
            p = Decimal("100") + Decimal(i) / Decimal("10")
            candles.append(Candle(start + timedelta(minutes=5 * i), p, p + 1, p - 1,
                                  p, "10", symbol="BTC/USDT", timeframe="5m"))
        ranked = rank_market({"BTC/USDT": candles}, min_quote_volume=Decimal("100"))
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["symbol"], "BTC/USDT")


if __name__ == "__main__":
    unittest.main()
