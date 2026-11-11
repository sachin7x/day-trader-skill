# Crypto research package

The root repository's eleven stock-trading skills remain the existing US-equity workflow. This package is separate and research-first.

## Offline workflow

Prepare a CSV with these columns:

`timestamp,open,high,low,close,volume`

Timestamps must be ISO-8601 with a timezone, preferably UTC. Candle timestamps represent interval start times.

Rank one market:

```bash
python -m crypto scan --csv data/BTCUSDT-5m.csv --symbol BTC/USDT --timeframe 5m --min-quote-volume 1000000
```

Run a deterministic strategy backtest:

```bash
python -m crypto backtest --csv data/BTCUSDT-5m.csv --symbol BTC/USDT --timeframe 5m --strategy ema_cross --cash 10000
```

The Python API also exposes `crypto.research.walk_forward` for fixed-rule out-of-sample folds and `crypto.research.monte_carlo` for bootstrap scenario analysis of completed trades.

For a perpetual research simulation, pass `--asset-class crypto_perpetual`. This does not enable leverage or live execution. Funding data is currently supplied programmatically to `BacktestConfig`, not loaded by the CLI.

## Public exchange data

The optional `CCXTPublicAdapter` requires CCXT and uses public endpoints only. It does not accept API keys or submit orders.

See [the architecture and operating boundary](../docs/CRYPTO_ENGINE_DESIGN.md) before using market data or interpreting backtest output.
