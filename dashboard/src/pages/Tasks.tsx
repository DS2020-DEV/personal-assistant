import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";

const empty = { title: "", description: "", priority: "normal", due_at: "", status: "open", source: "dashboard" };

export default function Tasks() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [form, setForm] = useState(empty);
  const load = () => api.get("/api/tasks").then(setTasks).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    await api.post("/api/tasks", {
      ...form,
      due_at: form.due_at ? new Date(form.due_at).toISOString() : null,
    });
    setForm(empty);
    load();
  };

  const complete = async (task: any) => {
    await api.patch(`/api/tasks/${task.id}`, { ...task, status: "done" });
    load();
  };

  return (
    <div className="grid split">
      <div className="card">
        <h2>Open and done</h2>
        <table className="table">
          <thead>
            <tr><th>Task</th><th>Priority</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr key={task.id}>
                <td>
                  <strong>{task.title}</strong>
                  <div className="muted">{task.description}</div>
                </td>
                <td>{task.priority}</td>
                <td><span className="badge">{task.status}</span></td>
                <td className="row">
                  {task.status !== "done" && <button className="btn" onClick={() => complete(task)}>Done</button>}
                  <button className="btn ghost" onClick={() => api.delete(`/api/tasks/${task.id}`).then(load)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form className="card stack" onSubmit={create}>
        <h2>New task</h2>
        <input placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
        <textarea placeholder="Details" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
          <option>low</option>
          <option>normal</option>
          <option>high</option>
        </select>
        <input type="datetime-local" value={form.due_at} onChange={(e) => setForm({ ...form, due_at: e.target.value })} />
        <button className="btn primary" type="submit">Save task</button>
      </form>
    </div>
  );
}
