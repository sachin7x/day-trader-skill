# Crypto Engine: Architecture and Operating Boundary

## Status

This branch establishes a research-first crypto subsystem. It is not a production exchange execution platform. Live trading is explicitly unavailable.

## Package map

```
crypto/
  models.py                 Decimal-backed Candle, Instrument, Signal, RiskLimits
  indicators.py             Pure indicators, no external numerical dependency
  scanner.py                Transparent opportunity ranking
  strategies.py              Independent deterministic strategies
  risk.py                    Fee/slippage-aware sizing and hard blocks
  backtesting.py             Event-driven OHLCV simulator
  execution.py               Idempotent paper ledger; live call hard-disabled
  exchanges/
    base.py                  Async public market-data interface
    ccxt_public.py            Optional CCXT public-data implementation
  config.example.json
```

The original eleven `trader-*` skills remain intact. Existing US-equity order schemas and risk rules are not broadened to accept crypto symbols.

## Quick start

The core package uses only the Python standard library. Run the repository tests from the root:

```bash
python3 -m unittest discover -s tests -v
```

For optional public exchange data:

```bash
python3 -m pip install 'ccxt>=4,<5'
```

Example market-data usage:

```python
import asyncio
from crypto.exchanges.ccxt_public import CCXTPublicAdapter

async def main():
    exchange = CCXTPublicAdapter("binance")
    try:
        await exchange.load_markets()
        candles = await exchange.fetch_ohlcv("BTC/USDT", timeframe="5m", limit=500)
        print(candles[-1])
    finally:
        await exchange.close()

asyncio.run(main())
```

This example uses public market data only. A successful API response is not proof that a venue is accessible or lawful for a particular person in a particular jurisdiction.

## Safety and data rules

1. Timestamps must be timezone-aware. Normalize exchange timestamps to UTC at ingestion.
2. A strategy only receives candles through the latest completed candle supplied to it.
3. Backtest signals are generated at a candle close and can only enter at the next candle open.
4. If OHLC data touches stop and target in the same candle, stop wins. The simulator cannot infer intrabar sequence from OHLC alone.
5. Stop gaps fill at the worse of the stop and the next bar open, then adverse slippage is applied.
6. Fees are charged on entry and exit. Perpetual funding can be supplied as a timestamp-keyed rate series.
7. The backtester limits order quantity to a configurable fraction of candle volume. This is a coarse liquidity constraint, not a full order-book fill model.
8. Leverage is disabled by default. Perpetual maintenance margin, liquidation price and venue-specific margin tiers are not yet implemented. Perpetual research output must therefore be treated as incomplete until those checks exist.
9. No probability or expected win rate is fabricated. Strategy outputs are rule-based signals, not a forecast.
10. The paper broker is an in-memory test double, not an exchange simulator with matching-engine queue priority.

## Known limitations in this increment

- CCXT adapter exposes public OHLCV, ticker, trades, order book, funding-rate and open-interest methods only where the exchange supports them. It does not connect authenticated credentials.
- No private balance, position, order placement, cancellation or execution-history methods are implemented.
- No WebSocket streaming manager, persistent database, cross-exchange symbol normalization or reconnect supervisor yet.
- No liquidation-cluster inference, long/short ratio, on-chain or social sentiment provider.
- Strategy library currently contains four long-entry examples. Funding-rate mean reversion, OI divergence, liquidity sweeps, short strategies and market-regime classification remain future work.
- Backtesting supports one open position at a time and does not yet model portfolio correlation, multiple simultaneous assets, order-book depth, exchange-specific funding schedules or risk of ruin. Risk of ruin is deliberately reported as `null`, not guessed.
- Annualized Sharpe/Sortino values are estimates based on the median candle interval and assume independent observations. Use raw return, drawdown and trade-level results first.
- The example scanner score is a transparent ranking heuristic, not a validated predictive model.

## Next implementation phases

1. Complete historical-data ingestion, pagination, deduplication, gap detection and persistent caching.
2. Add exchange-specific instrument metadata and market-data health monitoring.
3. Add strategy walk-forward and out-of-sample evaluation, regime splits and parameter sensitivity.
4. Add multi-asset portfolio accounting, correlation and concentration limits.
5. Add perpetual contract specifications, funding schedule, maintenance margin and liquidation-distance model.
6. Add private exchange adapters only after official API review, regional access review and security design.
7. Add live execution only behind per-order approval, idempotency, reconciliation and an independently tested emergency stop.

## India operator checklist

This code does not decide whether an exchange is legally available to an India-based operator, whether an exchange is registered with FIU-IND, or how a particular trade is taxed. Verify current rules using official sources before connecting an account. Maintain immutable trade, fee, funding, deposit and withdrawal records for independent tax reconciliation. Do not put withdrawal permissions on trading API keys.
