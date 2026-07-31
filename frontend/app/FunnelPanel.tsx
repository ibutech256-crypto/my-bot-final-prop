// Signal-lifecycle funnel dashboard (Phase 4).
//
// Answers, without reading the engine log: how many setups were scanned, where
// they dropped out, why every watchlist signal is still on the watchlist, and
// how that differs between the London and New York sessions.
//
// Data sources, in order of preference:
//   1. the FUNNEL_UPDATE websocket event pushed by run_mt5_engine (live), and
//   2. GET /api/v1/funnel/ + /funnel/watchlist/ + /strategy-config/ (first
//      paint, and a 15s poll so the panel still fills in if the socket is down).
"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Filter, AlertTriangle, Layers, Gauge, Clock, Activity,
  ShieldCheck, ShieldAlert, RefreshCw, Eye,
} from "lucide-react";

// ============================================================
// TYPES
// ============================================================
interface FunnelRow { stage: string; count: number; pct_of_scanned: number; pct_of_previous: number; }
interface ReasonRow { code: string; count: number; text: string; }
interface StatBlock { count: number; min: number; avg: number; median: number; p95: number; max: number; }
interface SubcheckRow { passed: number; evaluated: number; pct: number; }
interface SessionBlock {
  funnel: FunnelRow[];
  outcomes: Record<string, number>;
  rejection_reasons: ReasonRow[];
  score: StatBlock;
  spread_pips: StatBlock;
  order_latency_ms: StatBlock;
  htf_distribution: Record<string, number>;
  tier_distribution: Record<string, number>;
  kod_subcheck_pass_rate: Record<string, SubcheckRow>;
}
interface WatchlistTrace {
  symbol: string; timeframe: string; outcome: string; reason_code: string;
  reason_text: string; score: number; tier: string; direction: string;
  htf_status: string; updated_at: string; signal_id: number | null;
}
export interface FunnelSnapshot {
  available?: boolean;
  detail?: string;
  stale?: boolean;
  age_seconds?: number;
  shadow_mode?: boolean;
  generated_at: string;
  started_at: string;
  uptime_seconds: number;
  scan_cycles: number;
  current_session: string;
  cumulative: SessionBlock;
  by_session: Record<string, SessionBlock>;
  watchlist_reasons: WatchlistTrace[];
  recent_traces: any[];
}

// The FUNNEL_UPDATE websocket frame is a deliberately trimmed projection of the
// snapshot: the full document is ~200KB, far too large to broadcast to every
// connected client every couple of scan cycles. It therefore carries only the
// fast-moving headline fields, flattened, and omits by_session, the score and
// spread distributions and the KOD sub-check rates.
export interface FunnelPush {
  scan_cycles: number;
  current_session: string;
  stages: FunnelRow[];
  rejection_reasons: ReasonRow[];
  outcomes: Record<string, number>;
  htf_distribution: Record<string, number>;
  tier_distribution: Record<string, number>;
  watchlist_reasons: WatchlistTrace[];
}

/** Overlay a trimmed websocket push onto the last polled snapshot.
 *
 * Returning the polled document untouched when no snapshot has loaded yet would
 * leave the panel empty until the first poll completes, so the push is also
 * able to stand alone with the fields it does carry.
 */
function mergePush(base: FunnelSnapshot | null, push: FunnelPush): FunnelSnapshot | null {
  if (!push || !Array.isArray(push.stages)) return base;
  const prev = base?.cumulative;
  const cumulative: SessionBlock = {
    funnel: push.stages,
    outcomes: push.outcomes ?? prev?.outcomes ?? {},
    rejection_reasons: push.rejection_reasons ?? prev?.rejection_reasons ?? [],
    htf_distribution: push.htf_distribution ?? prev?.htf_distribution ?? {},
    tier_distribution: push.tier_distribution ?? prev?.tier_distribution ?? {},
    // Not transmitted over the socket: keep the last polled values so the
    // tiles do not flicker to zero between HTTP refreshes.
    score: prev?.score ?? { count: 0, min: 0, avg: 0, median: 0, p95: 0, max: 0 },
    spread_pips: prev?.spread_pips ?? { count: 0, min: 0, avg: 0, median: 0, p95: 0, max: 0 },
    order_latency_ms: prev?.order_latency_ms ?? { count: 0, min: 0, avg: 0, median: 0, p95: 0, max: 0 },
    kod_subcheck_pass_rate: prev?.kod_subcheck_pass_rate ?? {},
  };
  return {
    ...(base ?? {
      generated_at: "", started_at: "", uptime_seconds: 0,
      by_session: {}, recent_traces: [],
    } as unknown as FunnelSnapshot),
    scan_cycles: push.scan_cycles ?? base?.scan_cycles ?? 0,
    current_session: push.current_session ?? base?.current_session ?? "",
    watchlist_reasons: push.watchlist_reasons ?? base?.watchlist_reasons ?? [],
    cumulative,
    // A live frame just arrived, so by definition the data is not stale.
    age_seconds: 0,
    stale: false,
  };
}

// ============================================================
// HELPERS
// ============================================================
const num = (v: any, f = 0) => { const n = Number(v); return Number.isFinite(n) ? n : f; };
const pct1 = (n: number) => `${num(n).toFixed(1)}%`;

const duration = (s: number) => {
  const t = Math.max(0, Math.floor(num(s)));
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${t % 60}s` : `${t}s`;
};

// Stages that indicate real progress toward an order. Colouring them
// differently makes the drop-off point obvious at a glance.
const EXECUTION_STAGES = new Set([
  "TIER_QUALIFIED", "RISK_APPROVED", "EXECUTION_GATE_PASSED",
  "SIZED", "ORDER_SENT", "FILLED", "POSITION_MANAGED", "CLOSED",
]);

const stageColor = (stage: string, count: number) => {
  if (count === 0) return "bg-slate-700";
  if (EXECUTION_STAGES.has(stage)) return "bg-[#10B981]";
  if (stage === "KOD_CONFIRMED" || stage === "HTF_CONFIRMED") return "bg-[#8B5CF6]";
  return "bg-blue-500";
};

const htfColor = (k: string) =>
  k === "ALIGNED" ? "text-[#10B981]"
    : k === "CONFLICT" ? "text-[#EF4444]"
    : k === "DATA_UNAVAILABLE" ? "text-[#F59E0B]" : "text-slate-400";

// ============================================================
// COMPONENT
// ============================================================
export default function FunnelPanel({ pushed }: { pushed?: FunnelPush | null }) {
  const [snap, setSnap] = useState<FunnelSnapshot | null>(null);
  const [watchlist, setWatchlist] = useState<{ total: number; reasons: any[]; signals: any[] } | null>(null);
  const [cfg, setCfg] = useState<any>(null);
  const [scope, setScope] = useState<string>("cumulative");
  const [err, setErr] = useState<string>("");

  const base = useMemo(() => (
    typeof window !== "undefined" && window.location.hostname !== "localhost"
      ? `http://${window.location.hostname}:8000/api/v1`
      : (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1")
  ), []);

  const load = useCallback(async () => {
    try {
      const [f, w, c] = await Promise.all([
        fetch(`${base}/funnel/`).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${base}/funnel/watchlist/?hours=24`).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${base}/strategy-config/`).then(r => r.ok ? r.json() : null).catch(() => null),
      ]);
      if (f && f.available !== false) { setSnap(f); setErr(""); }
      else if (f && f.detail) setErr(f.detail);
      if (w) setWatchlist(w);
      if (c) setCfg(c);
    } catch { setErr("Funnel API unreachable."); }
  }, [base]);

  useEffect(() => { load(); const i = setInterval(load, 15000); return () => clearInterval(i); }, [load]);
  // A websocket push is always fresher than the polled snapshot file, but it
  // only carries a subset of the fields, so it is overlaid rather than swapped.
  useEffect(() => {
    if (!pushed) return;
    setSnap(prev => mergePush(prev, pushed));
  }, [pushed]);

  if (!snap) {
    return (
      <div className="rounded-xl border border-[#2A303C] bg-[#151921] p-8 text-center">
        <Filter size={28} className="mx-auto text-slate-600 mb-3" />
        <div className="text-slate-300 text-sm font-semibold">Signal funnel not available yet</div>
        <div className="text-slate-500 text-[11px] mt-2 max-w-xl mx-auto">
          {err || "Waiting for the engine to publish its first snapshot."}
        </div>
      </div>
    );
  }

  const block: SessionBlock = scope === "cumulative"
    ? snap.cumulative
    : (snap.by_session?.[scope] ?? snap.cumulative);

  const sessions = Object.keys(snap.by_session ?? {});
  const scanned = block.funnel?.[0]?.count ?? 0;
  const outcomes = block.outcomes ?? {};

  // The compound KOD rate is the product of the independent sub-check rates.
  // Showing it explains a zero KOD count that no single threshold accounts for.
  const compoundKod = Object.values(block.kod_subcheck_pass_rate ?? {})
    .reduce((acc, r) => acc * (num(r.pct) / 100), 1) * 100;

  return (
    <div className="space-y-4">
      {/* ---- HEADER ---- */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Tile icon={Activity} label="Scan cycles" value={String(snap.scan_cycles)} sub={`uptime ${duration(snap.uptime_seconds)}`} />
        <Tile icon={Layers} label="Evaluations" value={scanned.toLocaleString()} sub={`${scope === "cumulative" ? "all sessions" : scope}`} />
        <Tile icon={Clock} label="Session" value={snap.current_session || "-"} sub={`snapshot ${Math.round(num(snap.age_seconds))}s old`} accent={snap.stale ? "amber" : undefined} />
        <Tile
          icon={snap.shadow_mode ? ShieldAlert : ShieldCheck}
          label="Mode"
          value={snap.shadow_mode ? "SHADOW" : "LIVE"}
          sub={snap.shadow_mode ? "no orders transmitted" : "orders are real"}
          accent={snap.shadow_mode ? "amber" : "green"}
        />
        <Tile icon={Gauge} label="Would-execute" value={String(num(outcomes.SHADOW) + num(outcomes.ACTIVE))} sub={`${num(outcomes.REJECTED)} rejected`} accent="green" />
      </div>

      {/* ---- SCOPE SWITCH ---- */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">Scope</span>
        {["cumulative", ...sessions].map(s => (
          <button
            key={s}
            onClick={() => setScope(s)}
            className={`text-[10px] font-mono px-2.5 py-1 rounded-full border transition-colors ${
              scope === s
                ? "bg-blue-600/20 text-blue-400 border-blue-500/40"
                : "bg-slate-900/50 text-slate-400 border-slate-800 hover:text-slate-200"
            }`}
          >
            {s.toUpperCase()}
          </button>
        ))}
        <button onClick={load} className="ml-auto text-[10px] font-mono px-2.5 py-1 rounded-full border border-slate-800 bg-slate-900/50 text-slate-400 hover:text-slate-200 inline-flex items-center gap-1">
          <RefreshCw size={10} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* ---- FUNNEL ---- */}
        <Card title="Signal lifecycle funnel" icon={Filter}
              subtitle="% of scanned - and step conversion from the stage above">
          <div className="space-y-1.5">
            {(block.funnel ?? []).map(row => (
              <div key={row.stage} className="flex items-center gap-2">
                <div className="w-44 shrink-0 text-[10px] font-mono text-slate-400 truncate">{row.stage}</div>
                <div className="flex-1 h-4 bg-slate-900/70 rounded overflow-hidden relative">
                  <div className={`h-full ${stageColor(row.stage, row.count)} transition-all`}
                       style={{ width: `${Math.max(num(row.pct_of_scanned), row.count > 0 ? 0.7 : 0)}%` }} />
                </div>
                <div className="w-16 text-right text-[10px] font-mono text-slate-200">{row.count.toLocaleString()}</div>
                <div className="w-14 text-right text-[10px] font-mono text-slate-500">{pct1(row.pct_of_scanned)}</div>
                <div className={`w-14 text-right text-[10px] font-mono ${num(row.pct_of_previous) < 20 && row.count === 0 ? "text-[#EF4444]" : "text-slate-600"}`}>
                  {pct1(row.pct_of_previous)}
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* ---- REJECTIONS ---- */}
        <Card title="Why evaluations ended" icon={AlertTriangle}
              subtitle="every terminal state carries a machine-readable code">
          <div className="max-h-[340px] overflow-auto">
            <table className="w-full text-[10px] font-mono">
              <thead className="text-slate-500 sticky top-0 bg-[#151921]">
                <tr><th className="text-left py-1">CODE</th><th className="text-right">N</th><th className="text-right w-14">SHARE</th></tr>
              </thead>
              <tbody>
                {(block.rejection_reasons ?? []).map(r => {
                  const total = (block.rejection_reasons ?? []).reduce((a, x) => a + x.count, 0) || 1;
                  return (
                    <tr key={r.code} className="border-t border-slate-800/60 align-top">
                      <td className="py-1 pr-2">
                        <div className="text-slate-200">{r.code}</div>
                        <div className="text-slate-600 text-[9px] leading-tight">{r.text}</div>
                      </td>
                      <td className="text-right text-slate-300">{r.count.toLocaleString()}</td>
                      <td className="text-right text-slate-500">{pct1((r.count / total) * 100)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>

        {/* ---- HTF + TIER ---- */}
        <Card title="HTF confirmation & tier mix" icon={Layers}
              subtitle="HTF is computed per symbol from H4/D1 - never defaulted">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono mb-1.5">HTF status</div>
              {Object.entries(block.htf_distribution ?? {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => {
                const tot = Object.values(block.htf_distribution ?? {}).reduce((a, x) => a + x, 0) || 1;
                return (
                  <div key={k} className="flex justify-between text-[10px] font-mono py-0.5">
                    <span className={htfColor(k)}>{k}</span>
                    <span className="text-slate-400">{v.toLocaleString()} <span className="text-slate-600">({pct1((v / tot) * 100)})</span></span>
                  </div>
                );
              })}
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono mb-1.5">Tier</div>
              {Object.entries(block.tier_distribution ?? {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
                <div key={k} className="flex justify-between text-[10px] font-mono py-0.5">
                  <span className={k === "NONE" ? "text-slate-500" : "text-[#10B981]"}>{k}</span>
                  <span className="text-slate-400">{v.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-slate-800/60">
            <Mini label="Score avg" value={num(block.score?.avg).toFixed(1)} sub={`med ${num(block.score?.median).toFixed(0)} / max ${num(block.score?.max).toFixed(0)}`} />
            <Mini label="Spread median" value={`${num(block.spread_pips?.median).toFixed(1)}p`} sub={`p95 ${num(block.spread_pips?.p95).toFixed(0)}p`} />
            <Mini label="Order latency" value={block.order_latency_ms?.count ? `${num(block.order_latency_ms.avg).toFixed(0)}ms` : "n/a"} sub={`${num(block.order_latency_ms?.count)} orders`} />
          </div>
        </Card>

        {/* ---- KOD SUBCHECKS ---- */}
        <Card title="KOD sub-check pass rates" icon={Gauge}
              subtitle="each threshold measured independently, not short-circuited">
          <div className="space-y-1.5">
            {Object.entries(block.kod_subcheck_pass_rate ?? {}).sort((a, b) => a[1].pct - b[1].pct).map(([k, r]) => (
              <div key={k} className="flex items-center gap-2">
                <div className="w-44 shrink-0 text-[10px] font-mono text-slate-400 truncate">{k}</div>
                <div className="flex-1 h-3 bg-slate-900/70 rounded overflow-hidden">
                  <div className={`h-full ${r.pct < 15 ? "bg-[#EF4444]" : r.pct < 50 ? "bg-[#F59E0B]" : "bg-[#10B981]"}`}
                       style={{ width: `${Math.min(100, num(r.pct))}%` }} />
                </div>
                <div className="w-24 text-right text-[10px] font-mono text-slate-300">
                  {pct1(r.pct)} <span className="text-slate-600">({r.passed}/{r.evaluated})</span>
                </div>
              </div>
            ))}
          </div>
          {Object.keys(block.kod_subcheck_pass_rate ?? {}).length > 0 && (
            <div className="mt-3 pt-3 border-t border-slate-800/60 text-[10px] font-mono">
              <span className="text-slate-500">Compound (all five must pass): </span>
              <span className={compoundKod < 1 ? "text-[#EF4444] font-bold" : "text-slate-200"}>{compoundKod.toFixed(2)}%</span>
              <div className="text-slate-600 text-[9px] mt-1 leading-tight">
                KOD is required for Tier 1 and Tier 3. A compound rate near zero means
                those tiers are structurally unreachable and the narrowest sub-check
                above is the binding constraint.
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* ---- WATCHLIST ---- */}
      <Card title="Why signals are still on the watchlist" icon={Eye}
            subtitle={watchlist ? `${watchlist.total} open watchlist signals in the last 24h` : "live from the engine snapshot"}>
        {watchlist && watchlist.reasons?.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {watchlist.reasons.map((r: any) => (
              <div key={r.code} className="rounded-lg border border-slate-800 bg-slate-900/50 px-2.5 py-1.5">
                <div className="text-[10px] font-mono text-slate-200">{r.code}</div>
                <div className="text-[9px] text-slate-500">{r.count} signals - avg score {num(r.avg_score).toFixed(1)}</div>
              </div>
            ))}
          </div>
        )}
        <div className="max-h-[320px] overflow-auto">
          <table className="w-full text-[10px] font-mono">
            <thead className="text-slate-500 sticky top-0 bg-[#151921]">
              <tr>
                <th className="text-left py-1">SYMBOL</th><th className="text-left">TF</th>
                <th className="text-left">DIR</th><th className="text-right">SCORE</th>
                <th className="text-left pl-3">HTF</th><th className="text-left pl-3">BLOCKED BY</th>
              </tr>
            </thead>
            <tbody>
              {(snap.watchlist_reasons ?? []).slice(0, 60).map((w, i) => (
                <tr key={`${w.symbol}-${w.timeframe}-${i}`} className="border-t border-slate-800/60">
                  <td className="py-1 text-slate-200">{w.symbol}</td>
                  <td className="text-slate-500">{w.timeframe}</td>
                  <td className={w.direction === "BUY" ? "text-[#10B981]" : "text-[#EF4444]"}>{w.direction}</td>
                  <td className="text-right text-slate-300">{num(w.score).toFixed(0)}</td>
                  <td className={`pl-3 ${htfColor(w.htf_status)}`}>{w.htf_status || "-"}</td>
                  <td className="pl-3">
                    <div className="text-slate-300">{w.reason_code}</div>
                    <div className="text-slate-600 text-[9px] leading-tight max-w-xl truncate">{w.reason_text}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ---- ACTIVE CONFIG ---- */}
      {cfg?.config && (
        <Card title="Active strategy configuration" icon={ShieldCheck}
              subtitle="the values the engine is actually enforcing - all env-tunable">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {["tiers", "kod", "htf", "spread", "risk", "gate", "liquidity", "pipeline"].filter(g => cfg.config[g]).map(g => (
              <div key={g} className="rounded-lg border border-slate-800 bg-slate-900/40 p-2.5">
                <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono mb-1">{g}</div>
                {Object.entries(cfg.config[g]).slice(0, 8).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-2 text-[9px] font-mono py-0.5">
                    <span className="text-slate-500 truncate">{k}</span>
                    <span className="text-slate-300 shrink-0">{String(v)}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

// ============================================================
// SUB-COMPONENTS
// ============================================================
const Card = ({ title, subtitle, icon: Icon, children }: { title: string; subtitle?: string; icon: any; children: React.ReactNode }) => (
  <div className="rounded-xl border border-[#2A303C] bg-[#151921] p-4">
    <div className="flex items-start gap-2 mb-3">
      <Icon size={14} className="text-slate-400 mt-0.5" />
      <div>
        <div className="text-[11px] uppercase tracking-widest text-slate-300 font-mono font-semibold">{title}</div>
        {subtitle && <div className="text-[9px] text-slate-600 mt-0.5">{subtitle}</div>}
      </div>
    </div>
    {children}
  </div>
);

const Tile = ({ icon: Icon, label, value, sub, accent }: { icon: any; label: string; value: string; sub?: string; accent?: string }) => (
  <div className="rounded-xl border border-[#2A303C] bg-[#151921] p-4">
    <div className="flex items-center gap-2 mb-1">
      <Icon size={14} className={accent === "green" ? "text-[#10B981]" : accent === "amber" ? "text-[#F59E0B]" : "text-slate-400"} />
      <span className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">{label}</span>
    </div>
    <div className={`text-lg font-bold font-mono mt-0.5 ${accent === "green" ? "text-[#10B981]" : accent === "amber" ? "text-[#F59E0B]" : "text-[#F3F4F6]"}`}>{value}</div>
    {sub && <div className="text-[10px] text-slate-600 mt-0.5">{sub}</div>}
  </div>
);

const Mini = ({ label, value, sub }: { label: string; value: string; sub?: string }) => (
  <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-2">
    <div className="text-[9px] uppercase tracking-widest text-slate-500 font-mono">{label}</div>
    <div className="text-sm font-bold font-mono text-slate-200">{value}</div>
    {sub && <div className="text-[9px] text-slate-600">{sub}</div>}
  </div>
);
