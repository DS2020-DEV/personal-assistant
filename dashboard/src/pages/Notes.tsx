import { useEffect, useState } from "react";
import { api } from "../api";

export default function Notes() {
  const [notes, setNotes] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);

  useEffect(() => {
    api.get("/api/notes").then(setNotes).catch(() => {});
    api.get("/api/computer/jobs").then(setJobs).catch(() => {});
  }, []);

  return (
    <div className="stack">
      <div className="card">
        <h2>WhatsApp notes</h2>
        <p className="muted">Voice memos, “note: …”, and study writeups land here. Meetings still live under Meetings; learning plans under Learning.</p>
        {notes.length === 0 && <p className="muted">No notes yet.</p>}
        {notes.map((note) => (
          <article key={note.id} className="card" style={{ marginTop: 12 }}>
            <strong>{note.title}</strong>
            <div className="muted">{note.kind} · {note.source}</div>
            <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{(note.body_md || "").slice(0, 2000)}</pre>
          </article>
        ))}
      </div>
      <div className="card">
        <h2>Computer jobs</h2>
        <p className="muted">Screenshot describe, open Cursor, type a prompt. Failsafe: slam the mouse into a screen corner.</p>
        {jobs.length === 0 && <p className="muted">No desktop jobs yet.</p>}
        {jobs.map((job) => (
          <p key={job.id}>
            <span className="badge">{job.status}</span> {job.action}
            <div className="muted">{(job.result || job.request || "").slice(0, 400)}</div>
          </p>
        ))}
      </div>
    </div>
  );
}
