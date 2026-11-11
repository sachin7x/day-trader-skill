import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from crypto.india import financial_year, tax_regime_for_transaction, to_inr, export_transactions_csv
from crypto.venues import VenueAssessment


class IndiaReportingTests(unittest.TestCase):
    def test_financial_year_boundary(self):
        self.assertEqual(financial_year(date(2026, 3, 31)), "2025-26")
        self.assertEqual(financial_year(date(2026, 4, 1)), "2026-27")

    def test_tax_regime_transition(self):
        self.assertEqual(tax_regime_for_transaction(date(2026, 3, 31))["tds_reference"], "section 194S")
        self.assertIn("393(1)", tax_regime_for_transaction(date(2026, 4, 1))["tds_reference"])

    def test_tax_regime_uses_india_local_date(self):
        utc_evening = datetime(2026, 3, 31, 19, 0, tzinfo=timezone.utc)
        self.assertIn("393(1)", tax_regime_for_transaction(utc_evening)["tds_reference"])
        self.assertEqual(financial_year(utc_evening), "2026-27")

    def test_inr_requires_explicit_fx_rate(self):
        self.assertEqual(to_inr("2.5", "83.25"), Decimal("208.13"))
        with self.assertRaises(ValueError):
            to_inr("1", "0")

    def test_export_requires_timezone_aware_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "trades.csv")
            n = export_transactions_csv([{
                "timestamp": datetime(2026, 4, 1, tzinfo=timezone.utc),
                "exchange": "example", "symbol": "BTC/USDT", "side": "buy",
                "quantity": "0.1", "price": "100"
            }], path)
            self.assertEqual(n, 1)
            with open(path, encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("2026-27", content)
            self.assertIn("+05:30", content)


class VenueGateTests(unittest.TestCase):
    def test_stale_review_blocks(self):
        assessment = VenueAssessment("x", "IN", True, True, checked_on=date(2025, 1, 1))
        ok, reasons = assessment.eligibility("crypto_spot", today=date(2026, 1, 1))
        self.assertFalse(ok)
        self.assertTrue(reasons)

    def test_perpetuals_need_explicit_approval(self):
        assessment = VenueAssessment("x", "IN", True, True, True, False,
                                     checked_on=date(2026, 11, 1))
        ok, reasons = assessment.eligibility("crypto_perpetual", today=date(2026, 11, 11))
        self.assertFalse(ok)
        self.assertIn("perpetual derivatives are not explicitly approved by the venue review", reasons)


    def test_venue_requires_verified_api_scopes_and_withdrawals_disabled(self):
        assessment = VenueAssessment("x", "IN", True, True, checked_on=date(2026, 11, 1),
                                     api_permissions_verified=True,
                                     withdrawal_permission_enabled=True)
        ok, reasons = assessment.eligibility("crypto_spot", today=date(2026, 11, 11))
        self.assertFalse(ok)
        self.assertIn("withdrawal permission is enabled; disable it before trading integration", reasons)


if __name__ == "__main__":
    unittest.main()
