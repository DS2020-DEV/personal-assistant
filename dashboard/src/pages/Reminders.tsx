import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";

const empty = { title: "", message: "", kind: "once", run_at: "", time_of_day: "08:30", weekday: 0, enabled: true };

export default function Reminders() {
  const [rows, setRows] = useState<any[]>([]);
  const [form, setForm] = useState(empty);
  const load = () => api.get("/api/reminders").then(setRows).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    await api.post("/api/reminders", {
      ...form,
      run_at: form.run_at ? new Date(form.run_at).toISOString() : null,
      weekday: form.kind === "weekly" ? Number(form.weekday) : null,
      time_of_day: form.kind === "once" ? null : form.time_of_day,
    });
    setForm(empty);
    load();
  };

  return (
    <div className="grid split">
      <div className="card">
        <h2>Reminders</h2>
        <table className="table">
          <thead><tr><th>Title</th><th>When</th><th></th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <strong>{row.title}</strong>
                  <div className="muted">{row.message}</div>
                </td>
                <td>
                  {row.kind}
                  {row.time_of_day ? ` · ${row.time_of_day}` : ""}
                  {row.run_at ? ` · ${new Date(row.run_at).toLocaleString()}` : ""}
                </td>
                <td><button className="btn ghost" onClick={() => api.delete(`/api/reminders/${row.id}`).then(load)}>Delete</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form className="card stack" onSubmit={create}>
        <h2>Set a reminder</h2>
        <input placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
        <textarea placeholder="Message sent on WhatsApp" value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} />
        <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
          <option value="once">Once</option>
          <option value="daily">Every day</option>
          <option value="weekly">Weekly</option>
        </select>
        {form.kind === "once" && (
          <input type="datetime-local" value={form.run_at} onChange={(e) => setForm({ ...form, run_at: e.target.value })} />
        )}
        {form.kind !== "once" && (
          <input type="time" value={form.time_of_day} onChange={(e) => setForm({ ...form, time_of_day: e.target.value })} />
        )}
        {form.kind === "weekly" && (
          <select value={form.weekday} onChange={(e) => setForm({ ...form, weekday: Number(e.target.value) })}>
            {["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map((d, i) => (
              <option key={d} value={i}>{d}</option>
            ))}
          </select>
        )}
        <button className="btn primary" type="submit">Save reminder</button>
      </form>
    </div>
  );
}
