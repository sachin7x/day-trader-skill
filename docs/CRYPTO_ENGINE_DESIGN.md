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
  data.py                    Candle completion, deduplication and gap checks
  derivatives.py             Funding/OI/basis diagnostics with evidence labels
  venues.py                  Dated jurisdiction and product eligibility gate
  india.py                   FY labels, tax-period references and CSV export
  ledger.py                  SQLite append-only, idempotent fill records
  backtesting.py             Event-driven OHLCV simulator
  execution.py               Idempotent paper ledger; live call hard-disabled
  cli.py                     Offline CSV scan and backtest commands
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
- The India CSV export is evidence formatting only. It does not calculate tax, decide TDS applicability or submit government forms.
- The SQLite fill ledger is implemented, but a complete cash/position portfolio ledger, migrations, and PostgreSQL backend are not yet implemented. No WebSocket streaming manager, cross-exchange symbol normalization or reconnect supervisor yet.
- No liquidation-cluster inference, long/short ratio, on-chain or social sentiment provider.
- Strategy library currently contains four long-entry examples. Funding-rate mean reversion, OI divergence, liquidity sweeps, short strategies and market-regime classification remain future work.
- Backtesting supports one open position at a time and does not yet model portfolio correlation, multiple simultaneous assets, order-book depth, exchange-specific funding schedules or risk of ruin. Risk of ruin is deliberately reported as `null`, not guessed.
- Annualized Sharpe/Sortino values are estimates based on the median candle interval and assume independent observations. Use raw return, drawdown and trade-level results first.
- The example scanner score is a transparent ranking heuristic, not a validated predictive model. Its 24-hour quote-volume field is estimated as candle base volume multiplied by candle close; it is not the exchange's authoritative quote-volume field and may be wrong for contract-volume markets. It skips symbols without a full 24-hour candle window.

## Next implementation phases

1. Complete historical-data ingestion, pagination, deduplication, gap detection and persistent caching.
2. Add exchange-specific instrument metadata and market-data health monitoring.
3. Add strategy walk-forward and out-of-sample evaluation, regime splits and parameter sensitivity.
4. Add multi-asset portfolio accounting, correlation and concentration limits.
5. Add perpetual contract specifications, funding schedule, maintenance margin and liquidation-distance model.
6. Add private exchange adapters only after official API review, regional access review and security design.
7. Add live execution only behind per-order approval, idempotency, reconciliation and an independently tested emergency stop.

## India operator checklist and regulatory data model

The system treats India as a reporting and venue-review profile, not as a blanket approval to trade on any foreign venue.

### Tax-period versioning

The Income-tax Department states that the Income-tax Act, 2025 governs relevant TDS events on or after 1 April 2026, while the Income-tax Act, 1961 governs the earlier credit/payment event through 31 March 2026. For VDA transfer TDS, the new reference is Section 393(1), Table Sl. No. 8(vi); the old reference is Section 194S. The official portal describes Form 141 Schedule D for qualifying Individual/HUF deductors and Form 142 for VDA exchanges that have agreed to deposit TDS on behalf of buyers/brokers. The exporter records the statutory-period label but does not decide whether TDS applies, compute tax, or generate a filed return.

Official references:
- [Income Tax Department: TDS compliance and transition to the 2025 Act](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/tds-compliance)
- [Income Tax Department: Form 141 FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/form-141-faqs?mobile-app=1)
- [Income Tax Department: Form 142 manual](https://www.incometax.gov.in/iec/foportal/newformpage/forms/form142-um)

### FIU-IND and service providers

The Ministry of Finance notification dated 7 March 2023 brought specified VDA service-provider activities within the PMLA framework, including exchange between VDA and fiat, exchange between VDAs, transfers, custody/administration, and specified issuer-related financial services. FIU-IND's 8 January 2026 AML/CFT guidelines and 15 September 2025 registration circular describe registration and ongoing compliance requirements for VDA service providers within scope. This is not a substitute for checking the exact legal status of a venue or the operator's own circumstances.

Official references:
- [FIU-IND: AML/CFT Guidelines for VDA service providers, updated 8 January 2026](https://fiuindia.gov.in/pdfs/downloads/VDA08012026.pdf)
- [FIU-IND: Third revision of VDA SP registration circular, 15 September 2025](https://fiuindia.gov.in/pdfs/downloads/VDASP15092025.pdf)
- [FIU-IND downloads and notices](https://fiuindia.gov.in/files/Downloads/Downloads.html)

### Venue access and foreign derivatives

A venue's public API responding successfully does not prove that account opening, deposits, withdrawals, spot trading or perpetual derivatives are available or permitted for a particular India-based user. The `crypto/venues.py` gate therefore requires a dated, explicit operator review and separate spot/perpetual approval. FIU registration, where applicable to the service provider, is a separate fact and does not itself establish that every product is lawful or accessible to the user.

SEBI has also published an advisory concerning foreign trading portals offering derivatives to Indian residents: [SEBI advisory, 30 October 2018](https://www.sebi.gov.in/media/press-releases/oct-2018/advisory-in-respect-of-foreign-trading-portals_40848.html). This is a reason to require current product- and jurisdiction-specific legal review, not a substitute for legal advice.

### Record keeping

Maintain immutable exchange fills, order IDs, transaction IDs, wallet transaction hashes, deposits, withdrawals, fee currency, funding, TDS and timestamped INR conversion rates. The CSV export accepts explicit historical FX rates; it never invents an INR conversion. Do not put withdrawal permissions on trading API keys.
