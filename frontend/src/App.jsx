import React, { useCallback, useEffect, useRef, useState } from "react";
import { SAMPLES } from "./samples";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

/* ─── helpers ─────────────────────────────────────────────────────────────── */
function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good Morning";
  if (h < 17) return "Good Afternoon";
  return "Good Evening";
}
function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
function fmtDate(iso) {
  return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
}

/* ─── icons (individual components, no shared path trick) ─────────────────── */
function HomeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  );
}
function BrainIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 8v4l3 3" />
    </svg>
  );
}
function ClockIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}
function GearIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}
function ShieldIcon({ size = 18, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
function ActivityIcon({ size = 18, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}
function AlertIcon({ size = 18, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}
function CheckIcon({ size = 18, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}
function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}
function BarIcon({ size = 18, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  );
}

/* ─── sidebar ─────────────────────────────────────────────────────────────── */
const NAV = [
  { id: "dashboard",   label: "Dashboard",   Ic: HomeIcon },
  { id: "predictions", label: "Predictions", Ic: BrainIcon },
  { id: "history",     label: "History",     Ic: ClockIcon },
  { id: "settings",    label: "Settings",    Ic: GearIcon },
];

function Sidebar({ active, onNav }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-icon"><ShieldIcon size={18} color="#fff" /></div>
        <span className="brand-name">NIDS</span>
      </div>
      <nav className="sidebar-nav">
        {NAV.map(({ id, label, Ic }) => (
          <button key={id} className={"nav-item" + (active === id ? " nav-active" : "")} onClick={() => onNav(id)}>
            <Ic /><span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-footer">
        <span className="live-dot" />
        <span>Live monitoring</span>
      </div>
    </aside>
  );
}

/* ─── topbar ──────────────────────────────────────────────────────────────── */
function TopBar({ onNewPrediction }) {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  const dateStr = now.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric", year: "numeric" });
  const timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  return (
    <header className="topbar">
      <div>
        <p className="greeting">{getGreeting()}, Admin 👋</p>
        <p className="topbar-date">{dateStr} · {timeStr}</p>
      </div>
      <button className="btn-primary" onClick={onNewPrediction}>
        <PlusIcon /> New Prediction
      </button>
    </header>
  );
}

/* ─── stat card ───────────────────────────────────────────────────────────── */
function StatCard({ label, value, Ic, iconBg, iconColor, valueColor }) {
  return (
    <div className="stat-card">
      <div className="stat-icon-wrap" style={{ background: iconBg }}>
        <Ic size={18} color={iconColor} />
      </div>
      <p className="stat-label">{label}</p>
      <p className="stat-value" style={{ color: valueColor }}>{value ?? "—"}</p>
    </div>
  );
}

/* ─── prediction panel ────────────────────────────────────────────────────── */
function PredictionPanel({ onResult }) {
  const [json, setJson] = useState("");
  const [status, setStatus] = useState("idle");
  const [errMsg, setErrMsg] = useState("");

  function loadSample(key) {
    const sample = { ...SAMPLES[key] };
    if (sample.flow_id) {
      sample.flow_id = `${key}-${Date.now().toString().slice(-5)}`;
    }
    setJson(JSON.stringify(sample, null, 2));
    setStatus("idle");
    setErrMsg("");
  }

  async function handlePredict() {
    setStatus("loading");
    setErrMsg("");
    let parsed;
    try {
      parsed = JSON.parse(json);
    } catch {
      setStatus("error");
      setErrMsg("Invalid JSON — please check your input.");
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed),
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error(e.detail || `Server error ${res.status}`);
      }
      onResult(await res.json());
      setStatus("idle");
    } catch (e) {
      setStatus("error");
      setErrMsg(e.message || "Cannot reach the API. Is the backend running?");
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <ActivityIcon color="#3B82F6" />
        <h2 className="card-title">Run Prediction</h2>
      </div>
      <div className="sample-row">
        <span className="sample-label">Load sample:</span>
        <button className="btn-sample" onClick={() => loadSample("normal")}>✅ Normal Traffic</button>
        <button className="btn-sample btn-sample-red" onClick={() => loadSample("portscan")}>🔍 Port Scan</button>
        <button className="btn-sample btn-sample-orange" onClick={() => loadSample("dos")}>⚡ DoS Attack</button>
      </div>
      <textarea
        className="json-area"
        placeholder="Paste JSON flow features here, or load a sample above…"
        value={json}
        onChange={(e) => setJson(e.target.value)}
        spellCheck={false}
      />
      {status === "error" && (
        <div className="error-box">
          <AlertIcon size={15} color="#DC2626" />
          <span>{errMsg}</span>
        </div>
      )}
      <button className="btn-primary btn-full" onClick={handlePredict} disabled={status === "loading" || !json.trim()}>
        {status === "loading" ? <><span className="spinner" /> Analyzing…</> : <><ShieldIcon size={15} color="#fff" /> Predict</>}
      </button>
    </div>
  );
}

/* ─── result card ─────────────────────────────────────────────────────────── */
function ResultCard({ result }) {
  if (!result) {
    return (
      <div className="card placeholder-card">
        <ShieldIcon size={40} color="#D1D5DB" />
        <p className="placeholder-title">Awaiting prediction</p>
        <p className="placeholder-sub">Paste a flow JSON and click Predict.</p>
      </div>
    );
  }
  const isAttack = result.alert;
  return (
    <div className={"card result-card " + (isAttack ? "result-attack" : "result-safe")}>
      <div className="card-header">
        <ShieldIcon size={18} color={isAttack ? "#EF4444" : "#22C55E"} />
        <h2 className="card-title">Prediction Result</h2>
      </div>
      {isAttack
        ? <div className="result-badge result-badge-attack">⚠️ Attack Detected: <strong>{result.predicted_class}</strong></div>
        : <div className="result-badge result-badge-safe">✅ Safe / Normal Traffic</div>
      }
      <div className="result-meta">
        <div className="meta-row"><span className="meta-label">Flow ID</span><span className="meta-mono">{result.flow_id}</span></div>
        <div className="meta-row"><span className="meta-label">Timestamp</span><span className="meta-mono">{new Date().toLocaleString()}</span></div>
        <div className="meta-row"><span className="meta-label">Model status</span><span className="meta-mono">{result.model_status}</span></div>
      </div>
    </div>
  );
}

/* ─── recent table ────────────────────────────────────────────────────────── */
function RecentTable({ events, loading, error }) {
  return (
    <div className="card">
      <div className="card-header">
        <BarIcon color="#3B82F6" />
        <h2 className="card-title">Recent Predictions</h2>
        <span className="refresh-badge"><span className="live-dot" />Auto-refresh 5s</span>
      </div>
      {error && <div className="error-box" style={{ marginBottom: 12 }}><AlertIcon size={15} color="#DC2626" /><span>{error}</span></div>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Time</th><th>Flow ID</th><th>Predicted Class</th><th>Status</th></tr>
          </thead>
          <tbody>
            {events.slice(0, 10).map((ev) => (
              <tr key={ev.id}>
                <td><span className="mono">{fmtTime(ev.created_at)}</span><br /><span className="sub-text">{fmtDate(ev.created_at)}</span></td>
                <td className="mono truncate">{ev.flow_id}</td>
                <td>{ev.predicted_class}</td>
                <td><span className={"badge " + (ev.alert ? "badge-attack" : "badge-normal")}>{ev.alert ? "Attack" : "Normal"}</span></td>
              </tr>
            ))}
            {!loading && events.length === 0 && <tr><td colSpan="4" className="td-empty">No predictions yet — run your first one above.</td></tr>}
            {loading && events.length === 0 && <tr><td colSpan="4" className="td-empty">Loading…</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ─── root ────────────────────────────────────────────────────────────────── */
export default function App() {
  const [activeNav, setActiveNav] = useState("dashboard");
  const [events, setEvents]       = useState([]);
  const [stats, setStats]         = useState(null);
  const [evError, setEvError]     = useState("");
  const [evLoading, setEvLoading] = useState(true);
  const [result, setResult]       = useState(null);
  const panelRef = useRef(null);

  const fetchData = useCallback(async () => {
    try {
      const [evRes, stRes] = await Promise.all([
        fetch(`${API_BASE}/api/events?limit=10`),
        fetch(`${API_BASE}/api/events/stats`),
      ]);
      if (!evRes.ok || !stRes.ok) throw new Error("API error");
      const [evData, stData] = await Promise.all([evRes.json(), stRes.json()]);
      setEvents(evData);
      setStats(stData);
      setEvError("");
    } catch (e) {
      setEvError(e.message || "Cannot reach the API.");
    } finally {
      setEvLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const t = setInterval(fetchData, 5000);
    return () => clearInterval(t);
  }, [fetchData]);

  function handleNewPrediction() {
    setActiveNav("dashboard");
    setTimeout(() => panelRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  function handleResult(data) {
    setResult(data);
    fetchData();
  }

  const accuracy = stats && stats.total_events > 0
    ? ((stats.normal_events / stats.total_events) * 100).toFixed(1) + "%"
    : "—";

  return (
    <div className="app-shell">
      <Sidebar active={activeNav} onNav={setActiveNav} />
      <div className="main-area">
        <TopBar onNewPrediction={handleNewPrediction} />
        <div className="page-content">
          <div className="stats-grid">
            <StatCard label="Total Predictions" value={stats?.total_events}  Ic={ActivityIcon} iconBg="#EFF6FF" iconColor="#3B82F6" valueColor="#1D4ED8" />
            <StatCard label="Attacks Detected"  value={stats?.total_alerts}  Ic={AlertIcon}    iconBg="#FEF2F2" iconColor="#EF4444" valueColor="#B91C1C" />
            <StatCard label="Normal Traffic"    value={stats?.normal_events} Ic={CheckIcon}    iconBg="#F0FDF4" iconColor="#22C55E" valueColor="#15803D" />
            <StatCard label="Detection Accuracy" value={accuracy}            Ic={BarIcon}      iconBg="#F5F3FF" iconColor="#8B5CF6" valueColor="#6D28D9" />
          </div>
          <div className="two-col" ref={panelRef}>
            <PredictionPanel onResult={handleResult} />
            <ResultCard result={result} />
          </div>
          <RecentTable events={events} loading={evLoading} error={evError} />
        </div>
      </div>
    </div>
  );
}
