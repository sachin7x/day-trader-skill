"""Offline CLI for crypto candle scanning and research backtests."""
import argparse
import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal

from .backtesting import BacktestConfig, run_backtest
from .data import normalize_candles
from .models import Candle, Instrument
from .scanner import rank_market
from .strategies import BollingerBreakout, EmaCross, RsiMeanReversion, VwapBreakout


STRATEGIES = {
    "ema_cross": EmaCross,
    "rsi_mean_reversion": RsiMeanReversion,
    "vwap_breakout": VwapBreakout,
    "bollinger_breakout": BollingerBreakout,
}


def load_candles_csv(path, symbol, timeframe):
    candles = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError("CSV missing columns: %s" % ", ".join(sorted(missing)))
        for row in reader:
            stamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            candles.append(Candle(stamp, row["open"], row["high"], row["low"],
                                  row["close"], row["volume"], symbol, timeframe))
    return candles


def main(argv=None):
    parser = argparse.ArgumentParser(description="Research-only crypto scanner and backtester")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="rank one symbol's CSV candle history")
    scan.add_argument("--csv", required=True)
    scan.add_argument("--symbol", required=True)
    scan.add_argument("--timeframe", default="5m")
    scan.add_argument("--min-quote-volume", default="0")
    scan.add_argument("--now", help="timezone-aware ISO timestamp for completion filtering")

    back = sub.add_parser("backtest", help="run a single-instrument offline backtest")
    back.add_argument("--csv", required=True)
    back.add_argument("--symbol", required=True)
    back.add_argument("--venue", default="offline")
    back.add_argument("--timeframe", default="5m")
    back.add_argument("--strategy", choices=sorted(STRATEGIES), default="ema_cross")
    back.add_argument("--asset-class", choices=("crypto_spot", "crypto_perpetual"), default="crypto_spot")
    back.add_argument("--cash", default="10000")
    back.add_argument("--fee-rate", default="0.001")
    back.add_argument("--slippage-bps", default="5")
    back.add_argument("--now", help="timezone-aware ISO timestamp for completion filtering")

    args = parser.parse_args(argv)
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        parser.error("--now must include a timezone")
    candles = load_candles_csv(args.csv, args.symbol, args.timeframe)
    candles, quality = normalize_candles(candles, args.timeframe, now=now)
    if len(candles) < 2:
        parser.error("not enough completed candles after data-quality filtering")

    if args.command == "scan":
        result = rank_market({args.symbol: candles},
                             min_quote_volume=Decimal(args.min_quote_volume))
    else:
        instrument = Instrument(args.symbol, args.venue, asset_class=args.asset_class,
                                taker_fee=Decimal(args.fee_rate))
        strategy = STRATEGIES[args.strategy]()
        config = BacktestConfig(initial_cash=Decimal(args.cash),
                                fee_rate=Decimal(args.fee_rate),
                                slippage_bps=Decimal(args.slippage_bps))
        result = run_backtest(candles, strategy, instrument, config)
    print(json.dumps({"data_quality": asdict(quality), "result": result},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
