# Institutional Intelligence Layer

The `intelligence/` package upgrades the platform from deterministic rule execution to adaptive institutional market intelligence. It does not replace Romeo TPT logic; it refines context, execution quality, risk selection, operational resilience and commercial deployment control.

## Core Engines

- Multi-timeframe matrix: Monthly → Weekly → Daily → 4H → 2H/69m synthetic → 15M → 5M → 2M → 1M context.
- Custom timeframe engine: generates 69-minute institutional candles with OHLCV, range, CRT and structure context.
- Multi-timeframe validation: penalises or blocks lower-timeframe trades that conflict with higher-timeframe structure or opposing macro order blocks.
- Adaptive Turtle Soup: activates on liquidity sweep and switches monitoring to M2/M1 microstructure confirmation.
- Hard Kill Zone: administrator-configurable institutional windows.
- Correlation Shield: DXY, BTC dominance and future reference assets can penalise, block or weight-adjust setups.
- Smart FVG: tracks creation, width, strength, age, fill percentage, CE midpoint, mitigation and invalidation. Opposing body close beyond midpoint invalidates confluence.
- Liquidity Magnet: dynamic targets from weekly, monthly, quarterly, equal highs/lows and old levels.
- Symbol Intelligence: independent statistics per symbol.
- Market Regime: trending, ranging, expansion, compression, accumulation/distribution proxy, volatility and risk-on/off context.
- Strategy Health: rolling module health and automatic weighting recommendations.
- Execution Quality: latency, slippage, delay, spread, rejects, partial fills, modification and close speed.
- Portfolio Intelligence: cross-asset and currency exposure control.
- AI Trade Review: deterministic permanent trade reviews.
- Screenshot Intelligence: SVG annotations for journal events.
- Trade Replay: candle-by-candle reconstruction.
- Reporting: daily, weekly, monthly, quarterly and yearly report generation.
- Broker Diagnostics: detects leverage, contract, spread and visibility changes.
- Smart Symbol Mapping: normalises broker suffixes like BTCUSDm, BTCUSD.pro, NAS100.cash.
- VPS Health: CPU/process/disk/API checks and service restart hooks.
- Backup: archive and retention management.
- Commercial Management: license activation, machine binding, feature flags and validation.
- AI Optimisation: recommendations only, unless administrator approval is enabled.

## Auditability

`backend/apps/intelligence_app` stores decision logs, symbol intelligence snapshots, operational incidents and commercial license records. Decisions include before/after scores, reasons, reversibility and approval metadata.

## Execution Safety Addendum

### 500 ms Timestamp Validation Gate

`intelligence/data_freshness.py` provides `TimestampValidationEngine`. The Romeo TPT orchestrator calls this gate before trade calculation. If the latest completed candle or price event is older than 500 ms, the engine raises a hard abort and no execution calculation proceeds. The adaptive Turtle Soup price observer applies the same validation to microstructure price events.

The platform remains MT5-native for market data and execution. External crypto exchanges such as Binance, OKX, Bybit or Coinbase are not required or integrated; the stale-data protection applies to any configured live stream but production execution uses the MT5 broker feed.

### M69 Resampler Cache Cleanup

`intelligence/resampling_cache.py` implements a bounded TTL cache for custom timeframe bars. `backend/apps/intelligence_app/tasks.py` exposes `cleanup_resampler_cache`, intended to run hourly from Celery beat. The cache enforces both TTL and maximum-entry bounds so old M69 data references are released before high-volume sessions such as New York Open.
