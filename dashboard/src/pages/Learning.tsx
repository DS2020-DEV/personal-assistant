import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";

export default function Learning() {
  const [plans, setPlans] = useState<any[]>([]);
  const [topic, setTopic] = useState("System design");
  const [goal, setGoal] = useState("Be able to design and explain production systems.");
  const [days, setDays] = useState(10);
  const [selected, setSelected] = useState<any>(null);
  const [busy, setBusy] = useState("");

  const load = async () => {
    const data = await api.get("/api/learning/plans");
    setPlans(data);
    if (data[0] && !selected) setSelected(data[0]);
  };
  useEffect(() => { load().catch(() => {}); }, []);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setBusy("Planning curriculum…");
    try {
      const plan = await api.post("/api/learning/plans", { topic, goal, days, daily_time: "09:00" });
      setSelected(plan);
      await load();
    } finally {
      setBusy("");
    }
  };

  const generate = async (lesson: any, send: boolean) => {
    setBusy(send ? "Teaching + sending to WhatsApp…" : "Writing notes and audio…");
    try {
      await api.post(`/api/learning/lessons/${lesson.id}/generate`, { send });
      const fresh = await api.get(`/api/learning/plans/${selected.id}`);
      setSelected(fresh);
      await load();
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="stack">
      <form className="card stack" onSubmit={create}>
        <h2>New learning plan</h2>
        <p className="muted">Creates a day-by-day curriculum. The daily tutor sends one spoken lesson plus notes to WhatsApp.</p>
        <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Topic, e.g. System design" />
        <textarea value={goal} onChange={(e) => setGoal(e.target.value)} />
        <div className="row">
          <input type="number" min={3} max={30} value={days} onChange={(e) => setDays(Number(e.target.value))} />
          <button className="btn primary" type="submit" disabled={!!busy}>Plan this topic</button>
        </div>
        {busy && <p className="muted">{busy}</p>}
      </form>
      <div className="grid split">
        <div className="card">
          <h2>Plans</h2>
          {plans.map((plan) => (
            <button key={plan.id} className="btn" onClick={() => setSelected(plan)} style={{ width: "100%", marginBottom: 8 }}>
              {plan.topic} · {plan.current_day}/{plan.total_days} · {plan.status}
            </button>
          ))}
        </div>
        <div className="card">
          {!selected && <p className="muted">Select a plan.</p>}
          {selected && (
            <div className="stack">
              <h2>{selected.topic}</h2>
              <p className="muted">{selected.goal}</p>
              {(selected.lessons || []).map((lesson: any) => (
                <div key={lesson.id} className="card" style={{ boxShadow: "none" }}>
                  <strong>Day {lesson.day_index}: {lesson.title}</strong>
                  <div className="muted">{lesson.objectives}</div>
                  <div className="row" style={{ marginTop: 8 }}>
                    <span className="badge">{lesson.status}</span>
                    <button className="btn" onClick={() => generate(lesson, false)}>Generate</button>
                    <button className="btn primary" onClick={() => generate(lesson, true)}>Generate + WhatsApp</button>
                  </div>
                  {lesson.audio_url && <audio controls src={lesson.audio_url} style={{ width: "100%", marginTop: 8 }} />}
                  {lesson.notes_md && <pre className="notes">{lesson.notes_md}</pre>}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
