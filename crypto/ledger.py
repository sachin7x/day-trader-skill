"""SQLite append-only fill ledger with idempotent trade ingestion."""
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal


class FillLedger:
    def __init__(self, database_path):
        self.database_path = database_path
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS fills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    venue TEXT NOT NULL,
                    trade_id TEXT NOT NULL,
                    order_id TEXT,
                    client_order_id TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
                    quantity TEXT NOT NULL,
                    price TEXT NOT NULL,
                    fee TEXT NOT NULL DEFAULT '0',
                    fee_currency TEXT,
                    timestamp_utc TEXT NOT NULL,
                    raw_json TEXT,
                    UNIQUE(venue, trade_id)
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_fills_symbol_time ON fills(symbol, timestamp_utc)")

    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def record_fill(self, venue, trade_id, symbol, side, quantity, price, timestamp,
                    fee=0, fee_currency=None, order_id=None, client_order_id=None, raw_json=None):
        if not venue or not trade_id or not symbol:
            raise ValueError("venue, trade_id and symbol are required")
        if side not in ("buy", "sell"):
            raise ValueError("side must be buy or sell")
        qty, px, fee_value = Decimal(str(quantity)), Decimal(str(price)), Decimal(str(fee))
        if qty <= 0 or px <= 0 or fee_value < 0:
            raise ValueError("quantity and price must be positive; fee cannot be negative")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
            raise ValueError("fill timestamp must be timezone-aware")
        stamp = timestamp.astimezone(timezone.utc).isoformat()
        with self._connect() as db:
            cur = db.execute("""
                INSERT OR IGNORE INTO fills
                (venue, trade_id, order_id, client_order_id, symbol, side, quantity,
                 price, fee, fee_currency, timestamp_utc, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (venue.lower(), str(trade_id), order_id, client_order_id, symbol.upper(),
                  side, str(qty), str(px), str(fee_value), fee_currency, stamp, raw_json))
            return cur.rowcount == 1

    def list_fills(self, symbol=None, since=None, limit=10000):
        if limit <= 0:
            raise ValueError("limit must be positive")
        query = "SELECT * FROM fills"
        clauses, params = [], []
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol.upper())
        if since:
            if isinstance(since, datetime):
                if since.tzinfo is None:
                    raise ValueError("since must be timezone-aware")
                since = since.astimezone(timezone.utc).isoformat()
            clauses.append("timestamp_utc >= ?")
            params.append(str(since))
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY timestamp_utc ASC, id ASC LIMIT ?"
        params.append(int(limit))
        with self._connect() as db:
            return [dict(row) for row in db.execute(query, params).fetchall()]
