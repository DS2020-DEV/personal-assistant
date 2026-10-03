import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import Overview from "./pages/Overview";
import Tasks from "./pages/Tasks";
import Reminders from "./pages/Reminders";
import Learning from "./pages/Learning";
import Meetings from "./pages/Meetings";
import Activity from "./pages/Activity";
import Notes from "./pages/Notes";
import Settings from "./pages/Settings";

const NAV = [
  ["overview", "Overview"],
  ["tasks", "Tasks"],
  ["reminders", "Reminders"],
  ["learning", "Learning"],
  ["meetings", "Meetings"],
  ["notes", "Notes"],
  ["activity", "Activity"],
  ["settings", "Settings"],
] as const;

type Page = (typeof NAV)[number][0];

export default function App() {
  const [page, setPage] = useState<Page>("overview");
  const [status, setStatus] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    try {
      const next = await api.get("/api/system/status");
      setStatus(next);
      setError("");
    } catch {
      /* Keep the last good status. Poll failures should not paint every page. */
    }
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, []);

  const toggle = async () => {
    setBusy(true);
    setError("");
    try {
      const next = await api.post(status?.assistants ? "/api/system/stop" : "/api/system/start");
      setStatus(next);
      if (next?.error) setError(next.error);
    } catch (err) {
      setError(String(err).replace(/^Error:\s*/, ""));
    } finally {
      setBusy(false);
    }
  };

  const title = useMemo(() => NAV.find((item) => item[0] === page)?.[1] || "Overview", [page]);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span>Local only · 127.0.0.1</span>
          <strong>Claw Desk</strong>
        </div>
        <nav>
          {NAV.map(([id, label]) => (
            <button key={id} className={page === id ? "active" : ""} onClick={() => setPage(id)}>
              {label}
            </button>
          ))}
        </nav>
        <div className="side-foot">
          Qwen on your RTX 5050 · WhatsApp via OpenClaw · dashboard never binds beyond localhost.
        </div>
      </aside>
      <section className="main">
        <header className="topbar">
          <h1>{title}</h1>
          <div className="actions">
            <span className={`pill ${status?.assistants ? "ok" : "bad"}`}>
              {status?.assistants ? "Assistants on" : "Assistants paused"}
            </span>
            <span className={`pill ${status?.jevConfigured ? "ok" : ""}`}>
              {status?.jevConfigured ? "Jev on" : "Jev off"}
            </span>
            <span className={`pill ${status?.azureConfigured ? "ok" : ""}`}>
              {status?.azureConfigured ? "Azure on" : "Azure off"}
            </span>
            <button className="btn icon" title="Settings" onClick={() => setPage("settings")}>
              ⚙
            </button>
            <button className={status?.assistants ? "btn danger" : "btn primary"} onClick={toggle} disabled={busy}>
              {busy ? "Working…" : status?.assistants ? "Stop" : "Start"}
            </button>
          </div>
        </header>
        <div className="content">
          {error && (
            <div className="card error">
              {error}
              {status?.nextStep && <div className="muted" style={{ marginTop: 8 }}>{status.nextStep}</div>}
            </div>
          )}
          {page === "overview" && <Overview status={status} onOpen={setPage} />}
          {page === "tasks" && <Tasks />}
          {page === "reminders" && <Reminders />}
          {page === "learning" && <Learning />}
          {page === "meetings" && <Meetings />}
          {page === "notes" && <Notes />}
          {page === "activity" && <Activity />}
          {page === "settings" && <Settings onSaved={refresh} />}
        </div>
      </section>
    </div>
  );
}
