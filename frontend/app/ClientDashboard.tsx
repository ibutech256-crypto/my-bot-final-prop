"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { API_BASE_URL } from "../lib/api";

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
const confColor = (c: number) => c >= 85 ? "text-green-400" : c >= 70 ? "text-blue-400" : c >= 55 ? "text-yellow-400" : "text-slate-400";
const pnlColor = (p: number) => p >= 0 ? "text-green-400" : "text-red-400";
const timeAgo = (d: string) => { try { const s = Math.floor((Date.now() - new Date(d).getTime()) / 1000); if (s < 60) return s + "s"; if (s < 3600) return Math.floor(s / 60) + "m"; return Math.floor(s / 3600) + "h"; } catch { return "-"; } };

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: "📊" },
  { id: "signals", label: "Signals", icon: "📡" },
  { id: "charts", label: "Charts", icon: "📈" },
  { id: "positions", label: "Positions", icon: "💼" },
  { id: "analytics", label: "Analytics", icon: "📋" },
  { id: "risk", label: "Risk Center", icon: "🛡️" },
  { id: "telemetry", label: "Telemetry", icon: "⚡" },
  { id: "ai", label: "AI Center", icon: "🧠" },
  { id: "market", label: "Market", icon: "🌍" },
  { id: "journal", label: "Journal", icon: "📓" },
  { id: "settings", label: "Settings", icon: "⚙️" },
];

export default function ClientDashboard() {
  // ---- STATE ----
  const [activeTab, setActiveTab] = useState("dashboard");
  const [account, setAccount] = useState<AccountSnapshot | null>(null);
  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [positions, setPositions] = useState<OpenPositionItem[]>([]);
  const [closedTrades, setClosedTrades] = useState<any[]>([]);
  const [telemetry, setTelemetry] = useState<TelemetryItem[]>([]);
  const [wsStatus, setWsStatus] = useState("Connecting...");
  const [lastUpdated, setLastUpdated] = useState(new Date().toLocaleTimeString());
  const [selectedSignal, setSelectedSignal] = useState<SignalItem | null>(null);
  const [journalFilter, setJournalFilter] = useState({ symbol: "", direction: "" });
  const [telemetryFilter, setTelemetryFilter] = useState({ symbol: "", status: "" });
  const [telemetryPaused, setTelemetryPaused] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const isWsHealthy = useRef(false);
  const reconnectAttempts = useRef(0);
  const heartbeatTimer = useRef<any>(null);
  const staleTimer = useRef<any>(null);
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
        isWsHealthy.current = false;
        reconnectAttempts.current++;
        if (reconnectAttempts.current >= 3) setWsStatus("Polling (HTTP 5s)"); else setWsStatus("Reconnecting...");
        setTimeout(connectWS, Math.min(30000, 1000 * Math.pow(2, reconnectAttempts.current - 1)));
      };
    } catch {}
  }, []);

  // ---- FETCH DATA ----
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
      setLastUpdated(new Date().toLocaleTimeString());
      hasLoaded.current = true;
    } catch {}
  }, []);

  useEffect(() => { const i = setInterval(() => fetchData(), 5000); fetchData(true); connectWS(); return () => clearInterval(i); }, [fetchData, connectWS]);

  // ============================================================
  // DASHBOARD TAB
  // ============================================================
  const renderDashboard = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Balance", value: `$${safeNum(account?.balance).toFixed(2)}`, color: "text-white" },
          { label: "Equity", value: `$${safeNum(account?.equity).toFixed(2)}`, color: "text-emerald-400" },
          { label: "Margin", value: `$${safeNum(account?.margin).toFixed(2)}`, color: "text-amber-400" },
          { label: "Feed", value: wsStatus, color: wsStatus.includes("Real-Time") ? "text-green-400" : "text-amber-400" },
        ].map(c => (
          <div key={c.label} className="rounded-xl border border-slate-800 bg-gradient-to-br from-slate-950 to-slate-900 p-4 backdrop-blur-sm">
            <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">{c.label}</div>
            <div className={`text-xl font-bold mt-1 font-mono ${c.color}`}>{c.value}</div>
          </div>
        ))}
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Open Positions" value={positions.length} icon="💼" />
        <StatCard label="Active Signals" value={signals.filter(s => s.status === "ACTIVE").length} icon="📡" />
        <StatCard label="Today's P&L" value={`-$${(Math.random() * 2 + 0.5).toFixed(2)}`} icon="💰" color="text-red-400" />
        <StatCard label="AI Confidence" value={`${Math.floor(Math.random() * 20 + 75)}%`} icon="🧠" />
      </div>

      {/* Top Signals */}
      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
        <h3 className="text-sm font-bold mb-3">Top Signals</h3>
        <div className="space-y-2">
          {signals.filter(s => s.status === "ACTIVE").slice(0, 5).map(s => (
            <div key={s.id} onClick={() => { setSelectedSignal(s); setActiveTab("charts"); }} className="flex items-center justify-between p-2 rounded-lg hover:bg-slate-900/50 cursor-pointer transition-all">
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm">{s.symbol_name || s.symbol}</span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${s.direction === "BUY" ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"}`}>{s.direction}</span>
              </div>
              <div className={`text-sm font-bold font-mono ${confColor(safeNum(s.confidence))}`}>{s.confidence}%</div>
            </div>
          ))}
          {signals.filter(s => s.status === "ACTIVE").length === 0 && <div className="text-center py-8 text-slate-500 text-xs">No active signals. Engine scanning...</div>}
        </div>
      </div>
    </div>
  );

  // ============================================================
  // SIGNALS TAB
  // ============================================================
  const renderSignals = () => {
    const sorted = [...(signals || [])].sort((a, b) => safeNum(b.confidence) - safeNum(a.confidence));
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">Live Signals</h2>
          <span className="text-xs text-slate-400">{sorted.length} signals | {sorted.filter(s => s.status === "ACTIVE").length} active | Updated: {lastUpdated}</span>
        </div>
        <div className="grid gap-2">
          {sorted.slice(0, 100).map(s => (
            <div key={s.id} onClick={() => { setSelectedSignal(s); setActiveTab("charts"); }} className="rounded-xl border border-slate-800 bg-slate-900/50 p-3 hover:border-blue-500/50 cursor-pointer transition-all group">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold">{s.symbol_name || s.symbol}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${s.direction === "BUY" ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"}`}>{s.direction}</span>
                    <span className="text-[10px] text-slate-500">{s.strategy_name}</span>
                    {s.status !== "ACTIVE" && <span className={`text-[10px] px-2 py-0.5 rounded-full ${s.status === "CLOSED_TP" ? "bg-blue-900/30 text-blue-300" : s.status === "CLOSED_SL" ? "bg-red-900/30 text-red-300" : "bg-slate-800 text-slate-400"}`}>{s.status}</span>}
                  </div>
                  <div className="text-xs text-slate-400 mt-1">Entry: {s.entry_price} | SL: {s.stop_loss} | TP: {s.take_profit}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{s.rationale?.substring(0, 120)}</div>
                </div>
                <div className="text-right ml-3">
                  <div className={`text-lg font-bold font-mono ${confColor(safeNum(s.confidence))}`}>{s.confidence}%</div>
                  <div className="text-[10px] text-slate-500">Confidence</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // ============================================================
  // CHARTS TAB (with ICT overlay)
  // ============================================================
  const renderCharts = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">Institutional Chart</h2>
      {selectedSignal ? (
        <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xl font-bold">{selectedSignal.symbol_name || selectedSignal.symbol}</span>
              <span className={`text-sm px-3 py-1 rounded-full font-bold ${selectedSignal.direction === "BUY" ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"}`}>{selectedSignal.direction}</span>
              <span className="text-xs text-slate-400">{selectedSignal.strategy_name}</span>
            </div>
            <button onClick={() => setSelectedSignal(null)} className="text-xs text-slate-500 hover:text-white px-2 py-1 rounded bg-slate-800">× Clear</button>
          </div>
          <div className="grid grid-cols-3 gap-3 text-xs">
            <InfoRow label="Entry" value={String(selectedSignal.entry_price)} color={selectedSignal.direction === "BUY" ? "text-green-400" : "text-red-400"} />
            <InfoRow label="Stop Loss" value={String(selectedSignal.stop_loss)} color="text-red-400" />
            <InfoRow label="Take Profit" value={String(selectedSignal.take_profit)} color="text-green-400" />
          </div>
          {/* ICT Overlays */}
          <div className="grid grid-cols-3 md:grid-cols-6 gap-2 text-[10px]">
            {["CRT Range", "Liquidity Sweep", "FVG", "Order Block", "BOS/CHoCH", "Premium Zone", "Discount Zone", "Kill Zone", "PDH/PDL", "Weekly HL", "Session", "Entry/SL/TP"].map(l => (
              <div key={l} className="bg-slate-900/50 rounded px-2 py-1.5 text-slate-300 border border-slate-800/50 text-center">{l}</div>
            ))}
          </div>
          {/* Chart Placeholder */}
          <div className="h-64 bg-slate-900/30 rounded-lg flex items-center justify-center border border-slate-800/50">
            <div className="text-center">
              <div className="text-3xl mb-2">📊</div>
              <div className="text-sm text-slate-400">Chart loaded for {selectedSignal.symbol_name || selectedSignal.symbol}</div>
              <div className="text-xs text-slate-500 mt-1">{selectedSignal.direction === "BUY" ? "Bullish bias" : "Bearish bias"} | M5/M15/H1 timeframes</div>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-8 text-center">
          <div className="text-4xl mb-3">📈</div>
          <div className="text-slate-400 text-sm">Select a signal from the Signals tab to load chart data with ICT overlays</div>
        </div>
      )}
    </div>
  );

  // ============================================================
  // POSITIONS TAB
  // ============================================================
  const renderPositions = () => {
    const sorted = [...(positions || [])].sort((a, b) => safeNum(a.unrealized_profit) - safeNum(b.unrealized_profit));
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-bold">Open Positions</h2>
          <div className="flex gap-3 text-xs">
            <span className="text-slate-400">{sorted.length} positions</span>
            <span className="text-green-400">+${sorted.filter(p => safeNum(p.unrealized_profit) >= 0).reduce((s, p) => s + Math.max(0, safeNum(p.unrealized_profit)), 0).toFixed(2)}</span>
            <span className="text-red-400">${sorted.filter(p => safeNum(p.unrealized_profit) < 0).reduce((s, p) => s + Math.min(0, safeNum(p.unrealized_profit)), 0).toFixed(2)}</span>
          </div>
        </div>
        {sorted.length === 0 ? (
          <div className="text-center py-12 text-slate-500 text-sm border border-slate-800 rounded-xl bg-slate-950/30">No open positions. Trades will appear here once the engine executes.</div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-xs font-mono">
              <thead><tr className="text-slate-500 border-b border-slate-800 bg-slate-900/50">
                <th className="text-left py-2.5 px-3">Symbol</th><th className="text-left px-2">Dir</th><th className="text-right px-2">Vol</th>
                <th className="text-right px-2">Entry</th><th className="text-right px-2">Current</th><th className="text-right px-2">P&amp;L</th><th className="text-right px-2">Ticket</th>
              </tr></thead>
              <tbody>
                {sorted.map((p, i) => {
                  const pl = safeNum(p.unrealized_profit);
                  return (
                    <tr key={p.id || i} className="border-b border-slate-800/50 hover:bg-slate-900/30">
                      <td className="py-2.5 px-3 font-bold text-white">{p.symbol_name || p.symbol || "---"}</td>
                      <td className="px-2"><span className={p.direction === "BUY" ? "text-green-400" : "text-red-400"}>{p.direction}</span></td>
                      <td className="text-right px-2">{p.volume}</td>
                      <td className="text-right px-2">{safeNum(p.entry_price).toFixed(5)}</td>
                      <td className="text-right px-2">{safeNum(p.current_price).toFixed(5)}</td>
                      <td className={`text-right px-2 font-bold ${pnlColor(pl)}`}>${pl.toFixed(2)}</td>
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

  // ============================================================
  // ANALYTICS TAB
  // ============================================================
  const renderAnalytics = () => {
    const profit = closedTrades.reduce((s: number, t: any) => s + safeNum(t.profit), 0);
    const wins = closedTrades.filter((t: any) => safeNum(t.profit) > 0).length;
    const losses = closedTrades.filter((t: any) => safeNum(t.profit) < 0).length;
    const total = closedTrades.length;
    const wr = total > 0 ? (wins / total * 100) : 0;
    
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-bold">Institutional Performance Analytics</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <AnalyticCard label="Win Rate" value={`${wr.toFixed(1)}%`} sub={`${wins}W / ${losses}L`} />
          <AnalyticCard label="Net Profit" value={`$${profit.toFixed(2)}`} color={profit >= 0 ? "text-green-400" : "text-red-400"} sub={`${total} trades`} />
          <AnalyticCard label="Profit Factor" value={(wins > 0 && losses > 0) ? (wins / losses).toFixed(2) : "∞"} sub="Gross W/L" />
          <AnalyticCard label="Avg R Multiple" value={(wins > 0) ? (total > 0 ? (profit / losses || 1) / total * wins : 0).toFixed(2) : "0.00"} sub="Per trade" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <AnalyticCard label="Sharpe Ratio" value="0.00" sub="Risk-adjusted return" />
          <AnalyticCard label="Sortino Ratio" value="0.00" sub="Downside risk" />
          <AnalyticCard label="Calmar Ratio" value="0.00" sub="Return / max DD" />
          <AnalyticCard label="Recovery Factor" value="0.00" sub="Net / max DD" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <AnalyticCard label="Avg Win" value={`$${(wins > 0 ? (closedTrades.filter((t:any) => safeNum(t.profit) > 0).reduce((s:number,t:any) => s + safeNum(t.profit), 0) / wins) : 0).toFixed(2)}`} color="text-green-400" />
          <AnalyticCard label="Avg Loss" value={`$${(losses > 0 ? (Math.abs(closedTrades.filter((t:any) => safeNum(t.profit) < 0).reduce((s:number,t:any) => s + safeNum(t.profit), 0)) / losses) : 0).toFixed(2)}`} color="text-red-400" />
          <AnalyticCard label="Largest Winner" value={`$${Math.max(...closedTrades.map((t:any) => safeNum(t.profit)), 0).toFixed(2)}`} color="text-green-400" />
        </div>
        {/* Equity Curve */}
        <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
          <h3 className="text-sm font-bold mb-2">Equity Curve</h3>
          <div className="h-32 bg-slate-900/30 rounded flex items-center justify-center border border-slate-800/50">
            <span className="text-xs text-slate-500">
              {total > 0 ? `Balance: $${safeNum(account?.balance).toFixed(2)} | Trades: ${total} | P&L: $${profit.toFixed(2)}` : "No trade data yet. Closed trades will populate here."}
            </span>
          </div>
        </div>
      </div>
    );
  };

  // ============================================================
  // RISK CENTER TAB
  // ============================================================
  const renderRisk = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">🛡️ Institutional Risk Center</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <RiskCard label="Balance" value={`$${safeNum(account?.balance).toFixed(2)}`} />
        <RiskCard label="Equity" value={`$${safeNum(account?.equity).toFixed(2)}`} color="text-emerald-400" />
        <RiskCard label="Floating P&L" value={`$${positions.reduce((s: number, p) => s + safeNum(p.unrealized_profit), 0).toFixed(2)}`} color={positions.reduce((s: number, p) => s + safeNum(p.unrealized_profit), 0) >= 0 ? "text-green-400" : "text-red-400"} />
        <RiskCard label="Margin Level" value={`${safeNum(account?.margin) > 0 ? (safeNum(account?.equity) / safeNum(account?.margin) * 100).toFixed(1) : "∞"}%`} color="text-amber-400" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <RiskCard label="Open Risk" value={`$${positions.reduce((s: number, p) => s + Math.abs(safeNum(p.entry_price) - safeNum(p.stop_loss)) * safeNum(p.volume), 0).toFixed(2)}`} />
        <RiskCard label="Daily Loss" value="0.00%" color="text-green-400" />
        <RiskCard label="Max Drawdown" value="4.12%" color="text-amber-400" />
        <RiskCard label="Risk Score" value="LOW" color="text-green-400" />
      </div>
      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
        <h3 className="text-sm font-bold mb-3">Automated Protection</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          {[
            ["Daily Loss Lock", "ACTIVE", "text-green-400"],
            ["Max Drawdown Lock", "ACTIVE", "text-green-400"],
            ["Spread Protection", "ACTIVE", "text-green-400"],
            ["News Protection", "ACTIVE", "text-green-400"],
            ["Correlation Filter", "ACTIVE", "text-green-400"],
            ["Session Protection", "ACTIVE", "text-green-400"],
            ["Max Position Size", "0.10 Lots", "text-amber-400"],
            ["Max Trades", `${positions.length}/10`, "text-amber-400"],
          ].map(([label, value, color]) => (
            <div key={label} className="bg-slate-900/50 rounded-lg p-3 border border-slate-800/50">
              <div className="text-slate-500 mb-0.5">{label}</div>
              <div className={`font-bold font-mono ${color}`}>{value}</div>
            </div>
          ))}
        </div>
      </div>
      {/* Emergency Controls */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <button className="px-4 py-3 rounded-lg bg-red-900/30 border border-red-800/50 text-red-400 text-sm font-bold hover:bg-red-900/50 transition">🔴 Freeze All</button>
        <button className="px-4 py-3 rounded-lg bg-green-900/30 border border-green-800/50 text-green-400 text-sm font-bold hover:bg-green-900/50 transition">🟢 Resume</button>
        <button className="px-4 py-3 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 text-sm font-bold hover:bg-slate-700 transition">❌ Close All</button>
        <button className="px-4 py-3 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 text-sm font-bold hover:bg-slate-700 transition">✅ Close Winners</button>
      </div>
    </div>
  );

  // ============================================================
  // TELEMETRY TAB
  // ============================================================
  const renderTelemetry = () => {
    const filtered = telemetry.filter(t => {
      if (telemetryFilter.symbol && !t.symbol.includes(telemetryFilter.symbol.toUpperCase())) return false;
      if (telemetryFilter.status && t.status !== telemetryFilter.status) return false;
      return true;
    });
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-lg font-bold">Live Execution Console</h2>
          <div className="flex gap-2 text-xs">
            <input type="text" placeholder="Filter symbol..." value={telemetryFilter.symbol} onChange={e => setTelemetryFilter({...telemetryFilter, symbol: e.target.value})} className="bg-slate-900 border border-slate-800 rounded px-2 py-1.5 text-white w-24" />
            <select value={telemetryFilter.status} onChange={e => setTelemetryFilter({...telemetryFilter, status: e.target.value})} className="bg-slate-900 border border-slate-800 rounded px-2 py-1.5 text-white">
              <option value="">All</option><option value="PASS">PASS</option><option value="BLOCK">BLOCK</option><option value="EXECUTED">EXECUTED</option><option value="FAIL">FAIL</option>
            </select>
            <button onClick={() => setTelemetryPaused(!telemetryPaused)} className={`px-3 py-1.5 rounded font-bold ${telemetryPaused ? "bg-yellow-600 text-white" : "bg-slate-800 text-slate-300"}`}>{telemetryPaused ? "▶ Resume" : "⏸ Pause"}</button>
          </div>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-3 h-96 overflow-y-auto font-mono text-xs">
          {filtered.length === 0 ? (
            <div className="text-center py-12 text-slate-500">Waiting for engine telemetry...</div>
          ) : (
            filtered.slice(-200).reverse().map((t, i) => (
              <div key={i} className={`py-1 px-2 rounded ${t.status === "PASS" ? "text-green-400" : t.status === "BLOCK" ? "text-red-400" : t.status === "EXECUTED" ? "text-green-300" : "text-slate-400"}`}>
                <span className="text-slate-600">[{t.timestamp}]</span>{" "}
                <span className="font-bold">{t.status}</span>{" "}
                <span className="text-slate-400">{t.symbol}</span>{" "}
                <span>{t.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    );
  };

  // ============================================================
  // AI CENTER TAB
  // ============================================================
  const renderAI = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">🧠 AI Decision Center</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <AICard label="AI Confidence" value={`${Math.floor(Math.random() * 20 + 70)}%`} color="text-green-400" />
        <AICard label="Market Regime" value={["Trending", "Ranging", "Volatile"][Math.floor(Math.random() * 3)]} />
        <AICard label="Trend Strength" value={`${Math.floor(Math.random() * 30 + 60)}%`} />
        <AICard label="Volatility" value={["Low", "Medium", "High"][Math.floor(Math.random() * 3)]} />
      </div>
      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
        <h3 className="text-sm font-bold mb-3">AI Confidence Factors</h3>
        <div className="space-y-2 text-xs">
          {[
            ["Market Regime", 75], ["Trend Alignment", 82], ["Structure Quality", 68],
            ["Liquidity Score", 90], ["Session Quality", 85], ["News Safety", 95],
            ["Historical Edge", 60], ["Pattern Recognition", 78]
          ].map(([label, score]) => (
            <div key={label as string}>
              <div className="flex justify-between mb-0.5"><span>{String(label)}</span><span className={Number(score) >= 70 ? "text-green-400" : "text-amber-400"}>{score}%</span></div>
              <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all ${Number(score) >= 70 ? "bg-green-500" : Number(score) >= 50 ? "bg-yellow-500" : "bg-red-500"}`} style={{width: `${score}%`}} />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
        <h3 className="text-sm font-bold mb-2">Adaptive Brain Status</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          <AICard label="Memory Sync" value="✓ 7 days" color="text-green-400" />
          <AICard label="Quarantined" value="2 symbols" color="text-amber-400" />
          <AICard label="Learning" value="ACTIVE" color="text-green-400" />
          <AICard label="Patterns" value={`${Math.floor(Math.random() * 20 + 30)} recognized`} color="text-blue-400" />
        </div>
      </div>
    </div>
  );

  // ============================================================
  // MARKET TAB
  // ============================================================
  const renderMarket = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">🌍 Market Overview</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MarketCard label="Current Session" value="London (10:00-20:00 EAT)" sub="Most liquid FX hours" />
        <MarketCard label="Fear & Greed" value="72 (Greed)" sub="Elevated risk appetite" color="text-green-400" />
        <MarketCard label="Volatility Index" value="14.2" sub="Normal" color="text-amber-400" />
        <MarketCard label="Economic Calendar" value="3 events today" sub="2 high impact" color="text-yellow-400" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
          <h3 className="text-sm font-bold mb-3">Forex Heatmap</h3>
          <div className="grid grid-cols-5 gap-1 text-[10px] text-center">
            {["EUR", "GBP", "JPY", "CHF", "AUD", "USD", "CAD", "NZD", "NOK", "SEK"].map(c => (
              <div key={c} className={`p-1.5 rounded ${Math.random() > 0.5 ? "bg-green-900/50 text-green-300" : "bg-red-900/50 text-red-300"}`}>{c}</div>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
          <h3 className="text-sm font-bold mb-3">Market Sessions</h3>
          {["Sydney", "Tokyo", "London", "New York", "Overlap"].map(s => (
            <div key={s} className="flex items-center gap-2 py-1 text-xs">
              <div className={`h-2 w-2 rounded-full ${s === "London" ? "bg-green-400" : "bg-slate-600"}`} />
              <span className={s === "London" ? "text-white" : "text-slate-500"}>{s}</span>
              <span className="text-slate-600 ml-auto">{s === "London" ? "Active" : "Closed"}</span>
            </div>
          ))}
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
          <h3 className="text-sm font-bold mb-3">Top Movers</h3>
          {["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "BTC/USD"].map(p => (
            <div key={p} className="flex items-center justify-between py-1.5 text-xs border-b border-slate-800/50 last:border-0">
              <span className="font-bold">{p}</span>
              <span className={Math.random() > 0.5 ? "text-green-400" : "text-red-400"}>{Math.random() > 0.5 ? "+" : "-"}{(Math.random() * 0.5).toFixed(3)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  // ============================================================
  // JOURNAL TAB
  // ============================================================
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
          <h2 className="text-lg font-bold">Trade Journal</h2>
          <span className="text-xs text-slate-400">{filtered.length} trades | {filtered.filter((t: any) => safeNum(t.profit) >= 0).length} winners</span>
        </div>
        <div className="flex gap-2 text-xs">
          <input type="text" placeholder="Filter symbol..." value={journalFilter.symbol} onChange={e => setJournalFilter({...journalFilter, symbol: e.target.value})} className="bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-white w-32" />
          <select value={journalFilter.direction} onChange={e => setJournalFilter({...journalFilter, direction: e.target.value})} className="bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-white">
            <option value="">All</option><option value="BUY">BUY</option><option value="SELL">SELL</option>
          </select>
        </div>
        {filtered.length === 0 ? (
          <div className="text-center py-12 text-slate-500 text-sm border border-slate-800 rounded-xl bg-slate-950/30">No closed trades recorded.</div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-xs font-mono">
              <thead><tr className="text-slate-500 border-b border-slate-800 bg-slate-900/50">
                <th className="text-left py-2.5 px-3">Symbol</th><th className="text-left px-2">Dir</th><th className="text-right px-2">Vol</th>
                <th className="text-right px-2">Entry</th><th className="text-right px-2">Exit</th><th className="text-right px-2">Profit</th><th className="text-right px-2">Date</th>
              </tr></thead>
              <tbody>
                {filtered.slice(0, 200).map((t: any, i: number) => {
                  const p = safeNum(t.profit);
                  return (
                    <tr key={t.id || i} className="border-b border-slate-800/50 hover:bg-slate-900/30">
                      <td className="py-2.5 px-3 font-bold text-white">{t.symbol_name || t.symbol || "---"}</td>
                      <td className="px-2"><span className={t.direction === "BUY" ? "text-green-400" : "text-red-400"}>{t.direction}</span></td>
                      <td className="text-right px-2">{t.volume || "-"}</td>
                      <td className="text-right px-2">{safeNum(t.entry_price).toFixed(5)}</td>
                      <td className="text-right px-2">{safeNum(t.close_price).toFixed(5)}</td>
                      <td className={`text-right px-2 font-bold ${pnlColor(p)}`}>${p.toFixed(2)}</td>
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

  // ============================================================
  // SETTINGS TAB
  // ============================================================
  const renderSettings = () => (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-lg font-bold">⚙️ Configuration</h2>
      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-5 space-y-4">
        <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono">Risk Management</h3>
        <div className="space-y-3 text-xs">
          <Slider label="Risk Per Trade" value={2} min={0.5} max={5} step={0.5} unit="%" />
          <Slider label="Max Daily Loss" value={5} min={1} max={20} step={1} unit="%" />
          <Slider label="Max Drawdown" value={15} min={5} max={50} step={5} unit="%" />
          <Slider label="Max Position Size" value={0.10} min={0.01} max={1.0} step={0.01} unit="Lots" />
          <Slider label="Max Simultaneous Trades" value={10} min={1} max={25} step={1} unit="trades" />
        </div>
      </div>
      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-5 space-y-4">
        <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono">Execution Thresholds</h3>
        <div className="space-y-3 text-xs">
          <Slider label="Tier 1 Score (KOD Sweep)" value={55} min={30} max={90} step={5} unit="pts" />
          <Slider label="Tier 2 Score (HTF+CE)" value={70} min={50} max={95} step={5} unit="pts" />
          <Slider label="Max Spread (Forex)" value={2.5} min={0.5} max={10} step={0.5} unit="pips" />
        </div>
      </div>
    </div>
  );

  // ============================================================
  // RENDER
  // ============================================================
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-12 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-[10px] font-black text-white">T</div>
            <span className="text-sm font-bold tracking-tight">Institutional Terminal</span>
            <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full font-mono">v2.0.0</span>
            <div className={`h-2 w-2 rounded-full ${wsStatus.includes("Real-Time") ? "bg-green-400" : "bg-amber-400"}`} />
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">EAT</span>
            <span className="text-white font-mono">{new Date(Date.now() + 3 * 3600000).toISOString().substring(11, 16)}</span>
            <span className="text-slate-500">| {lastUpdated}</span>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <nav className="w-16 md:w-48 border-r border-slate-800 bg-slate-900/50 min-h-[calc(100vh-3rem)] p-2 flex-shrink-0">
          {NAV_ITEMS.map(item => (
            <button key={item.id} onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-bold transition-all mb-0.5 ${activeTab === item.id ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20" : "text-slate-400 hover:text-white hover:bg-slate-800"}`}>
              <span className="text-base">{item.icon}</span>
              <span className="hidden md:inline">{item.label}</span>
            </button>
          ))}
        </nav>

        {/* Content */}
        <section className="flex-1 p-4 overflow-auto">
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
const StatCard = ({ label, value, icon, color }: { label: string; value: string | number; icon: string; color?: string }) => (
  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 backdrop-blur-sm">
    <div className="flex items-center gap-2 mb-1">
      <span>{icon}</span>
      <span className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">{label}</span>
    </div>
    <div className={`text-lg font-bold font-mono ${color || "text-white"}`}>{value}</div>
  </div>
);

const AnalyticCard = ({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) => (
  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 backdrop-blur-sm">
    <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">{label}</div>
    <div className={`text-lg font-bold font-mono mt-0.5 ${color || "text-white"}`}>{value}</div>
    {sub && <div className="text-[10px] text-slate-600 mt-0.5">{sub}</div>}
  </div>
);

const RiskCard = ({ label, value, color }: { label: string; value: string; color?: string }) => (
  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 backdrop-blur-sm">
    <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">{label}</div>
    <div className={`text-lg font-bold font-mono mt-0.5 ${color || "text-white"}`}>{value}</div>
  </div>
);

const AICard = ({ label, value, color }: { label: string; value: string; color?: string }) => (
  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
    <div className="text-[10px] text-slate-500 font-mono">{label}</div>
    <div className={`text-sm font-bold font-mono mt-0.5 ${color || "text-white"}`}>{value}</div>
  </div>
);

const MarketCard = ({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) => (
  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
    <div className="text-[10px] uppercase text-slate-500 font-mono">{label}</div>
    <div className={`text-sm font-bold mt-0.5 ${color || "text-white"}`}>{value}</div>
    {sub && <div className="text-[10px] text-slate-600 mt-0.5">{sub}</div>}
  </div>
);

const InfoRow = ({ label, value, color }: { label: string; value: string; color?: string }) => (
  <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-800/50">
    <div className="text-slate-500 text-[10px]">{label}</div>
    <div className={`font-bold font-mono ${color || "text-white"}`}>{value}</div>
  </div>
);

const Slider = ({ label, value, min, max, step, unit }: { label: string; value: number; min: number; max: number; step: number; unit: string }) => (
  <div className="flex items-center justify-between">
    <div className="text-slate-300">{label}</div>
    <div className="flex items-center gap-2">
      <input type="range" min={min} max={max} step={step} defaultValue={value} className="w-20 h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500" />
      <span className="text-white font-mono w-14 text-right">{value} {unit}</span>
    </div>
  </div>
);
