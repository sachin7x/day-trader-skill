# Repository Audit: Multi-Asset Trading Upgrade

**Repository:** `sachin7x/day-trader-skill`  
**Audited ref:** `main`  
**Implementation branch:** `feat/multi-asset-crypto-engine`  
**Audit date:** 2026-11-11  
**Method:** GitHub tree and source inspection. No local checkout was available in this execution environment, so the existing test suite has not been executed. Findings below are source-backed; runtime behavior remains unverified unless explicitly stated.

## Executive summary

The repository is a useful, intentionally conservative US-equity day-trading toolkit. It contains 11 Claude skills, standard-library Python command-line tools, JSON hand-offs, and offline unit-test fixtures. It is not yet a general trading platform: the asset model, risk checks, order schema, session calendar, and simulation assumptions are equity-specific.

Preserve the existing skills as the US-equity compatibility layer. Add a separately namespaced core with explicit instrument specifications, market-data interfaces, deterministic strategies, event-driven simulation, and a risk gate shared by paper and future live adapters.

## Inventory verified from the Git tree

- 11 skill folders: scanner, news, entry, exit, timemachine, risk, budget, broker, alerts, analyst, and Pelosi tracker.
- Python implementations for each skill, plus skill instructions and example JSON configuration.
- 10 unit-test modules under `tests/` and offline fixtures for Yahoo charts, SEC data, Nasdaq symbol files, House disclosures, and historical TSLA bars.
- Root-level plugin manifests, README, and MIT license.
- No existing crypto package, dependency manifest, typed common instrument model, exchange adapter layer, WebSocket service, or multi-asset portfolio ledger was present in the inspected tree.

## Findings

| ID | Severity | Area / evidence | Consequence | Recommendation |
|---|---|---|---|---|
| A-01 | **Critical** | Asset validation in `trader-risk/check.py`: US ticker regex and explicit rejection of slash-delimited symbols; `trader-budget/size.py` sizes long stock trades only. | Crypto pairs and derivative contracts cannot pass the current equity risk pipeline. | Keep this behavior for the equity skill. Introduce a separate instrument-aware crypto risk gate; do not weaken stock validation to accept arbitrary symbols. |
| A-02 | **High** | `trader-timemachine/timemachine.py`: 5-minute US session model, opening-range rules, time-of-day resampling from a historical pool, and stock-session calendar. | Cannot model 24/7 markets, multiple candle intervals, perpetual funding, contract multipliers, or exchange liquidity. | Build an event-driven engine with exchange timestamps, next-bar execution, costs, funding, and explicit instrument metadata. |
| A-03 | **High** | `simulate()` in `trader-timemachine/timemachine.py` assigns `-1R` to every stop outcome; source comments acknowledge a gap through a stop can fill worse. | Tail loss and expected return can be understated when price gaps through a stop. | In the new engine, fill stop-market orders at the first executable price plus adverse slippage; preserve stop-first handling when OHLC cannot reveal intrabar order. |
| A-04 | **High** | `trader-risk/check.py` calculates trade risk from quantity and entry-to-stop distance; the equity risk schema has no exchange contract multiplier, maker/taker fee, funding, borrow, or crypto liquidation model. | Risk and position size can be materially understated for derivatives and fee-heavy strategies. | Use Decimal arithmetic and instrument-specific contract rules. Include entry/exit fees, slippage, funding, margin and liquidation-distance checks. |
| A-05 | **High** | `trader-broker/ticket.py` builds an Alpaca-shaped stock order payload (`ALPACA_FIELDS`, `place_stock_order`) and delegates the actual broker call to the external Claude connector. | No native exchange execution/reconciliation layer for crypto spot or perpetuals. | Add a separate exchange adapter contract. Keep live methods unavailable unless an explicit per-order approval token is validated immediately before submission. |
| A-06 | **Medium** | `trader-scanner/scan.py`, `trader-news/news.py`, and other data tools use public HTTP endpoints; README identifies Yahoo Finance as unofficial. | No continuous market stream, consolidated exchange state, or guaranteed data freshness. Public endpoints can lag, change, or rate-limit. | Add provider adapters, timestamp/sequence tracking, stale-data rejection, retry/backoff and source provenance. |
| A-07 | **Medium** | NYSE holiday and early-close tables are embedded in scanner, risk, budget, alerts, and Time Machine code and cover named calendar years. | Calendar behavior becomes stale and duplicated; it is unsuitable for Indian equities or 24/7 crypto. | Keep crypto UTC/24-7. Centralize exchange calendars for equities and use maintained market-calendar data where appropriate. |
| A-08 | **Medium** | Workflow state is passed through files such as `trader/orders.json`, `trader/state/risk.json`, and `trader/state/broker.json`. | Concurrent processes can race or overwrite state; there is no transactional portfolio/event ledger. | Start with SQLite transactions and an append-only order/fill/event ledger. Preserve JSON exports for skill interoperability. |
| A-09 | **Medium** | The README describes a 10,000-path replay and historical replay over recent intraday stock bars. | This is useful as a scenario tool, but it is not a multi-year, multi-regime, cost-aware research framework and must not be interpreted as calibrated win probability. | Add walk-forward/out-of-sample evaluation, cost-aware metrics, regime splits, parameter sensitivity and explicit sample-size reporting. |
| A-10 | **Low** | The tree has tests and fixtures, but no root packaging/dependency manifest or visible CI/lint/type-check configuration. | Reproducibility and contributor onboarding are harder as the codebase grows. | Add optional dependency groups, documented Python support, deterministic tests and CI without disturbing the zero-dependency equity tools. |

## Existing strengths to preserve

1. The stock risk checker is a pure function over orders, configuration, portfolio, prices and broker state.
2. The broker workflow checks a fingerprint of the exact order against a same-day risk verdict before showing it as ready.
3. Paper trading is the default in the example configuration.
4. The Time Machine uses a deterministic random seed and conservative stop-before-target ordering when both are touched in one OHLC bar.
5. Offline fixtures make the existing tools testable without live market access.
6. The tools clearly warn that stop prices are not guaranteed fills and that simulated results are not predictions.

## Implementation boundary

The first crypto increment should be research and paper-trading only. It must not call private exchange endpoints or submit live orders. It will establish the common models, indicators, deterministic strategies, cost-aware risk calculations, and a backtest harness. Exchange connectivity and live execution remain separate later phases, with region/access checks and approval controls.

## Verification status

- Repository tree and source files: inspected through GitHub.
- Feature branch: created from `main`.
- Existing test suite: **not run**. The GitHub source connector is available, but this environment could not resolve `github.com` for a local clone. Do not interpret source inspection as a passing test run.
