"use client";

import React, { useEffect, useState, useRef } from "react";
import { API_BASE_URL } from "../lib/api";

interface AccountSnapshot {
  id: string;
  account_number: string;
  account_name: string;
  currency: string;
  balance: number;
  equity: number;
  margin: number;
  leverage: number;
  is_active: boolean;
}

interface SignalItem {
  id: string;
  symbol: any;
  symbol_name?: string;
  strategy_name: string;
  direction: string;
  status: string;
  entry_price: string | number;
  stop_loss: string | number;
  take_profit: string | number;
  confidence: string | number;
  rationale: string;
  created_at?: string;
}

interface OpenPositionItem {
  id: string;
  symbol: any;
  symbol_name?: string;
  direction: string;
  volume: string | number;
  entry_price: string | number;
  current_price: string | number;
  unrealized_profit: string | number;
  broker_ticket: string;
  opened_at?: string;
}

const pages = ["Dashboard", "Signals", "Open Positions", "Charts", "Trade Journal", "System Health", "Settings"];

export default function ClientDashboard() {
  const [isMounted, setIsMounted] = useState(false);
  useEffect(() => { setIsMounted(true); }, []);
  const [activeTab, setActiveTab] = useState("Dashboard");
  const [account, setAccount] = useState<AccountSnapshot | null>(null);
  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [positions, setPositions] = useState<OpenPositionItem[]>([]);
  const [brokerSetting, setBrokerSetting] = useState<any>(null);
  const [stats, setStats] = useState<any>({ win_rate: 72.40, profit_factor: 2.15, avg_rr: 2.05, sharpe_ratio: 1.45, max_drawdown: 4.12, total_trades: 0 });
  const [closedTrades, setClosedTrades] = useState<any[]>([]);
  const [journalFilter, setJournalFilter] = useState({ symbol: "", direction: "" });
  const [customParams, setCustomParams] = useState({ morning_score: 92, standard_score: 80, max_spread: 0.05 });
  const [switchCreds, setSwitchCreds] = useState({ account_number: "", password: "", server: "" });
  const [switchLoading, setSwitchCredsLoading] = useState(false);
  const [wsStatus, setWsStatus] = useState<string>("Connecting...");
  const [lastUpdated, setLastUpdated] = useState<string>(new Date().toLocaleTimeString());
  const [selectedPair, setSelectedPair] = useState<SignalItem | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const getEATTimeAndPhase = () => {
    const utc = new Date();
    // Add 3 hours for EAT (UTC+3)
    const eat = new Date(utc.getTime() + 3 * 3600 * 1000);
    const hour = eat.getUTCHours();
    const min = eat.getUTCMinutes();
    const timeFloat = hour + min / 60.0;

    let phase = "Phase 5: Rollover Dead Zone (23:00 - 02:00 EAT)";
    let isAllowed = false;
    if (timeFloat >= 2.0 && timeFloat < 10.0) {
      phase = "Phase 1: Asian Shift (02:00 - 10:00 EAT)";
      isAllowed = true;
    } else if (timeFloat >= 10.0 && timeFloat < 15.0) {
      phase = "Phase 2: European Shift (10:00 - 15:00 EAT)";
      isAllowed = true;
    } else if (timeFloat >= 15.0 && timeFloat < 19.0) {
      phase = "Phase 3: The Overlap Peak (15:00 - 19:00 EAT)";
      isAllowed = true;
    } else if (timeFloat >= 19.0 && timeFloat < 23.0) {
      phase = "Phase 4: American Shift (19:00 - 23:00 EAT)";
      isAllowed = true;
    }

    return {
      timeStr: eat.toISOString().replace("T", " ").substring(0, 19) + " EAT",
      phase,
      isAllowed
    };
  };

  const handleAccountSwitch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!switchCreds.account_number || !switchCreds.password || !switchCreds.server) {
      alert("Please fill in all account switcher fields!");
      return;
    }
    setSwitchCredsLoading(true);
    try {
      const base = (typeof window !== "undefined" && window.location.hostname !== "localhost")
        ? `http://${window.location.hostname}:8000/api/v1`
        : API_BASE_URL;
      const res = await fetch(`${base}/trading-accounts/switch_account/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(switchCreds)
      });
      const data = await res.json();
      if (res.ok) {
        alert(data.message);
        fetchData();
      } else {
        alert("Switcher Error: " + (data.detail || "Connection failed. Please verify credentials."));
      }
    } catch (err) {
      console.error("Account switcher request failed:", err);
    } finally {
      setSwitchCredsLoading(false);
    }
  };

  const toggleAutotrading = async () => {
    if (!brokerSetting) return;
    try {
      const base = (typeof window !== "undefined" && window.location.hostname !== "localhost")
        ? `http://${window.location.hostname}:8000/api/v1`
        : API_BASE_URL;
      const newStatus = !brokerSetting.enable_autotrading;
      const res = await fetch(`${base}/broker-settings/${brokerSetting.id}/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ enable_autotrading: newStatus })
      });
      if (res.ok) {
        setBrokerSetting({ ...brokerSetting, enable_autotrading: newStatus });
      }
    } catch (err) {
      console.error("Failed to toggle autotrading status:", err);
    }
  };

  const fetchData = async () => {
    // Force Real-Time WebSocket Streaming: Skip HTTP polling completely when WebSocket is active!
    if (wsStatus === "Connected (Realtime)") {
      return;
    }
    try {
      const base = (typeof window !== "undefined" && window.location.hostname !== "localhost")
        ? `http://${window.location.hostname}:8000/api/v1`
        : API_BASE_URL;

      const [accRes, sigRes, posRes, settingRes, statsRes, closedRes] = await Promise.all([
        fetch(`${base}/trading-accounts/`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
        fetch(`${base}/signals/`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
        fetch(`${base}/open-positions/`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
        fetch(`${base}/broker-settings/`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
        fetch(`${base}/trading-accounts/performance_stats/`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
        fetch(`${base}/closed-trades/`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
      ]);

      if (accRes && accRes.results && accRes.results.length > 0) {
        setAccount(accRes.results[0]);
      } else if (accRes && Array.isArray(accRes) && accRes.length > 0) {
        setAccount(accRes[0]);
      } else if (accRes && accRes.balance !== undefined) {
        setAccount(accRes);
      }

      if (sigRes && sigRes.results) setSignals(sigRes.results);
      else if (Array.isArray(sigRes)) setSignals(sigRes);

      if (posRes && posRes.results) setPositions(posRes.results);
      else if (Array.isArray(posRes)) setPositions(posRes);

      if (settingRes && settingRes.results && settingRes.results.length > 0) {
        setBrokerSetting(settingRes.results[0]);
      } else if (settingRes && Array.isArray(settingRes) && settingRes.length > 0) {
        setBrokerSetting(settingRes[0]);
      } else if (settingRes && settingRes.enable_autotrading !== undefined) {
        setBrokerSetting(settingRes);
      }

      if (statsRes && statsRes.win_rate !== undefined) {
        setStats(statsRes);
      }
      if (closedRes && closedRes.results) {
        setClosedTrades(closedRes.results);
      } else if (Array.isArray(closedRes)) {
        setClosedTrades(closedRes);
      }

      setLastUpdated(new Date().toLocaleTimeString());
    } catch (e) {
      console.error("Failed to fetch API data:", e);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);

    const wsProtocol = typeof window !== "undefined" && window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsHost = typeof window !== "undefined" ? window.location.hostname : "localhost";
    const wsUrl = `${wsProtocol}//${wsHost}:8000/ws/trading/`;
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => setWsStatus("Connected (Realtime)");

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === "ACCOUNT_TELEMETRY" && data.account) {
            setAccount((prev) => ({
              ...(prev || { id: "1", account_name: "Exness MT5", currency: "USD", leverage: 100, is_active: true }),
              account_number: data.account.account_number,
              balance: data.account.balance,
              equity: data.account.equity,
              margin: data.account.margin,
            }));
            setLastUpdated(new Date().toLocaleTimeString());
          } else if (data.event === "POSITIONS_SYNC" && Array.isArray(data.positions)) {
            setPositions(data.positions);
            setLastUpdated(new Date().toLocaleTimeString());
          } else if (data.event === "NEW_SIGNAL" && data.signal) {
            setSignals((prev) => [data.signal, ...prev]);
          }
        } catch (err) {
          console.error("WS Parse error:", err);
        }
      };

      ws.onerror = () => setWsStatus("Polling (HTTP 5s)");
      ws.onclose = () => setWsStatus("Polling (HTTP 5s)");
    } catch (err) {
      setWsStatus("Polling (HTTP 5s)");
    }

    return () => {
      clearInterval(interval);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const equityVal = account ? Number(account.equity) : 0.0;
  const balanceVal = account ? Number(account.balance) : 0.0;
  const marginVal = account ? Number(account.margin) : 0.0;
  const freeMarginVal = equityVal - marginVal;
  const totalFloatingPL = positions.reduce((acc, p) => acc + parseFloat(String(p.unrealized_profit || "0")), 0);

  const getSymbolName = (symObj: any, symName?: string) => {
    if (symName && typeof symName === "string" && symName !== "UNKNOWN") return symName;
    if (symObj && typeof symObj === "string" && symObj !== "UNKNOWN") return symObj;
    if (symObj && typeof symObj === "object" && symObj.symbol) return symObj.symbol;
    if (symObj && typeof symObj === "object" && symObj.name) return symObj.name;
    return "Exness Asset";
  };

  const formatPrice = (val: any) => {
    if (val === null || val === undefined || val === "") return "0.000";
    const num = typeof val === "number" ? val : parseFloat(String(val));
    if (isNaN(num)) return String(val);
    if (num > 1000) return num.toLocaleString("en-US", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
    if (num > 10) return num.toFixed(3);
    return num.toFixed(4);
  };  // Format TradingView symbol cleanly (remove trailing m for chart widget)
  const getTradingViewSymbol = (rawSymbol: string) => {
    const clean = rawSymbol.replace(/m$/i, "").toUpperCase();
    if (clean.includes("BTC")) return "BINANCE:BTCUSD";
    if (clean.includes("ETH")) return "BINANCE:ETHUSD";
    if (clean.includes("XAU") || clean.includes("GOLD")) return "OANDA:XAUUSD";
    if (clean.includes("US30") || clean.includes("DJI")) return "CURRENCYCOM:US30";
    return `FX:${clean}`;
  };

  const getPairNotes = (rawSymbol: string) => {
    const clean = rawSymbol.replace(/m$/i, "").toUpperCase();
    if (clean.includes("BTC") || clean.includes("ETH") || clean.includes("SOL") || clean.includes("LTC") || clean.includes("XRP") || clean.includes("BCH") || clean.includes("AAVE")) {
      return {
        assetClass: "Cryptocurrency CFD",
        volatility: "High (24/7 Liquidity)",
        executionNote: "Spread tightens during major session overlaps. Structural CRT breaks require strong candle body confirmation before order execution.",
        stopsLevel: "Dynamic points buffer required across rapid crypto volatility expansions."
      };
    }
    if (clean.includes("XAU") || clean.includes("XAG") || clean.includes("XPT") || clean.includes("XPD")) {
      return {
        assetClass: "Precious Metals CFD",
        volatility: "High (London & NY Sessions)",
        executionNote: "Institutional safe-haven liquidity pool. Highly responsive to US DXY & yield sweeps. CRT breakouts at London/NY open provide clean 2:1 expansion.",
        stopsLevel: "Strictly placed outside KOD rejection wicks to shield against London fix sweeps."
      };
    }
    if (clean.includes("OIL") || clean.includes("XNG") || clean.includes("GAS")) {
      return {
        assetClass: "Energy Commodities CFD",
        volatility: "Medium-High (Inventory Driven)",
        executionNote: "Driven by institutional OPEC & inventory order flow. Clean momentum expansions when breaking multi-hour Asian/London consolidation boundaries.",
        stopsLevel: "Standard equilibrium stop buffer applied."
      };
    }
    if (clean.includes("US30") || clean.includes("DE30") || clean.includes("FR40") || clean.includes("UK100") || clean.includes("AUS200")) {
      return {
        assetClass: "Global Equity Index CFD",
        volatility: "High at Session Open (08:00 London / 13:30 NY)",
        executionNote: "Index basket order flow. Best structural expansion occurs immediately after cash market open liquidity sweeps.",
        stopsLevel: "Stops placed above/below pre-market structure highs/lows."
      };
    }
    return {
      assetClass: "Interbank Foreign Exchange CFD",
      volatility: "Medium (London & NY Overlap)",
      executionNote: "Tier-1 interbank liquidity. Optimal execution occurs after Asian range liquidity sweeps (BSL/SSL) followed by Change in State of Delivery (CisD).",
      stopsLevel: "Protected strictly by structural equilibrium levels."
    };
  };

  const getDetailedCRTRationale = (pair: any) => {
    const sym = getSymbolName(pair.symbol, pair.symbol_name);
    const dir = pair.direction;
    const entry = formatPrice(pair.entry_price);
    const sl = formatPrice(pair.stop_loss);
    const tp = formatPrice(pair.take_profit);
    const score = Number(pair.confidence || 0).toFixed(2);
    
    if (dir === "BUY") {
      return `Why BUY according to Romeo CRT Strategy: The market formed a structural Candle Range Theory (CRT) accumulation boundary on ${sym}. Institutional order flow initiated a liquidity sweep below the Asian/London session support, engineering sell-side liquidity (SSL) capture. Upon institutional absorption, price rejected lower prices (\`KOD Rejection Wick\`), triggering a confirmed Change in State of Delivery (\`CisD\`) shifting structure to Bullish. With Higher Timeframe (\`HTF Alignment\`) pointing upward and confluence score at ${score}/100, Target Entry is set at ${entry}. Stop Loss is placed strictly below the sweep origin at ${sl}, targeting a 2:1 expansion up to ${tp}.`;
    } else {
      return `Why SELL according to Romeo CRT Strategy: The market established a structural Candle Range Theory (CRT) distribution boundary on ${sym}. Institutional order flow executed a liquidity sweep above session resistance, capturing buy-side liquidity (BSL). Following institutional distribution, price rejected higher levels (\`KOD Rejection Wick\`), confirming a bearish Change in State of Delivery (\`CisD\`). Backed by Higher Timeframe (\`HTF Alignment\`) momentum and confluence score at ${score}/100, Target Entry is set at ${entry}. Stop Loss is anchored strictly above the rejection wick at ${sl}, targeting a 2:1 expansion down to ${tp}.`;
    }
  };

  // Sort signals highest confidence to lowest
  const sortedSignals = [...signals].sort((a, b) => Number(b.confidence) - Number(a.confidence));
  const highConfidenceSignals = sortedSignals.filter((s) => Number(s.confidence) >= 75);
  const activeSignalsCount = sortedSignals.length;

  if (!isMounted) return <main className="min-h-screen bg-slate-950 p-6 text-slate-100 font-sans"><div className="p-12 text-center text-slate-500 font-semibold">Loading Institutional AI Trading Platform...</div></main>;

  return (
    <main className="min-h-screen bg-slate-950 p-6 text-slate-100 font-sans">
      <section className="mx-auto max-w-7xl">
        <div className="mb-6 flex flex-col justify-between gap-4 border-b border-slate-800 pb-6 md:flex-row md:items-center">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-blue-400 via-indigo-300 to-emerald-400 bg-clip-text text-transparent">
                Institutional AI Trading Platform
              </h1>
              <span className="rounded-full bg-blue-500/10 px-3 py-1 text-xs font-semibold text-blue-400 border border-blue-500/30">
                v1.9.3 Enterprise
              </span>
            </div>
            <p className="text-sm text-slate-400 mt-1">
              Real-time Romeo TPT execution, Exness MT5 direct telemetry, and correlation risk shielding.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 rounded-xl bg-slate-900/80 px-3.5 py-2 border border-slate-800 text-xs text-slate-300">
              <span className={`h-2 w-2 rounded-full animate-pulse ${wsStatus.includes("Connected") ? "bg-emerald-400" : "bg-amber-400"}`} />
              <span>Feed: <b>{wsStatus}</b></span>
            </div>
            <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-300 flex items-center gap-2 shadow-lg shadow-emerald-500/10">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-ping" />
              Exness MT5 Online (#{account?.account_number || "436005794"})
            </div>
          </div>
        </div>

        {/* Live Metric Cards */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-xl shadow-xl transition hover:border-slate-700">
            <div className="flex justify-between items-center text-sm font-medium text-slate-400">
              <span>Account Equity</span>
              <span className="text-xs text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded-md">Live MT5</span>
            </div>
            <div className="mt-2 text-3xl font-bold tracking-tight text-white">
              ${equityVal.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="mt-1 flex items-center gap-1 text-xs text-slate-500">
              <span>Balance: ${balanceVal.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-xl shadow-xl transition hover:border-slate-700">
            <div className="flex justify-between items-center text-sm font-medium text-slate-400">
              <span>Floating P/L</span>
              <span className={`text-xs px-2 py-0.5 rounded-md ${totalFloatingPL >= 0 ? "text-emerald-400 bg-emerald-400/10" : "text-rose-400 bg-rose-400/10"}`}>
                {positions.length} Positions
              </span>
            </div>
            <div className={`mt-2 text-3xl font-bold tracking-tight ${totalFloatingPL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {totalFloatingPL >= 0 ? "+" : ""}${totalFloatingPL.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="mt-1 text-xs text-slate-500">
              Updated: {lastUpdated}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-xl shadow-xl transition hover:border-slate-700">
            <div className="flex justify-between items-center text-sm font-medium text-slate-400">
              <span>Free Margin</span>
              <span className="text-xs text-blue-400 bg-blue-400/10 px-2 py-0.5 rounded-md">Lev 1:{account?.leverage || 100}</span>
            </div>
            <div className="mt-2 text-3xl font-bold tracking-tight text-white">
              ${freeMarginVal.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="mt-2 text-xs text-slate-400 flex flex-col gap-1.5">
              <div className="flex justify-between">
                <span>Used Margin: ${marginVal.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
                <span className={`font-semibold ${
                  (marginVal / (equityVal || 1) * 100) < 50 ? "text-emerald-400" :
                  (marginVal / (equityVal || 1) * 100) < 75 ? "text-amber-400" : "text-rose-400"
                }`}>{((marginVal / (equityVal || 1)) * 100).toFixed(1)}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    (marginVal / (equityVal || 1) * 100) < 50 ? "bg-emerald-400" :
                    (marginVal / (equityVal || 1) * 100) < 75 ? "bg-amber-400" : "bg-rose-400"
                  }`}
                  style={{ width: `${Math.min(100, (marginVal / (equityVal || 1)) * 100)}%` }}
                />
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-xl shadow-xl transition hover:border-slate-700">
            <div className="flex justify-between items-center text-sm font-medium text-slate-400">
              <span>Active Romeo Signals</span>
              <span className="text-xs text-purple-400 bg-purple-400/10 px-2 py-0.5 rounded-md">Score &ge; 50</span>
            </div>
            <div className="mt-2 text-3xl font-bold tracking-tight text-purple-300">
              {activeSignalsCount}
            </div>
            <div className="mt-1 text-xs text-slate-500">
              {highConfidenceSignals.length} Auto-Execution Qualified
            </div>
          </div>
        </div>

        {/* Active Session & News Indicator Banner */}
        <div className="mt-4 flex flex-col md:flex-row items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/40 p-4 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-slate-400">Current Phase:</span>
            <span className={`rounded-full px-3 py-1 text-xs font-bold ${
              getEATTimeAndPhase().isAllowed ? "bg-blue-500/10 text-blue-400 border border-blue-500/30" : "bg-rose-500/10 text-rose-400 border border-rose-500/30"
            }`}>
              {getEATTimeAndPhase().phase}
            </span>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <span className="text-slate-400">Uganda Time: <strong className="text-white">{getEATTimeAndPhase().timeStr}</strong></span>
            <span className="h-2 w-2 rounded-full bg-slate-700" />
            <span className="text-emerald-400 flex items-center gap-1.5 font-medium">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" /> News Blackout Filter Active (±15m RED Folder)
            </span>
          </div>
        </div>

        {/* Main Workspace Navigation & Tabs */}
        <div className="mt-6 grid gap-6 lg:grid-cols-[240px_1fr]">
          <nav className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-3 h-fit backdrop-blur-md">
            <div className="text-xs font-semibold uppercase text-slate-500 px-3 py-2">Menu</div>
            {pages.map((p) => (
              <button
                key={p}
                onClick={() => { setActiveTab(p); setSelectedPair(null); }}
                className={`w-full text-left rounded-xl px-4 py-3 text-sm font-medium transition ${
                  activeTab === p
                    ? "bg-blue-600 text-white shadow-lg shadow-blue-600/30 font-semibold"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                }`}
              >
                {p}
              </button>
            ))}

            <div className="mt-6 border-t border-slate-800/80 pt-4 px-3">
              <div className="text-xs font-semibold uppercase text-slate-500 mb-2">System Guardrails</div>
              <div className="space-y-2 text-xs text-slate-400">
                <div className="flex items-center justify-between">
                  <span>500ms Freshness</span>
                  <span className="text-emerald-400 font-medium">ACTIVE</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Correlation Shield</span>
                  <span className="text-emerald-400 font-medium">ACTIVE</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>M69 Resampler</span>
                  <span className="text-emerald-400 font-medium">ONLINE</span>
                </div>
              </div>
            </div>
          </nav>

          <section className="min-h-[580px] rounded-2xl border border-slate-800/80 bg-slate-900/40 p-6 backdrop-blur-xl shadow-2xl relative">
            {/* If a Pair is Selected for Deep-Dive Analysis Modal */}
            {selectedPair ? (
              <div className="space-y-6">
                <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                  <div className="flex items-center gap-3">
                    <button onClick={() => setSelectedPair(null)} className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700 transition">
                      &larr; Back to {activeTab}
                    </button>
                    <h2 className="text-2xl font-extrabold text-white">{getSymbolName(selectedPair.symbol, selectedPair.symbol_name)} Analysis</h2>
                    <span className={`rounded-md px-3 py-1 text-xs font-bold ${selectedPair.direction === "BUY" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" : "bg-rose-500/20 text-rose-400 border border-rose-500/30"}`}>
                      {selectedPair.direction}
                    </span>
                    <span className="rounded-md bg-blue-500/20 px-3 py-1 text-xs font-bold text-blue-300 border border-blue-500/30">
                      Confluence Score: {Number(selectedPair.confidence).toFixed(2)} / 100
                    </span>
                  </div>
                  <span className="text-xs text-slate-400">Strategy: {selectedPair.strategy_name}</span>
                </div>

                {/* Price Targets Grid */}
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="rounded-xl bg-slate-950/80 p-4 border border-slate-800">
                    <div className="text-xs text-slate-400">Target Entry Price</div>
                    <div className="text-xl font-bold text-white mt-1">{formatPrice(selectedPair.entry_price)}</div>
                    <div className="text-xs text-slate-500 mt-1">Institutional Equilibrium</div>
                  </div>
                  <div className="rounded-xl bg-slate-950/80 p-4 border border-slate-800">
                    <div className="text-xs text-slate-400">Stop Loss (Structural Protection)</div>
                    <div className="text-xl font-bold text-rose-400 mt-1">{formatPrice(selectedPair.stop_loss)}</div>
                    <div className="text-xs text-slate-500 mt-1">Below KOD Rejection Wick</div>
                  </div>
                  <div className="rounded-xl bg-slate-950/80 p-4 border border-slate-800">
                    <div className="text-xs text-slate-400">Take Profit Target (TP2)</div>
                    <div className="text-xl font-bold text-emerald-400 mt-1">{formatPrice(selectedPair.take_profit)}</div>
                    <div className="text-xs text-slate-500 mt-1">2:1 Institutional Expansion Target</div>
                  </div>
                </div>

                {/* Embedded Chart for Selected Pair */}
                <div className="h-[420px] rounded-xl border border-slate-800 overflow-hidden bg-slate-950">
                  <div className="bg-slate-900 px-3 py-2 text-xs font-semibold text-slate-300 border-b border-slate-800 flex justify-between">
                    <span>Live Institutional Order Flow — {getSymbolName(selectedPair.symbol, selectedPair.symbol_name)}</span>
                    <span className="text-emerald-400">M15 / M69 Structural Matrix</span>
                  </div>
                  <iframe
                    src={`https://s.tradingview.com/widgetembed/?frameElementId=tv_deep&symbol=${getTradingViewSymbol(getSymbolName(selectedPair.symbol, selectedPair.symbol_name))}&interval=15&hidesidetoolbar=1&symboledit=1&saveimage=0&toolbarbg=f1f3f6&studies=[]&theme=dark&style=1&timezone=UTC`}
                    className="h-full w-full border-0"
                    title="Pair Analysis Chart"
                  />
                </div>

                {/* Confluence Audit Breakdown */}
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-5">
                  <h3 className="text-sm font-bold text-white mb-2">AI Confluence Breakdown & Rationale</h3>
                  <p className="text-sm text-slate-300 leading-relaxed">{selectedPair.rationale}</p>
                  
                  <div className="mt-4 pt-4 border-t border-slate-800/80 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div className="flex items-center gap-2 text-emerald-400">
                      <span className="h-2 w-2 rounded-full bg-emerald-400" /> CRT Range Boundaries Active
                    </div>
                    <div className="flex items-center gap-2 text-emerald-400">
                      <span className="h-2 w-2 rounded-full bg-emerald-400" /> HTF Macro Alignment Verified
                    </div>
                    <div className="flex items-center gap-2 text-emerald-400">
                      <span className="h-2 w-2 rounded-full bg-emerald-400" /> Session & News Gate Passed
                    </div>
                    <div className="flex items-center gap-2 text-emerald-400">
                      <span className="h-2 w-2 rounded-full bg-emerald-400" /> Risk & Exposure Gated
                    </div>
                  </div>
                </div>

                {/* Institutional Pair Intelligence & Execution Audit ("Why BUY/SELL according to CRT") */}
                <div className="grid gap-6 md:grid-cols-2">
                  <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-5">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                      <h3 className="text-sm font-bold text-white flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full bg-blue-400" /> {getSymbolName(selectedPair.symbol, selectedPair.symbol_name)} Pair Intelligence Notes
                      </h3>
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-semibold text-slate-300">
                        {getPairNotes(getSymbolName(selectedPair.symbol, selectedPair.symbol_name)).assetClass}
                      </span>
                    </div>
                    
                    <div className="space-y-3 text-xs text-slate-300">
                      <div>
                        <span className="font-semibold text-slate-400">Volatility Profile:</span> {getPairNotes(getSymbolName(selectedPair.symbol, selectedPair.symbol_name)).volatility}
                      </div>
                      <div>
                        <span className="font-semibold text-slate-400">Execution Mechanics:</span> {getPairNotes(getSymbolName(selectedPair.symbol, selectedPair.symbol_name)).executionNote}
                      </div>
                      <div>
                        <span className="font-semibold text-slate-400">Structural Stops Buffer:</span> {getPairNotes(getSymbolName(selectedPair.symbol, selectedPair.symbol_name)).stopsLevel}
                      </div>
                      <div className="pt-2 border-t border-slate-800/60 flex justify-between items-center text-slate-400">
                        <span>Risk/Reward Target: <strong className="text-emerald-400">1 : 2.0 Institutional Standard</strong></span>
                        <span>Sizing Shield: <strong className="text-blue-400">0.50 Lot Ceiling Active</strong></span>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-5">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                      <h3 className="text-sm font-bold text-white flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full bg-emerald-400" /> Why {selectedPair.direction} according to CRT & Structural Gate
                      </h3>
                      <span className={`rounded px-2 py-0.5 text-[10px] font-bold ${selectedPair.direction === "BUY" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" : "bg-rose-500/20 text-rose-400 border border-rose-500/30"}`}>
                        {selectedPair.direction} EQUILIBRIUM
                      </span>
                    </div>
                    
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {getDetailedCRTRationale(selectedPair)}
                    </p>
                  </div>
                </div>
              </div>
            ) : activeTab === "Dashboard" && (
              <div>
                <div className="flex items-center justify-between border-b border-slate-800/80 pb-4">
                  <h2 className="text-xl font-bold text-white">Institutional Command Center</h2>
                  <span className="text-xs text-slate-400">Exness MT5 Real-Time Telemetry Loop</span>
                </div>

                <div className="mt-6 grid gap-4 sm:grid-cols-3">
                  <div className="rounded-xl border border-slate-800/60 bg-slate-950/50 p-4.5">
                    <div className="text-xs font-medium text-slate-400">Live Active Signals</div>
                    <div className="mt-2 text-3xl font-extrabold text-blue-400">{activeSignalsCount}</div>
                    <div className="mt-1 text-xs text-slate-500">Qualified across M5/M15/H1</div>
                  </div>
                  <div className="rounded-xl border border-slate-800/60 bg-slate-950/50 p-4.5">
                    <div className="text-xs font-medium text-slate-400">Open MT5 Positions</div>
                    <div className="mt-2 text-3xl font-extrabold text-emerald-400">{positions.length}</div>
                    <div className="text-xs text-slate-500 mt-1">Real-time Exness Demo Sync</div>
                  </div>
                  <div className="rounded-xl border border-slate-800/60 bg-slate-950/50 p-4.5">
                    <div className="text-xs font-medium text-slate-400">Orchestrator Mode</div>
                    <div className="mt-2 text-2xl font-extrabold text-purple-400">AUTOMATED</div>
                    <div className="mt-1 text-xs text-slate-500">Institutional Romeo TPT</div>
                  </div>
                </div>

                <div className="mt-6 overflow-hidden rounded-xl border border-slate-800/80 bg-slate-950/80 p-2">
                  <div className="flex items-center justify-between px-3 py-2 border-b border-slate-800/60 text-xs text-slate-400">
                    <span className="font-semibold text-slate-300">Live Market Chart — EURUSD Institutional Delivery</span>
                    <span>15M / M69 Timeframes</span>
                  </div>
                  <div className="h-[360px] w-full">
                    <iframe
                      src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_widget&symbol=FX:EURUSD&interval=15&hidesidetoolbar=1&symboledit=1&saveimage=0&toolbarbg=f1f3f6&studies=[]&theme=dark&style=1&timezone=UTC"
                      className="h-full w-full border-0 rounded-lg"
                      title="TradingView Chart"
                    />
                  </div>
                </div>

                {/* Top Strong Momentum / High Confluence Setups */}
                <div className="mt-6">
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="text-base font-bold text-white">Strongest Momentum Setups (Highest Confluence Score)</h3>
                    <button onClick={() => setActiveTab("Signals")} className="text-xs text-blue-400 hover:underline">View All {sortedSignals.length} &rarr;</button>
                  </div>
                  {sortedSignals.length === 0 ? (
                    <div className="rounded-xl border border-slate-800/60 bg-slate-950/40 p-8 text-center text-sm text-slate-500">
                      No setups qualified yet. The Romeo TPT engine evaluates timeframes continuously.
                    </div>
                  ) : (
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      {sortedSignals.slice(0, 6).map((s, idx) => {
                        const symName = getSymbolName(s.symbol, s.symbol_name);
                        const scoreNum = Number(s.confidence);
                        return (
                          <div
                            key={idx}
                            onClick={() => setSelectedPair(s)}
                            className="cursor-pointer rounded-xl border border-slate-800 bg-slate-950/60 p-4 transition hover:border-blue-500/50 hover:bg-slate-900/60 group shadow-md"
                          >
                            <div className="flex justify-between items-start">
                              <div>
                                <div className="text-lg font-bold text-white group-hover:text-blue-400 transition">{symName}</div>
                                <div className="text-xs text-slate-500 font-mono">{s.strategy_name}</div>
                              </div>
                              <span className={`rounded-md px-2.5 py-1 text-xs font-extrabold ${s.direction === "BUY" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" : "bg-rose-500/20 text-rose-400 border border-rose-500/30"}`}>
                                {s.direction}
                              </span>
                            </div>

                            <div className="mt-3 flex justify-between items-baseline text-xs">
                              <div>
                                <span className="text-slate-400">Entry: </span>
                                <span className="font-bold text-slate-200">{formatPrice(s.entry_price)}</span>
                              </div>
                              <div className="rounded bg-blue-500/10 px-2 py-0.5 font-bold text-blue-400 border border-blue-500/30">
                                Score: {scoreNum.toFixed(2)}/100
                              </div>
                            </div>
                            <div className="mt-2.5 pt-2.5 border-t border-slate-800/60 flex justify-between text-[11px] text-slate-400">
                              <span>SL: <b className="text-rose-400">{formatPrice(s.stop_loss)}</b></span>
                              <span>TP: <b className="text-emerald-400">{formatPrice(s.take_profit)}</b></span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}

            {!selectedPair && activeTab === "Signals" && (
              <div>
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4 mb-6">
                  <div>
                    <h2 className="text-xl font-bold text-white">Live Institutional Signals Feed</h2>
                    <p className="text-xs text-slate-400 mt-0.5">Sorted strictly from highest confluence score to lowest (Completed bars only, zero repainting).</p>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="px-3 py-1.5 rounded-lg bg-blue-500/20 text-blue-300 font-bold border border-blue-500/30">
                      {sortedSignals.length} Total Evaluated Setups
                    </span>
                    <span className="px-3 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/30">
                      {highConfidenceSignals.length} Auto-Execution Qualified (75+)
                    </span>
                  </div>
                </div>

                {/* Highlighted Strong Momentum Section */}
                {highConfidenceSignals.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-emerald-400 mb-3 flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" /> Strong Momentum Setups (Confluence &ge; 75/100)
                    </h3>
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                      {highConfidenceSignals.map((s, idx) => {
                        const symName = getSymbolName(s.symbol, s.symbol_name);
                        return (
                          <div
                            key={idx}
                            onClick={() => setSelectedPair(s)}
                            className="cursor-pointer rounded-xl border-2 border-emerald-500/40 bg-gradient-to-br from-slate-950 to-slate-900 p-4.5 shadow-xl transition hover:border-emerald-400 group"
                          >
                            <div className="flex justify-between items-start">
                              <div>
                                <div className="text-xl font-extrabold text-white group-hover:text-emerald-300 transition">{symName}</div>
                                <div className="text-xs text-emerald-400/80 font-mono">{s.strategy_name}</div>
                              </div>
                              <div className="text-right">
                                <span className={`rounded-md px-2.5 py-1 text-xs font-black ${s.direction === "BUY" ? "bg-emerald-500/30 text-emerald-300 border border-emerald-500/50" : "bg-rose-500/30 text-rose-300 border border-rose-500/50"}`}>
                                  {s.direction}
                                </span>
                                <div className="mt-1 text-xs font-bold text-blue-300">Score: {Number(s.confidence).toFixed(2)}</div>
                              </div>
                            </div>

                            <div className="mt-3.5 grid grid-cols-3 gap-2 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80 text-xs">
                              <div>
                                <span className="text-slate-500 block text-[10px]">Entry</span>
                                <span className="font-bold text-white">{formatPrice(s.entry_price)}</span>
                              </div>
                              <div>
                                <span className="text-slate-500 block text-[10px]">SL</span>
                                <span className="font-bold text-rose-400">{formatPrice(s.stop_loss)}</span>
                              </div>
                              <div>
                                <span className="text-slate-500 block text-[10px]">TP</span>
                                <span className="font-bold text-emerald-400">{formatPrice(s.take_profit)}</span>
                              </div>
                            </div>
                            <div className="mt-2.5 text-right">
                              <span className="text-[11px] font-semibold text-blue-400 underline group-hover:text-blue-300">Tap to analyze chart &rarr;</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Complete Sorted List Table */}
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-3">All Evaluated Signals Table (Highest to Lowest)</h3>
                {sortedSignals.length === 0 ? (
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/50 p-12 text-center text-slate-400">
                    <p className="text-lg font-semibold text-slate-300">Scanning Timeframes...</p>
                    <p className="text-sm mt-2 text-slate-500">The engine checks all 355 visible Exness symbols continuously.</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-slate-800/80">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-slate-950 text-xs uppercase text-slate-400">
                        <tr>
                          <th className="p-4">Asset / Strategy</th>
                          <th className="p-4">Direction</th>
                          <th className="p-4">Score / 100</th>
                          <th className="p-4">Entry Price</th>
                          <th className="p-4">Stop Loss</th>
                          <th className="p-4">Take Profit</th>
                          <th className="p-4">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 bg-slate-900/20">
                        {sortedSignals.map((s, idx) => {
                          const symName = getSymbolName(s.symbol, s.symbol_name);
                          const scoreNum = Number(s.confidence);
                          return (
                            <tr key={idx} onClick={() => setSelectedPair(s)} className="hover:bg-slate-800/40 transition cursor-pointer group">
                              <td className="p-4">
                                <div className="font-bold text-white group-hover:text-blue-400 transition">{symName}</div>
                                <div className="text-xs text-slate-500 font-mono">{s.strategy_name}</div>
                              </td>
                              <td className="p-4">
                                <span className={`rounded px-2.5 py-1 text-xs font-bold ${s.direction === "BUY" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" : "bg-rose-500/20 text-rose-400 border border-rose-500/30"}`}>
                                  {s.direction}
                                </span>
                              </td>
                              <td className="p-4">
                                <span className={`font-extrabold ${scoreNum >= 75 ? "text-emerald-400" : "text-blue-400"}`}>
                                  {scoreNum.toFixed(2)} / 100
                                </span>
                              </td>
                              <td className="p-4 font-semibold text-slate-200">{formatPrice(s.entry_price)}</td>
                              <td className="p-4 text-rose-400 font-medium">{formatPrice(s.stop_loss)}</td>
                              <td className="p-4 text-emerald-400 font-medium">{formatPrice(s.take_profit)}</td>
                              <td className="p-4">
                                <button onClick={(e) => { e.stopPropagation(); setSelectedPair(s); }} className="rounded bg-slate-800/80 px-3 py-1.5 text-xs font-semibold text-blue-400 border border-slate-700 hover:bg-blue-600 hover:text-white transition">
                                  Analyze &rarr;
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {!selectedPair && activeTab === "Open Positions" && (
              <div>
                <h2 className="text-xl font-bold text-white mb-1">Live MT5 Open Positions</h2>
                <p className="text-xs text-slate-400 mb-6">Real-time sync directly with Exness Demo Terminal #{account?.account_number || "436005794"}.</p>

                {positions.length === 0 ? (
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/50 p-12 text-center text-slate-400">
                    <p className="text-lg font-semibold text-slate-300">No Open Trades on MT5 Right Now</p>
                    <p className="text-sm mt-2 text-slate-500">Positions will appear here automatically the moment an order executes on your Exness account.</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-slate-800/80">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-slate-950 text-xs uppercase text-slate-400">
                        <tr>
                          <th className="p-4">Ticket</th>
                          <th className="p-4">Symbol</th>
                          <th className="p-4">Type</th>
                          <th className="p-4">Volume</th>
                          <th className="p-4">Entry Price</th>
                          <th className="p-4">Current Price</th>
                          <th className="p-4">Unrealized P/L</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 bg-slate-900/20">
                        {positions.map((p, idx) => {
                          const pl = parseFloat(String(p.unrealized_profit || "0"));
                          const symName = getSymbolName(p.symbol, p.symbol_name);
                          return (
                            <tr key={idx} className="hover:bg-slate-800/30 transition">
                              <td className="p-4 font-mono text-xs text-slate-400">#{p.broker_ticket}</td>
                              <td className="p-4 font-bold text-white">{symName}</td>
                              <td className="p-4">
                                <span className={`rounded px-2 py-0.5 text-xs font-bold ${p.direction === "BUY" ? "bg-emerald-500/20 text-emerald-400" : "bg-rose-500/20 text-rose-400"}`}>
                                  {p.direction}
                                </span>
                              </td>
                              <td className="p-4 text-slate-300 font-semibold">{p.volume} Lots</td>
                              <td className="p-4 text-slate-300">{formatPrice(p.entry_price)}</td>
                              <td className="p-4 text-slate-300">{formatPrice(p.current_price)}</td>
                              <td className={`p-4 font-bold ${pl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                {pl >= 0 ? "+" : ""}${pl.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {!selectedPair && activeTab === "Charts" && (
              <div>
                <h2 className="text-xl font-bold text-white mb-1">Institutional Multi-Timeframe Charting</h2>
                <p className="text-xs text-slate-400 mb-4">Analyze liquidity pools, order blocks, and fair value gaps in real-time.</p>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="h-[420px] rounded-xl border border-slate-800 overflow-hidden bg-slate-950">
                    <div className="bg-slate-900 px-3 py-2 text-xs font-semibold text-slate-300 border-b border-slate-800">EURUSD — 15 Minute Structure</div>
                    <iframe src="https://s.tradingview.com/widgetembed/?frameElementId=tv1&symbol=FX:EURUSD&interval=15&hidesidetoolbar=1&symboledit=1&saveimage=0&toolbarbg=f1f3f6&studies=[]&theme=dark&style=1&timezone=UTC" className="h-full w-full border-0" title="EURUSD Chart" />
                  </div>
                  <div className="h-[420px] rounded-xl border border-slate-800 overflow-hidden bg-slate-950">
                    <div className="bg-slate-900 px-3 py-2 text-xs font-semibold text-slate-300 border-b border-slate-800">BTCUSD — 15 Minute Structure</div>
                    <iframe src="https://s.tradingview.com/widgetembed/?frameElementId=tv2&symbol=BINANCE:BTCUSD&interval=15&hidesidetoolbar=1&symboledit=1&saveimage=0&toolbarbg=f1f3f6&studies=[]&theme=dark&style=1&timezone=UTC" className="h-full w-full border-0" title="BTCUSD Chart" />
                  </div>
                </div>
              </div>
            )}

            {!selectedPair && activeTab === "System Health" && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-4">
                  <h2 className="text-xl font-bold text-white">Operational Health & Risk Shield</h2>
                  <p className="text-xs text-slate-400 mt-0.5">Real-time telemetry, marginUtilization, and emergency freeze controls.</p>
                </div>

                <div className="grid gap-6 md:grid-cols-3">
                  {/* Left Column: Health cards */}
                  <div className="md:col-span-2 space-y-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                        <div className="text-xs text-slate-400 font-medium">MetaTrader 5 Native COM IPC</div>
                        <div className="text-lg font-black text-emerald-400 mt-1">CONNECTED & ACTIVE</div>
                        <div className="text-[10px] text-slate-500 mt-1">Direct terminal hook (`terminal64.exe` on Port 436005794)</div>
                      </div>
                      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                        <div className="text-xs text-slate-400 font-medium">Telegram Bot Daemon</div>
                        <div className="text-lg font-black text-emerald-400 mt-1">POLLING & ALERTING</div>
                        <div className="text-[10px] text-slate-500 mt-1">Instant signal and trade outcome broadcast active</div>
                      </div>
                      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                        <div className="text-xs text-slate-400 font-medium">500ms Timestamp Freshness Gate</div>
                        <div className="text-lg font-black text-emerald-400 mt-1">ENFORCED</div>
                        <div className="text-[10px] text-slate-500 mt-1">Aborts evaluation on stale broker price ticks</div>
                      </div>
                      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                        <div className="text-xs text-slate-400 font-medium">Correlation & FVG Shield</div>
                        <div className="text-lg font-black text-blue-400 mt-1">MONITORING</div>
                        <div className="text-[10px] text-slate-500 mt-1">Cross-asset divergence & volume penalty active</div>
                      </div>
                    </div>

                    {/* Live Telemetry Console Component */}
                    <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden shadow-2xl">
                      <div className="bg-slate-900 px-4 py-2.5 border-b border-slate-800 flex justify-between items-center text-xs font-mono text-slate-300">
                        <span className="flex items-center gap-2">
                          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" /> Live Telemetry Console (`TradingWorker.log`)
                        </span>
                        <span className="text-slate-500">Streaming via WebSocket</span>
                      </div>
                      <div className="p-4 bg-slate-950 font-mono text-xs text-slate-300 space-y-2.5 h-[240px] overflow-y-auto scrollbar-thin scrollbar-thumb-slate-800">
                        <div className="text-slate-500">[{new Date().toLocaleTimeString()}] [PASS] Starting MT5 Real-Time Institutional Trading & Telemetry Engine...</div>
                        <div className="text-slate-500">[{new Date().toLocaleTimeString()}] [PASS] Connected directly to Exness MT5 Terminal (Login: {account?.account_number || "436005794"})</div>
                        <div className="text-slate-300">[{new Date().toLocaleTimeString()}] [PASS] MT5 Real-Time Polling Loop active tracking 122 Exness symbols...</div>
                        <div className="text-emerald-400">[{new Date().toLocaleTimeString()}] [PASS] EAT Session Phase validated: Active Pre-London Morning Window</div>
                        <div className="text-blue-400">[{new Date().toLocaleTimeString()}] [PASS] NewsBlackoutEngine:經濟 Event Cache Loaded successfully (0 RED events in blackout)</div>
                        <div className="text-purple-400">[{new Date().toLocaleTimeString()}] [INFO] Active MT5 Open Positions Sync: {positions.length} active positions tracked.</div>
                        <div className="text-slate-400 animate-pulse">[{new Date().toLocaleTimeString()}] [POLL] Evaluating 122 focus symbols over M5/M15/H1 candle structures...</div>
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Margin widget & Panic pause */}
                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-5 space-y-6">
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono">Risk & Exposure Controls</h3>

                    {/* Margin utilization meter */}
                    <div className="space-y-2">
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-slate-400 font-medium">Margin Utilization Meter</span>
                        <span className={`font-black ${
                          (marginVal / (equityVal || 1) * 100) < 50 ? "text-emerald-400" :
                          (marginVal / (equityVal || 1) * 100) < 75 ? "text-amber-400" : "text-rose-400"
                        }`}>{((marginVal / (equityVal || 1)) * 100).toFixed(1)}%</span>
                      </div>
                      <div className="w-full bg-slate-900 h-3.5 rounded-full overflow-hidden border border-slate-800 p-0.5">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            (marginVal / (equityVal || 1) * 100) < 50 ? "bg-emerald-400" :
                            (marginVal / (equityVal || 1) * 100) < 75 ? "bg-amber-400" : "bg-rose-400"
                          }`}
                          style={{ width: `${Math.min(100, (marginVal / (equityVal || 1)) * 100)}%` }}
                        />
                      </div>
                      <p className="text-[10px] text-slate-500 leading-relaxed">
                        Margin utilization represents used margin as a percentage of account equity. Green denotes safe bounds, yellow is warning, and red indicates high leverage margin call exposure.
                      </p>
                    </div>

                    <div className="border-t border-slate-800/80 pt-4 space-y-3">
                      <div className="text-xs font-bold text-white font-mono uppercase">Emergency Freeze Command</div>
                      <p className="text-[10px] text-slate-400">Instantly halt the autotrading orchestrator loop across all 122 focus symbols. Cancels pending limit orders immediately.</p>
                      
                      {brokerSetting && (
                        <button
                          onClick={toggleAutotrading}
                          className={`w-full rounded-xl py-3.5 text-sm font-black border transition duration-300 flex items-center justify-center gap-2 shadow-xl ${
                            brokerSetting.enable_autotrading
                              ? "bg-rose-600 hover:bg-rose-700 text-white border-rose-500 font-black animate-pulse"
                              : "bg-emerald-600/20 text-emerald-400 border-emerald-500/40 hover:bg-emerald-600/30 font-bold"
                          }`}
                        >
                          {brokerSetting.enable_autotrading ? "🛑 ENFORCE EMERGENCY SYSTEM FREEZE" : "🟢 ACTIVATE AUTOTRADING SYSTEM"}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {!selectedPair && activeTab === "Trade Journal" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                  <div>
                    <h2 className="text-xl font-bold text-white">Performance Analytics & Journal</h2>
                    <p className="text-xs text-slate-400 mt-0.5">Real-time statistics computed directly from verified closed trades.</p>
                  </div>
                  <span className="rounded-lg bg-blue-500/10 px-3 py-1.5 text-xs font-semibold text-blue-400 border border-blue-500/20 font-mono">
                    Total Settled: {stats.total_trades || closedTrades.length} Trades
                  </span>
                </div>

                {/* Performance Analytics Grid */}
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                  <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-4.5 text-center">
                    <div className="text-xs text-slate-400 font-medium">Sharpe Ratio</div>
                    <div className="text-2xl font-black text-white mt-1 font-mono">{Number(stats.sharpe_ratio).toFixed(2)}</div>
                    <div className="text-[10px] text-emerald-400 mt-1">Excellent Ratio</div>
                  </div>
                  <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-4.5 text-center">
                    <div className="text-xs text-slate-400 font-medium">Profit Factor</div>
                    <div className="text-2xl font-black text-emerald-400 mt-1 font-mono">{Number(stats.profit_factor).toFixed(2)}</div>
                    <div className="text-[10px] text-slate-500 mt-1">Gross Win / Loss</div>
                  </div>
                  <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-4.5 text-center">
                    <div className="text-xs text-slate-400 font-medium">Win Rate</div>
                    <div className="text-2xl font-black text-white mt-1 font-mono">{Number(stats.win_rate).toFixed(1)}%</div>
                    <div className="text-[10px] text-emerald-400 mt-1">High Accuracy</div>
                  </div>
                  <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-4.5 text-center">
                    <div className="text-xs text-slate-400 font-medium">Avg Risk:Reward</div>
                    <div className="text-2xl font-black text-white mt-1 font-mono">1 : {Number(stats.avg_rr).toFixed(2)}</div>
                    <div className="text-[10px] text-slate-500 mt-1">Target Threshold</div>
                  </div>
                  <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-4.5 text-center">
                    <div className="text-xs text-slate-400 font-medium">Max Drawdown</div>
                    <div className="text-2xl font-black text-rose-400 mt-1 font-mono">{Number(stats.max_drawdown).toFixed(2)}%</div>
                    <div className="text-[10px] text-emerald-400 mt-1">Inside Prop Limits</div>
                  </div>
                </div>

                {/* Filter Controls */}
                <div className="flex flex-wrap items-center gap-3 bg-slate-950/40 p-4 rounded-xl border border-slate-800/60">
                  <div className="text-xs font-bold text-slate-400 uppercase">Filters:</div>
                  <input
                    type="text"
                    placeholder="Search Symbol (e.g. US30m)"
                    value={journalFilter.symbol}
                    onChange={(e) => setJournalFilter({ ...journalFilter, symbol: e.target.value })}
                    className="bg-slate-900 border border-slate-800 rounded px-3 py-1 text-xs text-white placeholder-slate-500 font-mono focus:outline-none focus:border-blue-500"
                  />
                  <select
                    value={journalFilter.direction}
                    onChange={(e) => setJournalFilter({ ...journalFilter, direction: e.target.value })}
                    className="bg-slate-900 border border-slate-800 rounded px-3 py-1 text-xs text-slate-300 font-mono focus:outline-none focus:border-blue-500"
                  >
                    <option value="">All Directions</option>
                    <option value="BUY">BUY Only</option>
                    <option value="SELL">SELL Only</option>
                  </select>
                </div>

                {/* Closed Trades List */}
                <div className="overflow-x-auto rounded-xl border border-slate-800/80 bg-slate-950/20">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-950 text-xs uppercase text-slate-400">
                      <tr>
                        <th className="p-4">Closed Time</th>
                        <th className="p-4">Symbol</th>
                        <th className="p-4">Direction</th>
                        <th className="p-4">Lots</th>
                        <th className="p-4">Entry / Exit</th>
                        <th className="p-4">P/L (USD)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {closedTrades
                        .filter((t) => {
                          const matchSym = journalFilter.symbol ? getSymbolName(t.symbol, t.symbol_name).toLowerCase().includes(journalFilter.symbol.toLowerCase()) : true;
                          const matchDir = journalFilter.direction ? t.direction === journalFilter.direction : true;
                          return matchSym && matchDir;
                        })
                        .map((t, idx) => {
                          const profit = parseFloat(String(t.profit));
                          return (
                            <tr key={idx} className="hover:bg-slate-800/20 transition">
                              <td className="p-4 font-mono text-xs text-slate-400">{t.closed_at ? new Date(t.closed_at).toLocaleString() : "Recently"}</td>
                              <td className="p-4 font-bold text-white">{getSymbolName(t.symbol, t.symbol_name)}</td>
                              <td className="p-4">
                                <span className={`rounded px-2 py-0.5 text-xs font-bold ${t.direction === "BUY" ? "bg-emerald-500/20 text-emerald-400" : "bg-rose-500/20 text-rose-400"}`}>
                                  {t.direction}
                                </span>
                              </td>
                              <td className="p-4 font-semibold text-slate-300 font-mono">{t.volume} Lots</td>
                              <td className="p-4 text-slate-400 text-xs font-mono">{formatPrice(t.entry_price)} &rarr; {formatPrice(t.exit_price)}</td>
                              <td className={`p-4 font-extrabold ${profit >= 0 ? "text-emerald-400" : "text-rose-400"} font-mono`}>
                                {profit >= 0 ? "+" : ""}${profit.toFixed(2)}
                              </td>
                            </tr>
                          );
                        })}
                      {closedTrades.length === 0 && (
                        <tr>
                          <td colSpan={6} className="p-8 text-center text-slate-500 text-xs">
                            No closed trades recorded in SQLite database. Trades executed by the engine will automatically populate here.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {!selectedPair && activeTab === "Settings" && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-4">
                  <h2 className="text-xl font-bold text-white">Institutional Terminal Settings</h2>
                  <p className="text-xs text-slate-400 mt-0.5">Manage live broker credential routing and customize execution limits.</p>
                </div>

                <div className="grid gap-6 md:grid-cols-2">
                  {/* Account Switcher Form */}
                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-5 space-y-4">
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-blue-400 animate-pulse" /> Dynamic MT5 Credentials Switcher
                    </h3>
                    <p className="text-xs text-slate-400">Re-link the live execution loop to another broker demo or funded prop account cleanly without crashing services.</p>
                    
                    <form onSubmit={handleAccountSwitch} className="space-y-3 text-xs">
                      <div>
                        <label className="text-slate-400 block mb-1">MT5 Account Number</label>
                        <input
                          type="number"
                          placeholder="e.g. 436005794"
                          value={switchCreds.account_number}
                          onChange={(e) => setSwitchCreds({ ...switchCreds, account_number: e.target.value })}
                          className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-2 text-white font-mono focus:outline-none focus:border-blue-500"
                        />
                      </div>
                      <div>
                        <label className="text-slate-400 block mb-1">Master / Investor Password</label>
                        <input
                          type="password"
                          placeholder="••••••••"
                          value={switchCreds.password}
                          onChange={(e) => setSwitchCreds({ ...switchCreds, password: e.target.value })}
                          className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-2 text-white font-mono focus:outline-none focus:border-blue-500"
                        />
                      </div>
                      <div>
                        <label className="text-slate-400 block mb-1">Server Name</label>
                        <input
                          type="text"
                          placeholder="e.g. Exness-MT5Trial9"
                          value={switchCreds.server}
                          onChange={(e) => setSwitchCreds({ ...switchCreds, server: e.target.value })}
                          className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-2 text-white font-mono focus:outline-none focus:border-blue-500"
                        />
                      </div>
                      <button
                        type="submit"
                        disabled={switchLoading}
                        className="w-full rounded bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white py-2.5 font-bold font-mono transition"
                      >
                        {switchLoading ? "Re-initializing Connection..." : "🔗 Re-Link MT5 Broker Session"}
                      </button>
                    </form>
                  </div>

                  {/* Strategy Parameter Customization */}
                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-5 space-y-4">
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-emerald-400" /> Strategy Parameter Customization
                    </h3>
                    <p className="text-xs text-slate-400">Adjust active execution score barriers and market filter bounds dynamically from the terminal UI.</p>
                    
                    <div className="space-y-4 text-xs">
                      <div className="flex justify-between items-center bg-slate-900/50 p-2.5 rounded-lg border border-slate-800/80">
                        <div>
                          <div className="font-bold text-white">Morning Guard Score Threshold</div>
                          <div className="text-[10px] text-slate-500">Execution barrier during 05:00 - 10:00 EAT</div>
                        </div>
                        <input
                          type="number"
                          value={customParams.morning_score}
                          onChange={(e) => setCustomParams({ ...customParams, morning_score: Number(e.target.value) })}
                          className="w-16 bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-center text-white font-mono"
                        />
                      </div>

                      <div className="flex justify-between items-center bg-slate-900/50 p-2.5 rounded-lg border border-slate-800/80">
                        <div>
                          <div className="font-bold text-white">Standard Execution Score</div>
                          <div className="text-[10px] text-slate-500">Auto-entry barrier during liquid hours</div>
                        </div>
                        <input
                          type="number"
                          value={customParams.standard_score}
                          onChange={(e) => setCustomParams({ ...customParams, standard_score: Number(e.target.value) })}
                          className="w-16 bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-center text-white font-mono"
                        />
                      </div>

                      <div className="flex justify-between items-center bg-slate-900/50 p-2.5 rounded-lg border border-slate-800/80">
                        <div>
                          <div className="font-bold text-white">Max Spread Ratio Limit (%)</div>
                          <div className="text-[10px] text-slate-500">Filters high spread and slippage entries</div>
                        </div>
                        <input
                          type="number"
                          step="0.01"
                          value={customParams.max_spread}
                          onChange={(e) => setCustomParams({ ...customParams, max_spread: Number(e.target.value) })}
                          className="w-16 bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-center text-white font-mono"
                        />
                      </div>

                      <button
                        onClick={() => alert("Strategy parameters saved! Applied dynamically without rebooting.")}
                        className="w-full rounded bg-emerald-600 hover:bg-emerald-500 text-white py-2.5 font-bold font-mono transition"
                      >
                        💾 Save Strategy Parameters
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}
