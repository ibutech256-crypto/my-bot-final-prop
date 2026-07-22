# Institutional AI Trading Platform (prop-frim-bot) — v1.9.3 Enterprise
## Full System Architecture & Production Deployment Guide

---

### Executive Overview

The **Institutional AI Trading Platform (`prop-frim-bot`)** is a full-stack, real-time algorithmic trading and risk shielding platform engineered specifically for **MetaTrader 5 (MT5)** direct execution. Built around the **Romeo TPT 11-Gate Deterministic Sequence**, the platform provides real-time telemetry, correlation exposure shielding, dynamic account management (Prop Firm vs. Growing Personal Accounts), and interactive multi-channel alerts.

---

### System Architecture & Core Technology Stack

```text
+-----------------------------------------------------------------------------------+
|                        INSTITUTIONAL COMMAND CENTER                               |
|                                                                                   |
|  +--------------------+      +----------------------+      +-------------------+  |
|  |   Next.js 15 UI    | <--> |   Django REST API    | <--> | Celery / Channels |  |
|  | (Port 3000 / HTTP) |      |   & WebSockets       |      | (Worker & Beat)   |  |
|  +--------------------+      +----------------------+      +-------------------+  |
+-----------------------------------------------------------------------------------+
                                          ^
                                          | Real-Time Polling & WebSockets (5s)
                                          v
+-----------------------------------------------------------------------------------+
|                     REAL-TIME TRADING & TELEMETRY ENGINE                          |
|                                                                                   |
|  +--------------------+      +----------------------+      +-------------------+  |
|  | TradingMT5Engine   | ---> | 11-Gate Romeo TPT    | ---> | AccountManager    |  |
|  | (355 MT5 Symbols)  |      | Deterministic Audit  |      | & Sizing Shield   |  |
|  +--------------------+      +----------------------+      +-------------------+  |
+-----------------------------------------------------------------------------------+
                                          |
        +---------------------------------+---------------------------------+
        | (Score >= 80 & Low Spread)                                        | (High-Priority Alerts)
        v                                                                   v
+---------------------------------------------------+             +-----------------------+
|            EXNESS MT5 DIRECT TERMINAL             |             | Telegram Bot Daemon   |
|                                                   |             | (@RomeoTPTBot)        |
|  - Account: #436005794 (Exness-MT5Trial9)         |             |                       |
|  - Auto Filling Retry: IOC -> FOK -> RETURN       |             | - /start, /status     |
|  - Stop-Loss Buffer: Stops Level + Spread + 10    |             | - Live Executions     |
+---------------------------------------------------+             +-----------------------+
```

1. **Frontend Dashboard (`TradingFrontend`)**:
   - Built with **Next.js 15 (App Router)**, React 19, and Tailwind CSS.
   - Serves real-time Exness MT5 account telemetry (`Balance`, `Equity`, `Margin`, `Floating P/L`), active signals (`Score >= 50`), live positions, and embedded **TradingView** order flow charts (`M15 / M69 Structural Matrix`).
   - Uses `ClientDashboard.tsx` with dynamic client rendering (`ssr: false`) for instant page builds and 100% real-time data sync without stale caching.

2. **Backend API & WebSockets (`TradingBackend`)**:
   - Built with **Django 5 / Django REST Framework (DRF)** and **Django Channels (ASGI)**.
   - Provides REST endpoints under `http://194.37.80.107:8000/api/v1/` (`/signals/`, `/open-positions/`, `/orders/`, `/trading-accounts/`).
   - Broadcasts real-time events (`ACCOUNT_TELEMETRY`, `POSITIONS_SYNC`, `NEW_SIGNAL`) over WebSockets (`ws://194.37.80.107:8000/ws/trading/`).

3. **Asynchronous Workers (`TradingBeat` & `TradingWorker`)**:
   - Powered by **Celery 5** and **Redis** (`redis://127.0.0.1:6379/1`).
   - `TradingBeat` executes periodic system heartbeats and performance recomputations.
   - `TradingWorker` handles asynchronous database analytics and background reporting.

4. **Institutional MT5 Trading Engine (`TradingMT5Engine`)**:
   - Runs `backend/manage.py run_mt5_engine` continuously in a 5-second polling loop tracking **355+ Exness symbols** across multiple timeframes (`M5`, `M15`, `H1`).
   - Evaluates setups via `RomeoTPTOrchestrator`, records setups scoring $\ge 50$ (`WATCHLIST`), and triggers direct automated execution (`client.place_market_order`) for high-confluence setups scoring $\ge 80$ (`ACTIVE`).

5. **Telegram Daemon (`TradingTelegram`)**:
   - Runs `python -m telegram.bot` to manage interactive user commands (`/start`, `/status`, `/balance`, `/signals`, `/positions`).
   - Dispatches instant high-priority alerts for new signals ($\ge 80$) and live trade executions (`🚨 INSTITUTIONAL TRADE EXECUTED 🚨`).

---

### Key Trading Engine Frameworks & Safety Guardrails

#### 1. Multi-Account Management Framework (`trading_engine/account_manager.py`)
The system dynamically determines account progression rules and position sizing based on real-time balance:

* **Growing (Personal) Account Mode (`Balance < $1,000`)**:
  - **Open Positions Limit**: Strictly capped at **4 concurrent open trades** (`active_positions < 4`).
  - **Daily Trade Target/Cap**: Target band of **10 to 15 trades per day**, strictly capped at **15 trades/day**.
  - **Lot Ceiling**: Strictly capped at **`0.05 micro-lots max`**, scaling safely from `0.01` up to `0.05` as equity grows past `$100`, `$250`, and `$500`.

* **Prop Firm Account Mode (`Balance ≥ $1,000`)**:
  - **Drawdown Protection**: Enforces daily loss caps ($5\%$) and total drawdown limits ($10\%$).
  - **Open Positions Limit**: Capped at **5 concurrent open positions** across all symbols (`active_positions < 5`).
  - **Daily Trade Target/Cap**: Target band of **15 to 25 trades per day**.
  - **Lot Ceiling & Stop Normalizer**: Strictly capped at **`0.50 lots max`** across all asset classes (`safety_max = Decimal("0.50")`). If a structural stop-loss is very tight (`price_risk < 0.20%` of entry), the risk calculator normalizes the risk floor (`min_price_risk_floor = entry * 0.002`) to prevent mathematical division from producing oversized positions.

#### 2. Institutional Execution Quality Gate (`TradeExecutionGate.evaluate`)
Before calling `order_send`, every candidate setup (`Score ≥ 80`) must clear three strict execution gates:
1. **Low Spread & Slippage Filter**: Measures real-time `tick.ask - tick.bid` against asset price (`spread_ratio ≤ 0.35%`). If spread expands (e.g. wide-spread stock CFDs or session rollover), the trade is rejected: `EXECUTION REJECTED: High spread condition exceeds low-spread threshold`.
2. **Momentum & Volume Verification**: Requires confirmed directional momentum (`Volatility` / `Structure` confluences $> 0$ or strong candle body velocity ratio $\ge 35\%$).
3. **CRT Late Entry Protection**: Checks if current market price (`tick.ask` / `tick.bid`) has drifted more than $35\%$ of the risk distance away from `sig.entry_price`. If drifted, **the trade is skipped unless it exhibits exceptional volume momentum (`Score ≥ 82` plus confirmed HTF structural alignment)**.

#### 3. Bulletproof MT5 Order Execution (`mt5_client.py`)
* **Automatic Filling Mode Retry**: Attempts order filling in priority order: `ORDER_FILLING_IOC` $\to$ `ORDER_FILLING_FOK` $\to$ `ORDER_FILLING_RETURN`. If any mode returns `10030` (`TRADE_RETCODE_INVALID_FILL`), it silently retries with the next mode until filled.
* **Stop-Loss Buffer Enforcement**: Queries MT5 `symbol_info.trade_stops_level` and `symbol_info.point`, enforcing `stops_level + spread + 10 points` buffer to permanently prevent `10016 Invalid stops` broker rejections.

---

### 24/7 Windows Server VPS Deployment & Service Management

All 6 components run natively as **NSSM (Non-Sucking Service Manager)** background services under `C:\prop-frim-bot` on Windows Server (`194.37.80.107`):

#### Service Management Commands (Run in PowerShell or CMD as Administrator)
```powershell
# Check status of all 6 institutional services
nssm status TradingBackend
nssm status TradingBeat
nssm status TradingFrontend
nssm status TradingMT5Engine
nssm status TradingTelegram
nssm status TradingWorker

# Restart individual services (e.g. after code or configuration updates)
nssm restart TradingMT5Engine
nssm restart TradingFrontend

# Restart all services sequentially
foreach ($svc in 'TradingBackend','TradingBeat','TradingFrontend','TradingMT5Engine','TradingTelegram','TradingWorker') { nssm restart $svc }
```

#### Service Configurations & Log Paths
All services are configured with unbuffered UTF-8 logging (`PYTHONUNBUFFERED=1`, `PYTHONIOENCODING=utf-8`):
* `TradingBackend` -> `logs\TradingBackend.log` (`backend\manage.py runserver 0.0.0.0:8000`)
* `TradingBeat` -> `logs\TradingBeat.log` (`celery -A backend.config beat -l INFO`)
* `TradingFrontend` -> `logs\TradingFrontend.log` (`node next start C:\prop-frim-bot\frontend -H 0.0.0.0 -p 3000`)
* `TradingMT5Engine` -> `logs\TradingMT5Engine.log` (`backend\manage.py run_mt5_engine`)
* `TradingTelegram` -> `logs\TradingTelegram.log` (`python -u -m telegram.bot`)
* `TradingWorker` -> `logs\TradingWorker.log` (`celery -A backend.config worker -l INFO --concurrency=4 -P threads`)

---

### Rebuilding & Deploying Code Changes

#### 1. Updating Python Backend / Trading Engine Code
```powershell
cd C:\prop-frim-bot
# After editing python files (e.g. account_manager.py, run_mt5_engine.py, mt5_client.py)
nssm restart TradingMT5Engine
nssm restart TradingBackend
```

#### 2. Rebuilding Next.js Frontend Dashboard (`page.tsx` / `ClientDashboard.tsx`)
```powershell
cd C:\prop-frim-bot\frontend
nssm stop TradingFrontend
# Clean old processes if needed
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'node.exe' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
# Run synchronous build
npx next build
# Start service
nssm start TradingFrontend
```

---

### Security & Credential Rotation Checklist

Whenever handing over or securing the server, immediately rotate all credentials:
1. **Windows Administrator Password (`SSH` / `RDP`)**:
   ```cmd
   net user administrator YourNewStrongPasswordHere!2026
   ```
2. **MetaTrader 5 Account Password**: Change directly inside Exness Personal Area (`#436005794`) or MT5 Terminal settings, then update `C:\prop-frim-bot\.env` (`MT5_PASSWORD=...`) and restart `TradingMT5Engine`.
3. **Telegram Bot Token**: If rotated via `@BotFather`, update `TELEGRAM_BOT_TOKEN=...` inside `C:\prop-frim-bot\.env` and restart `TradingTelegram` and `TradingMT5Engine`.
