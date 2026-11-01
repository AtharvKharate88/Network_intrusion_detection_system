import React, { useCallback, useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function StatCard({ label, value, tone = "" }) {
  return (
    <article className={`stat-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function App() {
  const [events, setEvents] = useState([]);
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: "50" });
      if (filter !== "all") params.set("alert", String(filter === "alerts"));
      const [eventResponse, statsResponse] = await Promise.all([
        fetch(`${API_BASE}/api/events?${params}`),
        fetch(`${API_BASE}/api/events/stats`),
      ]);
      if (!eventResponse.ok || !statsResponse.ok) {
        throw new Error("The API returned an error.");
      }
      setEvents(await eventResponse.json());
      setStats(await statsResponse.json());
      setError("");
    } catch (requestError) {
      setError(requestError.message);
    }
  }, [filter]);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">NETWORK INTRUSION DETECTION SYSTEM</p>
          <h1>Command Center</h1>
        </div>
        <div className="live-status"><i /> LIVE API FEED · 5s</div>
      </header>

      {error && <div className="error-banner">API unavailable: {error}</div>}

      <section className="stats-grid">
        <StatCard label="Total flows" value={stats?.total_events ?? "—"} />
        <StatCard label="Active alerts" value={stats?.total_alerts ?? "—"} tone="danger" />
        <StatCard label="Normal traffic" value={stats?.normal_events ?? "—"} tone="success" />
        <StatCard label="Attack events" value={stats?.attack_events ?? "—"} tone="warning" />
      </section>

      <section className="content-grid">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">TELEMETRY</p>
              <h2>Recent flow events</h2>
            </div>
            <div className="filters">
              {["all", "alerts", "normal"].map((item) => (
                <button className={filter === item ? "active" : ""} onClick={() => setFilter(item)} key={item}>
                  {item}
                </button>
              ))}
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Class</th><th>Source</th><th>Destination</th><th>Time</th></tr></thead>
              <tbody>
                {events.map((event) => (
                  <tr onClick={() => setSelected(event)} key={event.id}>
                    <td><span className={`badge ${event.alert ? "attack" : "normal"}`}>{event.predicted_class}</span></td>
                    <td>{event.source_ip || "—"}:{event.source_port || "—"}</td>
                    <td>{event.destination_ip || "—"}:{event.destination_port || "—"}</td>
                    <td>{new Date(event.created_at).toLocaleTimeString()}</td>
                  </tr>
                ))}
                {!events.length && <tr><td colSpan="4" className="empty">No persisted events yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        <aside className="panel distribution">
          <p className="eyebrow">MODEL OUTPUT</p>
          <h2>Attack distribution</h2>
          {Object.entries(stats?.attack_distribution || {}).map(([name, count]) => (
            <div className="distribution-row" key={name}>
              <div><span>{name}</span><b>{count}</b></div>
              <div className="bar"><span style={{ width: `${(count / (stats?.total_events || 1)) * 100}%` }} /></div>
            </div>
          ))}
          {!stats && <p className="muted">Waiting for API data…</p>}
        </aside>
      </section>

      {selected && (
        <div className="detail-drawer">
          <button className="close" onClick={() => setSelected(null)}>×</button>
          <p className="eyebrow">EVENT INSPECTION</p>
          <h2>{selected.predicted_class}</h2>
          <p className="muted">Flow {selected.flow_id}</p>
          <dl>
            <dt>Source</dt><dd>{selected.source_ip || "—"}:{selected.source_port || "—"}</dd>
            <dt>Destination</dt><dd>{selected.destination_ip || "—"}:{selected.destination_port || "—"}</dd>
            <dt>Observed</dt><dd>{new Date(selected.created_at).toLocaleString()}</dd>
          </dl>
        </div>
      )}
    </main>
  );
}
export default App;
