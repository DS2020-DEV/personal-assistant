import { useEffect, useState } from "react";
import { api } from "../api";

export default function Activity() {
  const [rows, setRows] = useState<any[]>([]);
  const load = () => api.get("/api/activity?limit=200").then(setRows).catch(() => {});
  useEffect(() => {
    load();
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="card">
      <h2>Live activity</h2>
      <table className="table">
        <thead><tr><th>Time</th><th>Agent</th><th>Action</th><th>Detail</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{new Date(row.ts).toLocaleString()}</td>
              <td><span className="badge">{row.agent}</span></td>
              <td>{row.action}</td>
              <td className="muted">{row.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
