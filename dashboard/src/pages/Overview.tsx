import { useEffect, useState } from "react";
import { api } from "../api";
import WhatsAppQr from "./WhatsAppQr";

export default function Overview({ status, onOpen }: { status: any; onOpen: (page: any) => void }) {
  const [tasks, setTasks] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [activity, setActivity] = useState<any[]>([]);

  useEffect(() => {
    api.get("/api/tasks").then(setTasks).catch(() => {});
    api.get("/api/learning/plans").then(setPlans).catch(() => {});
    api.get("/api/activity?limit=8").then(setActivity).catch(() => {});
  }, []);

  const openTasks = tasks.filter((t) => t.status === "open");
  const activePlan = plans.find((p) => p.status === "active");

  return (
    <div className="stack">
      <div className="card stack">
        <h2>WhatsApp pairing QR</h2>
        <WhatsAppQr />
      </div>
      <div className="grid cards">
        <div className="card">
          <h3>Runtime</h3>
          <p className="muted">{status?.gpuHint}</p>
          <p>Ollama {status?.ollama ? "reachable" : "down"}</p>
          <p>OpenClaw {status?.openclaw ? "running" : "idle"}</p>
          <p>WhatsApp {status?.whatsappLinked ? "linked" : status?.whatsappConfigured ? "target set, not linked" : "not configured"}</p>
          <p>Jev {status?.jevConfigured ? "routing WhatsApp" : "off — using regex + Qwen"}</p>
          <p>Azure OpenAI {status?.azureConfigured ? "ready for hard jobs / vision" : "off"}</p>
          {status?.missing?.length > 0 && (
            <p className="error">
              Missing: {status.missing.join(", ")}. Run scripts\bootstrap.ps1 then press Start.
            </p>
          )}
        </div>
        <div className="card">
          <h3>Open tasks</h3>
          <p style={{ fontSize: 28, margin: 0 }}>{openTasks.length}</p>
          <button className="btn" onClick={() => onOpen("tasks")}>Manage tasks</button>
        </div>
        <div className="card">
          <h3>Learning</h3>
          <p>{activePlan ? `${activePlan.topic} · day ${activePlan.current_day}/${activePlan.total_days}` : "No active plan"}</p>
          <button className="btn" onClick={() => onOpen("learning")}>Open tutor</button>
        </div>
      </div>
      <div className="grid split">
        <div className="card">
          <h2>Today's work</h2>
          {openTasks.length === 0 && <p className="muted">No open tasks.</p>}
          <ul>
            {openTasks.slice(0, 8).map((task) => (
              <li key={task.id}>{task.title}</li>
            ))}
          </ul>
        </div>
        <div className="card">
          <h2>Recent activity</h2>
          {activity.map((row) => (
            <p key={row.id}>
              <span className="badge">{row.agent}</span> {row.action}
              <div className="muted">{row.detail}</div>
            </p>
          ))}
        </div>
      </div>
    </div>
  );
}
