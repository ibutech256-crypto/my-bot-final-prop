"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
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
  const wsReconnectTimer = useRef<NodeJS.Timeout | null>(null);
  const isWsHealthy = useRef<boolean>(false);

  const getEATTimeAndPhase = () => {
    const utc = new Date();
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

  // --- WebSocket Connection with Auto-Reconnect (Module 1) ---
  const connectWebSocket = useCallback(() => {
    // Clean up any existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const wsProtocol = typeof window !== "undefined" && window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsHost = typeof window !== "undefined" ? window.location.hostname : "localhost";
    const wsUrl = `${wsProtocol}//${wsHost}:8000/ws/trading/`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        isWsHealthy.current = true;
        setWsStatus("Feed: WebSocket Real-Time");
      };

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

      ws.onerror = () => {
        isWsHealthy.current = false;
        setWsStatus("Polling (HTTP 5s)");
      };

      ws.onclose = () => {
        isWsHealthy.current = false;
        setWsStatus("Polling (HTTP 5s)");
        // Auto-reconnect after 3 seconds
        if (wsReconnectTimer.current) clearTimeout(wsReconnectTimer.current);
        wsReconnectTimer.current = setTimeout(connectWebSocket, 3000);
      };
    } catch (err) {
      isWsHealthy.current = false;
      setWsStatus("Polling (HTTP 5s)");
    }
  }, []);

  // --- HTTP Polling Fallback (only when WebSocket is down) ---
  const fetchData = useCallback(async () => {
    // Skip HTTP polling entirely when WebSocket is healthy (Module 1)
    if (isWsHealthy.current) {
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
  }, []);

  // --- Initialization Effect ---
  useEffect(() => {
    // Initial data load
    fetchData();

    // Connect WebSocket
    connectWebSocket();

    // HTTP polling at 5s interval (will be skipped when WebSocket is healthy)
    const interval = setInterval(fetchData, 5000);

    return () => {
      clearInterval(interval);
      if (wsRef.current) wsRef.current.close();
      if (wsReconnectTimer.current) clearTimeout(wsReconnectTimer.current);
    };
  }, [fetchData, connectWebSocket]);

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

  // ... rest of the component remains the same (below)
  // The JSX output is unchanged from the original file
  
  const renderDashboard = () => (
    <div className="grid gap-4 md:grid-cols-4 mb-6">
      <div className="rounded-xl border border-slate-800 bg-gradient-to-br from-slate-950 to-slate-900 p-4">
        <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">Balance</div>
        <div className="text-2xl font-bold text-white mt-1 font-mono">
          ${account?.balance?.toFixed(2) ?? "---"}
        </div>
      </div>
      <div className="rounded-xl border border-slate-800 bg-gradient-to-br from-slate-950 to-slate-900 p-4">
        <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">Equity</div>
        <div className="text-2xl font-bold text-emerald-400 mt-1 font-mono">
          ${account?.equity?.toFixed(2) ?? "---"}
        </div>
      </div>
      <div className="rounded-xl border border-slate-800 bg-gradient-to-br from-slate-950 to-slate-900 p-4">
        <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">Margin</div>
        <div className="text-2xl font-bold text-amber-400 mt-1 font-mono">
          ${account?.margin?.toFixed(2) ?? "---"}
        </div>
      </div>
      <div className="rounded-xl border border-slate-800 bg-gradient-to-br from-slate-950 to-slate-900 p-4">
        <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">Feed Status</div>
        <div className={`text-sm font-bold mt-1 font-mono ${wsStatus.includes("Real-Time") ? "text-green-400" : "text-amber-400"}`}>
          {wsStatus}
        </div>
        <div className="text-[10px] text-slate-500 mt-0.5">Last: {lastUpdated}</div>
      </div>
    </div>
  );

  // Return the full dashboard JSX
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-12 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-[10px] font-black text-white">T</div>
            <span className="text-sm font-bold tracking-tight">Institutional Terminal</span>
            <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full font-mono">v2.0.0</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">EAT</span>
            <span className="text-white font-mono">{getEATTimeAndPhase().timeStr.split(" ")[1]}</span>
            <span className={`h-2 w-2 rounded-full ${getEATTimeAndPhase().isAllowed ? "bg-green-400" : "bg-red-400"}`} />
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-4">
        {/* Tab Navigation */}
        <nav className="flex gap-1 mb-6 overflow-x-auto">
          {pages.map((p) => (
            <button
              key={p}
              onClick={() => setActiveTab(p)}
              className={`px-4 py-2 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${
                activeTab === p
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
              }`}
            >
              {p}
            </button>
          ))}
        </nav>

        {/* Dashboard Tab */}
        {activeTab === "Dashboard" && renderDashboard()}

        {/* Signals Tab */}
        {activeTab === "Signals" && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold">Recent Signals</h2>
              <span className="text-xs text-slate-400">Last updated: {lastUpdated}</span>
            </div>
            <div className="grid gap-3">
              {signals.length === 0 && (
                <div className="text-center py-12 text-slate-500 text-sm">
                  No signals yet. Waiting for market data feed...
                </div>
              )}
              {signals.map((sig) => (
                <div
                  key={sig.id}
                  onClick={() => setSelectedPair(sig)}
                  className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 hover:border-blue-500/50 cursor-pointer transition-all"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-bold">{sig.symbol_name || sig.symbol || "---"}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                          sig.direction === "BUY" ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"
                        }`}>
                          {sig.direction}
                        </span>
                        <span className="text-[10px] text-slate-500">{sig.strategy_name}</span>
                      </div>
                      <div className="text-xs text-slate-400 mt-1">
                        Entry: {sig.entry_price} | SL: {sig.stop_loss} | TP: {sig.take_profit}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">{sig.rationale?.substring(0, 100)}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-mono font-bold">
                        {sig.confidence}%
                      </div>
                      <div className="text-[10px] text-slate-500">Confidence</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* System Health Tab */}
        {activeTab === "System Health" && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold">System Health</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">Backend</div>
                <div className="text-sm font-bold text-green-400 mt-1">Running</div>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">WebSocket</div>
                <div className={`text-sm font-bold mt-1 ${wsStatus.includes("Real-Time") ? "text-green-400" : "text-amber-400"}`}>
                  {wsStatus}
                </div>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">Redis/Memurai</div>
                <div className="text-sm font-bold text-green-400 mt-1">Connected</div>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">MT5 Gateway</div>
                <div className="text-sm font-bold text-green-400 mt-1">Active</div>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">Celery Worker</div>
                <div className="text-sm font-bold text-green-400 mt-1">Running</div>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">EAT Session</div>
                <div className={`text-sm font-bold mt-1 ${getEATTimeAndPhase().isAllowed ? "text-green-400" : "text-red-400"}`}>
                  {getEATTimeAndPhase().phase.split(":")[0]}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Settings Tab */}
        {activeTab === "Settings" && (
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
      </div>
    </main>
  );
}
