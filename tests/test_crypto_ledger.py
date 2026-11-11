import os
import tempfile
import unittest
from datetime import datetime, timezone

from crypto.ledger import FillLedger


class LedgerTests(unittest.TestCase):
    def test_fill_ingestion_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = FillLedger(os.path.join(tmp, "fills.sqlite"))
            stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
            args = ("binance", "trade-1", "BTC/USDT", "buy", "0.1", "90000", stamp)
            self.assertTrue(ledger.record_fill(*args, fee="0.09", fee_currency="USDT"))
            self.assertFalse(ledger.record_fill(*args, fee="0.09", fee_currency="USDT"))
            fills = ledger.list_fills(symbol="BTC/USDT")
            self.assertEqual(len(fills), 1)
            self.assertEqual(fills[0]["trade_id"], "trade-1")
            with self.assertRaises(ValueError):
                ledger.record_fill("binance", "trade-1", "BTC/USDT", "buy", "0.2",
                                   "90000", stamp, fee="0.09", fee_currency="USDT")

    def test_naive_timestamp_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = FillLedger(os.path.join(tmp, "fills.sqlite"))
            with self.assertRaises(ValueError):
                ledger.record_fill("x", "1", "BTC/USDT", "buy", "1", "100",
                                   datetime(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
