# Institutional Trading Engine

The `trading_engine/` package implements the Part 2 execution layer without changing the Part 1 architecture.

## Deterministic Romeo TPT Sequence

`RomeoTPTOrchestrator.evaluate()` executes the required order:

1. Detect CRT range
2. Wait for liquidity sweep
3. Confirm rejection
4. Wait for CISD
5. Wait for KOD candle close
6. Validate structure
7. Validate higher-timeframe alignment
8. Validate session
9. Validate risk and portfolio exposure
10. Calculate score
11. Return an execution-ready trade setup

Only completed candles are evaluated for entry confirmation, preventing repainting and premature entries.

## Modules

- `crt.py` — CRT high, low, internal/external range, expansion/compression and targets.
- `liquidity.py` — buy-side/sell-side liquidity, equal highs/lows and sweeps.
- `kod.py` — strong opposing candle confirmation after sweep.
- `cisd.py` — internal structure and momentum shift confirmation.
- `order_block.py` — bullish/bearish, mitigated, breaker and invalid blocks.
- `fvg.py` — bullish/bearish FVG, CE, mitigation, fill and invalidation.
- `market_structure.py` — swings, BOS, CHOCH, expansion, compression, accumulation and distribution.
- `session.py` — Sydney, Tokyo, London, New York, London Open, NY Open and Power Hour filtering.
- `news_filter.py` — disables trading 15 minutes before and after high-impact events.
- `broker_intelligence.py` — reads MT5 account and symbol specifications directly from the broker.
- `risk.py` — broker-adaptive sizing and account protection limits.
- `portfolio.py` — total and correlated exposure control.
- `scoring.py` — confluence score gating.
- `execution.py` — signal-only, manual-confirmation and automated execution modes.
- `trade_management.py` — SL, TP1/TP2/TP3, break-even, trailing and partial plan.
- `analytics_engine.py` — performance metrics and equity curve.
- `backtesting.py` — backtest summaries, walk-forward windows, deterministic Monte Carlo and stress adjustments.

## Broker Adaptability

`MT5BrokerIntelligence` obtains broker name, server, account currency, balance, equity, free margin, margin level, leverage, contract size, digits, tick size, tick value, volume step, min/max volume, spread, swap, execution mode, filling modes, order modes and visibility directly from MT5. The position sizing engine uses those values for Forex, indices, metals, commodities and crypto without symbol-specific code.
