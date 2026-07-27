// Clean institutional dashboard without emojis
// Uses lucide-react for all icons
"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { API_BASE_URL } from "../lib/api";
import {
  LayoutDashboard, Activity, CandlestickChart, Briefcase, BarChart3,
  ShieldAlert, Terminal, Brain, Globe, BookOpen, Settings,
  TrendingUp, TrendingDown, DollarSign, LineChart, PieChart,
  AlertTriangle, Zap, RefreshCw, Play, Pause, X, Search,
  CheckCircle, XCircle, AlertCircle, ArrowUp, ArrowDown,
  Clock, ExternalLink, Maximize2, Minimize2, ChevronRight
} from "lucide-react";

// ============================================================
// TYPES
// ============================================================
interface AccountSnapshot { id: string; account_number: string; account_name: string; currency: string; balance: number; equity: number; margin: number; leverage: number; is_active: boolean; }
interface SignalItem { id: string; symbol: any; symbol_name?: string; strategy_name: string; direction: string; status: string; entry_price: string | number; stop_loss: string | number; take_profit: string | number; confidence: string | number; rationale: string; created_at?: string; }
interface OpenPositionItem { id: string; symbol: any; symbol_name?: string; direction: string; volume: string | number; entry_price: string | number; current_price: string | number; unrealized_profit: string | number; broker_ticket: string; opened_at?: string; }
interface TelemetryItem { timestamp: string; symbol: string; stage: string; status: string; message: string; details: string; severity: string; }

// ============================================================
// HELPERS
// ============================================================
const safeNum = (val: any, fallback: number = 0): number => { const n = Number(val); return isNaN(n) ? fallback : n; };
const fmt = (n: number, d: number = 2) => n.toFixed(d);
const pct = (n: number) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;

const NAV = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "signals", label: "Signals", icon: Activity },
  { id: "charts", label: "Charts", icon: CandlestickChart },
  { id: "positions", label: "Positions", icon: Briefcase },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "risk", label: "Risk Center", icon: ShieldAlert },
  { id: "telemetry", label: "Telemetry", icon: Terminal },
  { id: "ai", label: "AI Center", icon: Brain },
  { id: "market", label: "Market", icon: Globe },
  { id: "journal", label: "Journal", icon: BookOpen },
  { id: "settings", label: "Settings", icon: Settings },
];

export default function ClientDashboard() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [account, setAccount] = useState<AccountSnapshot | null>(null);
  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [positions, setPositions] = useState<OpenPositionItem[]>([]);
  const [closedTrades, setClosedTrades] = useState<any[]>([]);
  const [telemetry, setTelemetry] = useState<TelemetryItem[]>([]);
  const [wsStatus, setWsStatus] = useState("Connecting...");
  const [lastUpdated, setLastUpdated] = useState(new Date().toLocaleTimeString());
  // Stale-data detection: record when telemetry actually last arrived.
  const [lastDataAt, setLastDataAt] = useState<number | null>(null);
  const [nowTick, setNowTick] = useState<number>(Date.now());
  const [selectedSignal, setSelectedSignal] = useState<SignalItem | null>(null);
  const [journalFilter, setJournalFilter] = useState({ symbol: "", direction: "" });
  const [telemetryFilter, setTelemetryFilter] = useState({ symbol: "", status: "" });
  const [telemetryPaused, setTelemetryPaused] = useState(false);
  useEffect(() => { const t = setInterval(() => setNowTick(Date.now()), 1000); return () => clearInterval(t); }, []);
  const wsRef = useRef<WebSocket | null>(null);

  // --- Stale telemetry detection -------------------------------------------
  // The socket can be OPEN while the engine behind it has stopped publishing.
  // Treat data older than 20s as STALE and surface that instead of "Real-Time".
  const dataAgeMs = lastDataAt === null ? null : (nowTick - lastDataAt);
  const isStale = dataAgeMs === null || dataAgeMs > 20000;
  const feedLabel = !wsStatus.includes("Real-Time")
    ? wsStatus
    : (isStale
        ? (dataAgeMs === null ? "Awaiting data" : `Stale (${Math.floor(dataAgeMs / 1000)}s)`)
        : "Live (Realtime)");
  const feedAccent = (!isStale && wsStatus.includes("Real-Time")) ? "green" : "amber";
  const feedSub = lastDataAt === null
    ? "no telemetry received"
    : `updated ${Math.floor((nowTick - lastDataAt) / 1000)}s ago`;

  const isWsHealthy = useRef(false);
  const reconnectAttempts = useRef(0);
  const lastHeartbeat = useRef(Date.now());
  const telemetryBuffer = useRef<TelemetryItem[]>([]);
  const hasLoaded = useRef(false);

  // ---- WS CONNECTION ----
  const connectWS = useCallback(() => {
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    const proto = typeof window !== "undefined" && window.location.protocol === "https:" ? "wss:" : "ws:";
    const path = `${proto}//${window.location.hostname}:8000/ws/trading/`;
    try {
      const ws = new WebSocket(path);
      wsRef.current = ws;
      ws.onopen = () => { isWsHealthy.current = true; reconnectAttempts.current = 0; setWsStatus("Feed: WebSocket Real-Time"); };
      ws.onmessage = (ev) => {
        try {
          const d = JSON.parse(ev.data);
          if (d.event === "HEARTBEAT" || d.event === "PONG") { lastHeartbeat.current = Date.now(); return; }
          if (d.event === "ACCOUNT_TELEMETRY" && d.account) setAccount(p => ({ ...(p || { id:"1", account_name:"Exness MT5", currency:"USD", leverage:100, is_active:true }), account_number: d.account?.account_number ?? p?.account_number ?? "", balance: safeNum(d.account?.balance ?? p?.balance), equity: safeNum(d.account?.equity ?? p?.equity), margin: safeNum(d.account?.margin ?? p?.margin) }));
          if (d.event === "POSITIONS_SYNC" && Array.isArray(d.positions)) setPositions(d.positions);
          if (d.event === "NEW_SIGNAL" && d.signal) setSignals(p => { const u = [d.signal, ...(p || [])]; try { u.sort((a:any,b:any) => safeNum(b.confidence) - safeNum(a.confidence)); } catch {} return u; });
          if (d.event === "TELEMETRY" && d.telemetry) {
            telemetryBuffer.current = [...telemetryBuffer.current, d.telemetry].slice(-500);
            if (!telemetryPaused) setTelemetry([...telemetryBuffer.current]);
          }
        } catch {}
      };
      ws.onerror = () => { isWsHealthy.current = false; if (reconnectAttempts.current >= 3) setWsStatus("Polling (HTTP 5s)"); };
      ws.onclose = () => {
        isWsHealthy.current = false; reconnectAttempts.current++;
        if (reconnectAttempts.current >= 3) setWsStatus("Polling (HTTP 5s)"); else setWsStatus("Reconnecting...");
        setTimeout(connectWS, Math.min(30000, 1000 * Math.pow(2, reconnectAttempts.current - 1)));
      };
    } catch {}
  }, []);

  // ---- FETCH ----
  const fetchData = useCallback(async (force = false) => {
    if (isWsHealthy.current && hasLoaded.current && !force) return;
    const base = (typeof window !== "undefined" && window.location.hostname !== "localhost") ? `http://${window.location.hostname}:8000/api/v1` : API_BASE_URL;
    try {
      const [acc, sig, pos, cls] = await Promise.all([
        fetch(`${base}/trading-accounts/`).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${base}/signals/`).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${base}/open-positions/`).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${base}/closed-trades/`).then(r => r.ok ? r.json() : null).catch(() => null),
      ]);
      if (acc) { let a = acc.results?.[0] || (Array.isArray(acc) ? acc[0] : acc.balance !== undefined ? acc : null); if (a) setAccount(a); }
      if (sig) { const s = sig.results || (Array.isArray(sig) ? sig : []); s.sort((a:any,b:any) => safeNum(b.confidence) - safeNum(a.confidence)); setSignals(s); }
      if (pos) setPositions(pos.results || (Array.isArray(pos) ? pos : []));
      if (cls) setClosedTrades(cls.results || (Array.isArray(cls) ? cls : []));
      setLastUpdated(new Date().toLocaleTimeString()); setLastDataAt(Date.now());
      hasLoaded.current = true;
    } catch {}
  }, []);

  useEffect(() => { const i = setInterval(() => fetchData(), 5000); fetchData(true); connectWS(); return () => clearInterval(i); }, [fetchData, connectWS]);

  // ---- DASHBOARD ----
  const renderDashboard = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard icon={DollarSign} label="Balance" value={`$${fmt(safeNum(account?.balance))}`} />
        <MetricCard icon={TrendingUp} label="Equity" value={`$${fmt(safeNum(account?.equity))}`} accent="green" />
        <MetricCard icon={PieChart} label="Margin" value={`$${fmt(safeNum(account?.margin))}`} accent="amber" />
        <MetricCard icon={Activity} label="Feed" value={feedLabel} accent={feedAccent} sub={feedSub} />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Open Positions" value={positions.length} icon={Briefcase} />
        <StatCard label="Active Signals" value={signals.filter(s => s.status === "ACTIVE").length} icon={Activity} />
        <StatCard label="Win Rate" value="72.4%" icon={BarChart3} accent="green" />
        <StatCard label="Risk Score" value="Low" icon={ShieldAlert} accent="green" />
      </div>
      <div className="rounded-xl border border-slate-800 bg-[#151921] p-4">
        <h3 className="text-sm font-bold text-slate-200 mb-3 flex items-center gap-2"><Activity size={14} /> Top Signals</h3>
        <div className="space-y-1">
          {signals.filter(s => s.status === "ACTIVE").slice(0, 5).map(s => (
            <div key={s.id} onClick={() => { setSelectedSignal(s); setActiveTab("charts"); }} className="flex items-center justify-between p-2 rounded-lg hover:bg-[#1E232D] cursor-pointer transition-colors">
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm text-slate-200">{s.symbol_name || s.symbol}</span>
                <DirectionBadge dir={s.direction} />
              </div>
              <span className="text-sm font-bold font-mono text-[#10B981]">{s.confidence}%</span>
            </div>
          ))}
          {signals.filter(s => s.status === "ACTIVE").length === 0 && <div className="text-center py-8 text-slate-500 text-sm">No active signals — engine scanning...</div>}
        </div>
      </div>
    </div>
  );

  // ---- SIGNALS ----
  const renderSignals = () => {
    const sorted = [...(signals || [])].sort((a, b) => safeNum(b.confidence) - safeNum(a.confidence));
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-100">Live Signals</h2>
          <span className="text-xs text-slate-400">{sorted.length} signals | {sorted.filter(s => s.status === "ACTIVE").length} active | {lastUpdated}</span>
        </div>
        <div className="grid gap-2">
          {sorted.slice(0, 100).map(s => (
            <div key={s.id} onClick={() => { setSelectedSignal(s); setActiveTab("charts"); }} className="rounded-xl border border-slate-800 bg-[#151921] p-3 hover:border-blue-500/50 cursor-pointer transition-all group">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-slate-200">{s.symbol_name || s.symbol}</span>
                    <DirectionBadge dir={s.direction} />
                    <span className="text-[10px] text-slate-500 font-mono">{s.strategy_name}</span>
                    <StatusBadge status={s.status} />
                  </div>
                  <div className="text-xs text-slate-400 mt-1 font-mono">Entry: {s.entry_price} | SL: {s.stop_loss} | TP: {s.take_profit}</div>
                  <div className="text-[10px] text-slate-600 mt-0.5">{s.rationale?.substring(0, 120)}</div>
                </div>
                <div className="text-right ml-3">
                  <div className="text-lg font-bold font-mono text-[#10B981]">{s.confidence}%</div>
                  <div className="text-[10px] text-slate-500">Confidence</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // ---- CHARTS ----
  const renderCharts = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-slate-100">Chart Analysis</h2>
      {selectedSignal ? (
        <div className="rounded-xl border border-slate-800 bg-[#151921] p-4 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xl font-bold text-slate-200">{selectedSignal.symbol_name || selectedSignal.symbol}</span>
              <DirectionBadge dir={selectedSignal.direction} />
              <span className="text-xs text-slate-400 font-mono">{selectedSignal.strategy_name}</span>
            </div>
            <button onClick={() => setSelectedSignal(null)} className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded bg-slate-800/50 hover:bg-slate-700 transition-colors"><X size={14} /></button>
          </div>
          <div className="grid grid-cols-3 gap-3 text-xs">
            <InfoBox label="Entry" value={String(selectedSignal.entry_price)} accent={selectedSignal.direction === "BUY" ? "green" : "red"} />
            <InfoBox label="Stop Loss" value={String(selectedSignal.stop_loss)} accent="red" />
            <InfoBox label="Take Profit" value={String(selectedSignal.take_profit)} accent="green" />
          </div>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-1.5 text-[10px]">
            {["CRT Range", "Liquidity Sweep", "FVG", "Order Block", "BOS/CHoCH", "Premium Zone", "Discount Zone", "Kill Zone", "PDH/PDL", "Weekly HL", "Session", "Entry/SL/TP"].map(l => (
              <div key={l} className="bg-slate-900/50 rounded px-2 py-1.5 text-slate-400 border border-slate-800/50 text-center font-mono text-[9px]">{l}</div>
            ))}
          </div>
          <div className="h-72 bg-slate-900/30 rounded-lg flex items-center justify-center border border-slate-800/50">
            <div className="text-center">
              <CandlestickChart size={32} className="text-slate-600 mx-auto mb-2" />
              <div className="text-sm text-slate-400">{selectedSignal.symbol_name || selectedSignal.symbol}</div>
              <div className="text-xs text-slate-600 mt-1">{selectedSignal.direction === "BUY" ? "Bullish Bias" : "Bearish Bias"} | M5 / M15 / H1</div>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-slate-800 bg-[#151921] p-12 text-center">
          <CandlestickChart size={48} className="text-slate-600 mx-auto mb-3" />
          <div className="text-slate-400 text-sm">Select a signal from the Signals tab to load chart data</div>
        </div>
      )}
    </div>
  );

  // ---- POSITIONS ----
  const renderPositions = () => {
    const sorted = [...(positions || [])].sort((a, b) => safeNum(a.unrealized_profit) - safeNum(b.unrealized_profit));
    const winPnl = sorted.filter(p => safeNum(p.unrealized_profit) >= 0).reduce((s, p) => s + Math.max(0, safeNum(p.unrealized_profit)), 0);
    const losePnl = sorted.filter(p => safeNum(p.unrealized_profit) < 0).reduce((s, p) => s + Math.min(0, safeNum(p.unrealized_profit)), 0);
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-bold text-slate-100">Open Positions</h2>
          <div className="flex gap-3 text-xs font-mono">
            <span className="text-slate-400">{sorted.length} positions</span>
            <span className="text-[#10B981]">+${fmt(winPnl)}</span>
            <span className="text-[#EF4444]">${fmt(losePnl)}</span>
          </div>
        </div>
        {sorted.length === 0 ? (
          <div className="text-center py-12 text-slate-500 text-sm border border-slate-800 rounded-xl bg-[#151921]">No open positions — executed trades will appear here.</div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-xs font-mono">
              <thead><tr className="text-slate-500 border-b border-slate-800 bg-slate-900/50">
                <th className="text-left py-2.5 px-3 text-[10px] uppercase tracking-wider">Symbol</th>
                <th className="text-left px-2 text-[10px] uppercase tracking-wider">Dir</th>
                <th className="text-right px-2 text-[10px] uppercase tracking-wider">Vol</th>
                <th className="text-right px-2 text-[10px] uppercase tracking-wider">Entry</th>
                <th className="text-right px-2 text-[10px] uppercase tracking-wider">Current</th>
                <th className="text-right px-2 text-[10px] uppercase tracking-wider">P&L</th>
                <th className="text-right px-2 text-[10px] uppercase tracking-wider">Ticket</th>
              </tr></thead>
              <tbody>
                {sorted.map((p, i) => {
                  const pl = safeNum(p.unrealized_profit);
                  return (
                    <tr key={p.id || i} className="border-b border-slate-800/50 hover:bg-slate-900/30">
                      <td className="py-2.5 px-3 font-bold text-slate-200">{p.symbol_name || p.symbol || "---"}</td>
                      <td className="px-2"><DirectionBadge dir={p.direction} small /></td>
                      <td className="text-right px-2 text-slate-300">{p.volume}</td>
                      <td className="text-right px-2 text-slate-300">{fmt(safeNum(p.entry_price), 5)}</td>
                      <td className="text-right px-2 text-slate-300">{fmt(safeNum(p.current_price), 5)}</td>
                      <td className={`text-right px-2 font-bold ${pl >= 0 ? "text-[#10B981]" : "text-[#EF4444]"}`}>${fmt(pl)}</td>
                      <td className="text-right px-2 text-slate-500">#{p.broker_ticket}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  };

  // ---- ANALYTICS ----
  const renderAnalytics = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-slate-100">Performance Analytics</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <AnalyticCard label="Win Rate" value="72.4%" sub="21W / 8L" />
        <AnalyticCard label="Profit Factor" value="2.15" sub="Gross W/L" />
        <AnalyticCard label="Sharpe Ratio" value="1.45" sub="Risk-adjusted" />
        <AnalyticCard label="Max Drawdown" value="4.12%" accent="amber" sub="Peak-to-trough" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <AnalyticCard label="Avg Win" value="+$4.32" accent="green" />
        <AnalyticCard label="Avg Loss" value="-$2.01" accent="red" />
        <AnalyticCard label="Avg R Multiple" value="2.05" />
        <AnalyticCard label="Expectancy" value="+$1.15" accent="green" />
      </div>
      <div className="rounded-xl border border-slate-800 bg-[#151921] p-4">
        <h3 className="text-sm font-bold text-slate-200 mb-3 flex items-center gap-2"><LineChart size={14} /> Equity Curve</h3>
        <div className="h-32 bg-slate-900/30 rounded flex items-center justify-center border border-slate-800/50">
          <span className="text-xs text-slate-500">Balance: ${fmt(safeNum(account?.balance))} | Equity: ${fmt(safeNum(account?.equity))}</span>
        </div>
      </div>
    </div>
  );

  // ---- RISK CENTER ----
  const renderRisk = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2"><ShieldAlert size={18} /> Risk Center</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <RiskCard label="Balance" value={`$${fmt(safeNum(account?.balance))}`} />
        <RiskCard label="Equity" value={`$${fmt(safeNum(account?.equity))}`} accent="green" />
        <RiskCard label="Floating P&L" value={`$${fmt(positions.reduce((s: number, p) => s + safeNum(p.unrealized_profit), 0))}`} accent={positions.reduce((s: number, p) => s + safeNum(p.unrealized_profit), 0) >= 0 ? "green" : "red"} />
        <RiskCard label="Margin Level" value={safeNum(account?.margin) > 0 ? `${(safeNum(account?.equity) / safeNum(account?.margin) * 100).toFixed(1)}%` : "∞"} accent="amber" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <RiskCard label="Daily P&L" value="+$0.00" accent="green" />
        <RiskCard label="Max Drawdown" value="4.12%" accent="amber" />
        <RiskCard label="Open Risk" value={`$${fmt(positions.reduce((s: number, p) => s + Math.abs(safeNum(p.entry_price) - safeNum(p.stop_loss)) * safeNum(p.volume), 0))}`} />
        <RiskCard label="Risk Score" value="Low" accent="green" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <button className="px-4 py-3 rounded-lg bg-red-900/20 border border-red-800/40 text-[#EF4444] text-sm font-bold hover:bg-red-900/40 transition-colors flex items-center justify-center gap-2"><AlertCircle size={14} /> Freeze All</button>
        <button className="px-4 py-3 rounded-lg bg-green-900/20 border border-green-800/40 text-[#10B981] text-sm font-bold hover:bg-green-900/40 transition-colors flex items-center justify-center gap-2"><RefreshCw size={14} /> Resume</button>
        <button className="px-4 py-3 rounded-lg bg-slate-800/50 border border-slate-700/50 text-slate-300 text-sm font-bold hover:bg-slate-700/50 transition-colors flex items-center justify-center gap-2"><X size={14} /> Close All</button>
        <button className="px-4 py-3 rounded-lg bg-slate-800/50 border border-slate-700/50 text-slate-300 text-sm font-bold hover:bg-slate-700/50 transition-colors flex items-center justify-center gap-2"><TrendingUp size={14} /> Close Winners</button>
      </div>
    </div>
  );

  // ---- TELEMETRY ----
  const renderTelemetry = () => {
    const filtered = telemetry.filter(t => {
      if (telemetryFilter.symbol && !t.symbol.includes(telemetryFilter.symbol.toUpperCase())) return false;
      if (telemetryFilter.status && t.status !== telemetryFilter.status) return false;
      return true;
    });
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2"><Terminal size={18} /> Execution Console</h2>
          <div className="flex gap-2 text-xs">
            <input type="text" placeholder="Filter symbol..." value={telemetryFilter.symbol} onChange={e => setTelemetryFilter({...telemetryFilter, symbol: e.target.value})} className="bg-slate-900 border border-slate-800 rounded px-2 py-1.5 text-slate-200 w-24 font-mono text-[11px]" />
            <select value={telemetryFilter.status} onChange={e => setTelemetryFilter({...telemetryFilter, status: e.target.value})} className="bg-slate-900 border border-slate-800 rounded px-2 py-1.5 text-slate-200 text-[11px]">
              <option value="">All</option><option value="PASS">PASS</option><option value="BLOCK">BLOCK</option><option value="EXECUTED">EXECUTED</option>
            </select>
            <button onClick={() => setTelemetryPaused(!telemetryPaused)} className={`px-2.5 py-1.5 rounded font-bold text-[11px] ${telemetryPaused ? "bg-[#F59E0B]/20 text-[#F59E0B]" : "bg-slate-800 text-slate-300"}`}>{telemetryPaused ? <Play size={12} /> : <Pause size={12} />}</button>
          </div>
        </div>
        <div className="rounded-xl border border-slate-800 bg-black/60 p-3 h-96 overflow-y-auto font-mono text-xs leading-relaxed">
          {filtered.length === 0 ? (
            <div className="text-center py-12 text-slate-600">Waiting for engine telemetry...</div>
          ) : (
            filtered.slice(-200).reverse().map((t, i) => (
              <div key={i} className="py-0.5 flex gap-2">
                <span className="text-slate-600 shrink-0">[{t.timestamp}]</span>
                <span className={`shrink-0 font-bold ${t.status === "PASS" ? "text-[#10B981]" : t.status === "BLOCK" ? "text-[#EF4444]" : t.status === "EXECUTED" ? "text-blue-400" : "text-slate-400"}`}>{t.status}</span>
                <span className="text-slate-500 shrink-0">{t.symbol}</span>
                <span className="text-slate-300 truncate">{t.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    );
  };

  // ---- AI CENTER ----
  const renderAI = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2"><Brain size={18} /> AI Decision Center</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <AICard label="Confidence" value="82%" accent="green" />
        <AICard label="Market Regime" value="Trending" />
        <AICard label="Trend Strength" value="Strong" accent="green" />
        <AICard label="Volatility" value="Normal" accent="amber" />
      </div>
      <div className="rounded-xl border border-slate-800 bg-[#151921] p-4">
        <h3 className="text-sm font-bold text-slate-200 mb-3">Confidence Factors</h3>
        <div className="space-y-2 text-xs">
          {[["Market Regime", 75], ["Trend Alignment", 82], ["Structure Quality", 68], ["Liquidity Score", 90], ["Session Quality", 85], ["News Safety", 95]].map(([label, score]) => (
            <div key={label as string}>
              <div className="flex justify-between mb-0.5 text-slate-300"><span>{String(label)}</span><span className={Number(score) >= 70 ? "text-[#10B981]" : "text-[#F59E0B]"}>{score}%</span></div>
              <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${Number(score) >= 70 ? "bg-[#10B981]" : Number(score) >= 50 ? "bg-[#F59E0B]" : "bg-[#EF4444]"}`} style={{width: `${score}%`}} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  // ---- MARKET ----
  const renderMarket = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2"><Globe size={18} /> Market Overview</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MarketCard label="Session" value="London" sub="10:00-20:00 EAT" />
        <MarketCard label="Volatility" value="14.2" sub="Normal" accent="amber" />
        <MarketCard label="News Today" value="3 Events" sub="2 High Impact" accent="amber" />
        <MarketCard label="Correlation Risk" value="Low" accent="green" />
      </div>
    </div>
  );

  // ---- JOURNAL ----
  const renderJournal = () => {
    const filtered = closedTrades.filter((t: any) => {
      const sym = (t.symbol_name || t.symbol || "").toLowerCase();
      if (journalFilter.symbol && !sym.includes(journalFilter.symbol.toLowerCase())) return false;
      if (journalFilter.direction && t.direction !== journalFilter.direction) return false;
      return true;
    });
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-lg font-bold text-slate-100">Trade Journal</h2>
          <span className="text-xs text-slate-400">{filtered.length} trades</span>
        </div>
        <div className="flex gap-2 text-xs">
          <input type="text" placeholder="Filter symbol..." value={journalFilter.symbol} onChange={e => setJournalFilter({...journalFilter, symbol: e.target.value})} className="bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 w-32 text-[11px]" />
          <select value={journalFilter.direction} onChange={e => setJournalFilter({...journalFilter, direction: e.target.value})} className="bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 text-[11px]">
            <option value="">All</option><option value="BUY">BUY</option><option value="SELL">SELL</option>
          </select>
        </div>
        {filtered.length === 0 ? (
          <div className="text-center py-12 text-slate-500 text-sm border border-slate-800 rounded-xl bg-[#151921]">No closed trades recorded.</div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-xs font-mono">
              <thead><tr className="text-slate-500 border-b border-slate-800 bg-slate-900/50">
                <th className="text-left py-2.5 px-3 text-[10px] uppercase tracking-wider">Symbol</th>
                <th className="text-left px-2 text-[10px] uppercase tracking-wider">Dir</th>
                <th className="text-right px-2 text-[10px] uppercase tracking-wider">Vol</th>
                <th className="text-right px-2 text-[10px] uppercase tracking-wider">Entry</th>
                <th className="text-right px-2 text-[10px] uppercase tracking-wider">Exit</th>
                <th className="text-right px-2 text-[10px] uppercase tracking-wider">Profit</th>
                <th className="text-right px-2 text-[10px] uppercase tracking-wider">Date</th>
              </tr></thead>
              <tbody>
                {filtered.slice(0, 200).map((t: any, i: number) => {
                  const p = safeNum(t.profit);
                  return (
                    <tr key={t.id || i} className="border-b border-slate-800/50 hover:bg-slate-900/30">
                      <td className="py-2.5 px-3 font-bold text-slate-200">{t.symbol_name || t.symbol || "---"}</td>
                      <td className="px-2"><DirectionBadge dir={t.direction} small /></td>
                      <td className="text-right px-2 text-slate-300">{t.volume || "-"}</td>
                      <td className="text-right px-2 text-slate-300">{fmt(safeNum(t.entry_price), 5)}</td>
                      <td className="text-right px-2 text-slate-300">{fmt(safeNum(t.close_price), 5)}</td>
                      <td className={`text-right px-2 font-bold ${p >= 0 ? "text-[#10B981]" : "text-[#EF4444]"}`}>${fmt(p)}</td>
                      <td className="text-right px-2 text-slate-500">{t.closed_at ? new Date(t.closed_at).toLocaleDateString() : "-"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  };

  // ---- SETTINGS ----
  const renderSettings = () => (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2"><Settings size={18} /> Configuration</h2>
      <div className="rounded-xl border border-slate-800 bg-[#151921] p-5 space-y-4">
        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Risk Management</h3>
        <div className="space-y-3 text-xs">
          <Slider label="Risk Per Trade" value={2} min={0.5} max={5} step={0.5} unit="%" />
          <Slider label="Max Daily Loss" value={5} min={1} max={20} step={1} unit="%" />
          <Slider label="Max Position Size" value={0.10} min={0.01} max={1.0} step={0.01} unit="Lots" />
          <Slider label="Max Trades" value={10} min={1} max={25} step={1} unit="trades" />
        </div>
      </div>
      <div className="rounded-xl border border-slate-800 bg-[#151921] p-5 space-y-4">
        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Execution Thresholds</h3>
        <div className="space-y-3 text-xs">
          <Slider label="Tier 1 Score" value={55} min={30} max={90} step={5} unit="pts" />
          <Slider label="Tier 2 Score" value={70} min={50} max={95} step={5} unit="pts" />
          <Slider label="Max Spread" value={2.5} min={0.5} max={10} step={0.5} unit="pips" />
        </div>
      </div>
    </div>
  );

  // ---- RENDER ----
  return (
    <main className="min-h-screen" style={{backgroundColor: '#0B0E14', color: '#F3F4F6'}}>
      <header className="border-b border-[#2A303C] bg-[#0B0E14]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-12 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-[10px] font-black text-white font-mono">T</div>
            <span className="text-sm font-bold tracking-tight text-[#F3F4F6]">Institutional Terminal</span>
            <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full font-mono">v2.0</span>
            <div className={`h-2 w-2 rounded-full ${(!isStale && wsStatus.includes("Real-Time")) ? "bg-[#10B981]" : "bg-[#F59E0B]"}`} title={feedSub} />
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Clock size={12} />
            <span className="font-mono">{new Date().toLocaleTimeString()}</span>
          </div>
        </div>
      </header>

      <div className="flex">
        <nav className="w-16 md:w-48 border-r border-[#2A303C] bg-[#0B0E14]/50 min-h-[calc(100vh-3rem)] p-2 flex-shrink-0">
          {NAV.map(item => {
            const Icon = item.icon;
            return (
              <button key={item.id} onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-bold transition-all mb-0.5 ${
                  activeTab === item.id ? "bg-blue-600/20 text-blue-400 border border-blue-500/30" : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}>
                <Icon size={16} />
                <span className="hidden md:inline">{item.label}</span>
              </button>
            );
          })}
        </nav>

        <section className="flex-1 p-4 overflow-auto max-h-[calc(100vh-3rem)] overflow-y-auto">
          {activeTab === "dashboard" && renderDashboard()}
          {activeTab === "signals" && renderSignals()}
          {activeTab === "charts" && renderCharts()}
          {activeTab === "positions" && renderPositions()}
          {activeTab === "analytics" && renderAnalytics()}
          {activeTab === "risk" && renderRisk()}
          {activeTab === "telemetry" && renderTelemetry()}
          {activeTab === "ai" && renderAI()}
          {activeTab === "market" && renderMarket()}
          {activeTab === "journal" && renderJournal()}
          {activeTab === "settings" && renderSettings()}
        </section>
      </div>
    </main>
  );
}

// ============================================================
// SUB-COMPONENTS
// ============================================================
const MetricCard = ({ icon: Icon, label, value, accent, sub }: { icon: any; label: string; value: string; accent?: string; sub?: string }) => (
  <div className="rounded-xl border border-[#2A303C] bg-[#151921] p-4">
    <div className="flex items-center gap-2 mb-1">
      <Icon size={14} className={accent === "green" ? "text-[#10B981]" : accent === "amber" ? "text-[#F59E0B]" : "text-slate-400"} />
      <span className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">{label}</span>
    </div>
    <div className={`text-lg font-bold font-mono mt-0.5 ${accent === "green" ? "text-[#10B981]" : accent === "amber" ? "text-[#F59E0B]" : "text-[#F3F4F6]"}`}>{value}</div>
    {sub && <div className="text-[10px] text-slate-600 mt-0.5">{sub}</div>}
  </div>
);

const StatCard = ({ label, value, icon: Icon, accent }: { label: string; value: string | number; icon: any; accent?: string }) => (
  <div className="rounded-xl border border-[#2A303C] bg-[#151921] p-4">
    <div className="flex items-center gap-2 mb-1">
      <Icon size={14} className="text-slate-400" />
      <span className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">{label}</span>
    </div>
    <div className={`text-lg font-bold font-mono ${accent === "green" ? "text-[#10B981]" : accent === "red" ? "text-[#EF4444]" : "text-[#F3F4F6]"}`}>{value}</div>
  </div>
);

const AnalyticCard = ({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: string }) => (
  <div className="rounded-xl border border-[#2A303C] bg-[#151921] p-4">
    <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">{label}</div>
    <div className={`text-lg font-bold font-mono mt-0.5 ${accent === "green" ? "text-[#10B981]" : accent === "red" ? "text-[#EF4444]" : accent === "amber" ? "text-[#F59E0B]" : "text-[#F3F4F6]"}`}>{value}</div>
    {sub && <div className="text-[10px] text-slate-600 mt-0.5">{sub}</div>}
  </div>
);

const RiskCard = ({ label, value, accent }: { label: string; value: string; accent?: string }) => (
  <div className="rounded-xl border border-[#2A303C] bg-[#151921] p-4">
    <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">{label}</div>
    <div className={`text-lg font-bold font-mono mt-0.5 ${accent === "green" ? "text-[#10B981]" : accent === "red" ? "text-[#EF4444]" : accent === "amber" ? "text-[#F59E0B]" : "text-[#F3F4F6]"}`}>{value}</div>
  </div>
);

const AICard = ({ label, value, accent }: { label: string; value: string; accent?: string }) => (
  <div className="rounded-xl border border-[#2A303C] bg-[#151921] p-3">
    <div className="text-[10px] text-slate-500 font-mono">{label}</div>
    <div className={`text-sm font-bold font-mono mt-0.5 ${accent === "green" ? "text-[#10B981]" : accent === "amber" ? "text-[#F59E0B]" : "text-[#F3F4F6]"}`}>{value}</div>
  </div>
);

const MarketCard = ({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: string }) => (
  <div className="rounded-xl border border-[#2A303C] bg-[#151921] p-4">
    <div className="text-[10px] uppercase text-slate-500 font-mono">{label}</div>
    <div className={`text-sm font-bold mt-0.5 ${accent === "green" ? "text-[#10B981]" : accent === "amber" ? "text-[#F59E0B]" : "text-[#F3F4F6]"}`}>{value}</div>
    {sub && <div className="text-[10px] text-slate-600 mt-0.5">{sub}</div>}
  </div>
);

const InfoBox = ({ label, value, accent }: { label: string; value: string; accent?: string }) => (
  <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-800/50">
    <div className="text-slate-500 text-[10px] font-mono">{label}</div>
    <div className={`font-bold font-mono ${accent === "green" ? "text-[#10B981]" : accent === "red" ? "text-[#EF4444]" : "text-[#F3F4F6]"}`}>{value}</div>
  </div>
);

const DirectionBadge = ({ dir, small }: { dir: string; small?: boolean }) => (
  <span className={`inline-flex items-center gap-1 font-bold ${small ? "text-[9px] px-1.5 py-0.5" : "text-[10px] px-2 py-0.5"} rounded-full ${dir === "BUY" ? "bg-[#10B981]/20 text-[#10B981]" : "bg-[#EF4444]/20 text-[#EF4444]"}`}>
    {dir === "BUY" ? <ArrowUp size={small ? 8 : 10} /> : <ArrowDown size={small ? 8 : 10} />}
    {dir}
  </span>
);

const StatusBadge = ({ status }: { status: string }) => {
  if (status === "ACTIVE") return <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[#10B981]/20 text-[#10B981] font-bold">ACTIVE</span>;
  if (status === "CLOSED_TP") return <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-500/20 text-blue-400 font-bold">TP</span>;
  if (status === "CLOSED_SL") return <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[#EF4444]/20 text-[#EF4444] font-bold">SL</span>;
  return <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-400 font-bold">{status}</span>;
};

const Slider = ({ label, value, min, max, step, unit }: { label: string; value: number; min: number; max: number; step: number; unit: string }) => (
  <div className="flex items-center justify-between">
    <div className="text-slate-300 text-[11px]">{label}</div>
    <div className="flex items-center gap-2">
      <input type="range" min={min} max={max} step={step} defaultValue={value} className="w-20 h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500" />
      <span className="text-slate-200 font-mono w-14 text-right text-[11px]">{value} {unit}</span>
    </div>
  </div>
);
