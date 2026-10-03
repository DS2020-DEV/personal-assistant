import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";

const ACTION_LABEL: Record<string, string> = {
  received: "Message received",
  notes_ready: "Notes ready",
  failed: "Failed",
};

export default function Meetings() {
  const [data, setData] = useState<{ meetings: any[]; reminders: any[]; inbox: any[] }>({
    meetings: [],
    reminders: [],
    inbox: [],
  });
  const [title, setTitle] = useState("Meeting");
  const [remind, setRemind] = useState({ title: "", message: "", remind_at: "" });
  const load = () => api.get("/api/meetings").then(setData).catch(() => {});
  useEffect(() => {
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, []);

  const upload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    body.append("title", title);
    body.append("send", "true");
    await fetch("/api/meetings/upload", { method: "POST", body });
    load();
  };

  const addReminder = async (e: FormEvent) => {
    e.preventDefault();
    await api.post("/api/meetings/reminders", {
      ...remind,
      remind_at: new Date(remind.remind_at).toISOString(),
    });
    setRemind({ title: "", message: "", remind_at: "" });
    load();
  };

  return (
    <div className="stack">
      <div className="card">
        <h2>Incoming</h2>
        <p className="muted">WhatsApp voice notes and meeting recordings show here as soon as they arrive.</p>
        {(data.inbox || []).length === 0 && <p className="muted">Nothing received yet. Send a meeting recording from Message yourself.</p>}
        {(data.inbox || []).map((row) => (
          <p key={row.id}>
            <span className="badge">{ACTION_LABEL[row.action] || row.action}</span>{" "}
            {new Date(row.ts).toLocaleString()}
            <div className="muted">{row.detail}</div>
          </p>
        ))}
      </div>
      <div className="grid split">
        <div className="card stack">
          <h2>Meeting audio</h2>
          <p className="muted">Upload a recording, or send a WhatsApp voice note. Whisper transcribes on CPU so the GPU stays with Qwen.</p>
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
          <input type="file" accept="audio/*,video/*" onChange={upload} />
        </div>
        <form className="card stack" onSubmit={addReminder}>
          <h2>Meeting reminder</h2>
          <input placeholder="Standup" value={remind.title} onChange={(e) => setRemind({ ...remind, title: e.target.value })} required />
          <textarea placeholder="Bring yesterday's notes" value={remind.message} onChange={(e) => setRemind({ ...remind, message: e.target.value })} />
          <input type="datetime-local" value={remind.remind_at} onChange={(e) => setRemind({ ...remind, remind_at: e.target.value })} required />
          <button className="btn primary" type="submit">Remind me</button>
        </form>
      </div>
      <div className="card">
        <h2>Upcoming meeting reminders</h2>
        {data.reminders.map((row) => (
          <p key={row.id}>
            {row.title} · {new Date(row.remind_at).toLocaleString()} {row.sent ? "(sent)" : ""}
          </p>
        ))}
      </div>
      {data.meetings.map((meeting) => (
        <div className="card" key={meeting.id}>
          <h2>{meeting.title}</h2>
          <p className="muted">{meeting.source} · {new Date(meeting.created_at).toLocaleString()}</p>
          <pre className="notes">{meeting.notes_md || meeting.transcript}</pre>
        </div>
      ))}
    </div>
  );
}
