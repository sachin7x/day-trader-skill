"""India reporting helpers. These classify records; they do not compute tax liability."""
import csv
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP


IST = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")


def _india_date(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(IST).date()
    if isinstance(value, date):
        return value
    raise TypeError("expected date or timezone-aware datetime")


def financial_year(value):
    """Indian financial year label, e.g. 2026-27, using Asia/Kolkata date."""
    d = _india_date(value)
    start = d.year if d.month >= 4 else d.year - 1
    return "%d-%02d" % (start, (start + 1) % 100)


def tax_regime_for_transaction(value):
    """Return the applicable statutory reference by earlier credit/payment date.

    This is a date-based export label only. The transaction's legal character,
    payer category, thresholds and exemptions still require professional review.
    """
    d = _india_date(value)
    if d <= date(2026, 3, 31):
        return {
            "act": "Income-tax Act, 1961",
            "tds_reference": "section 194S",
            "challan_statement": "Form 26QE where applicable"
        }
    return {
        "act": "Income-tax Act, 2025",
        "tds_reference": "section 393(1), Table Sl. No. 8(vi)",
        "challan_statement": "Form 141, Schedule D where applicable to an Individual/HUF deductor"
    }


def to_inr(amount, inr_per_quote_unit):
    """Convert using an explicitly supplied historical FX rate; never fetch or guess it."""
    amount = Decimal(str(amount))
    rate = Decimal(str(inr_per_quote_unit))
    if amount < 0 or rate <= 0:
        raise ValueError("amount must be non-negative and FX rate must be positive")
    return (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def export_transactions_csv(records, path):
    """Write raw transaction evidence for independent tax reconciliation."""
    fields = [
        "timestamp_utc", "timestamp_ist", "financial_year", "exchange", "account_label",
        "symbol", "asset", "side", "quantity", "price", "quote_currency", "quote_value",
        "inr_per_quote_unit", "inr_value", "fee", "fee_currency", "funding",
        "tds", "transaction_id", "order_id", "tx_hash", "record_type"
    ]
    count = 0
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            raw = dict(record)
            stamp = raw.get("timestamp")
            if isinstance(stamp, str):
                stamp = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if not isinstance(stamp, datetime) or stamp.tzinfo is None:
                raise ValueError("each transaction needs a timezone-aware timestamp")
            utc = stamp.astimezone(timezone.utc)
            ist = utc.astimezone(IST)
            raw["timestamp_utc"] = utc.isoformat()
            raw["timestamp_ist"] = ist.isoformat()
            raw["financial_year"] = financial_year(ist)
            if raw.get("quote_value") is not None and raw.get("inr_per_quote_unit") is not None:
                raw["inr_value"] = str(to_inr(raw["quote_value"], raw["inr_per_quote_unit"]))
            raw["timestamp"] = None
            writer.writerow(raw)
            count += 1
    return count
