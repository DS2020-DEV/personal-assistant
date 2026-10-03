import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import WhatsAppQr from "./WhatsAppQr";

export default function Settings({ onSaved }: { onSaved?: () => void }) {
  const [settings, setSettings] = useState<any>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.get("/api/settings").then(setSettings);
  }, []);

  if (!settings) return <div className="card">Loading settings…</div>;

  const set = (path: string[], value: any) => {
    const next = structuredClone(settings);
    let cur = next;
    for (const key of path.slice(0, -1)) {
      if (cur[key] == null || typeof cur[key] !== "object") cur[key] = {};
      cur = cur[key];
    }
    cur[path[path.length - 1]] = value;
    setSettings(next);
  };

  const save = async (e: FormEvent) => {
    e.preventDefault();
    const saved = await api.put("/api/settings", { settings });
    setSettings(saved);
    setMsg("Saved. Scheduler times and model choice apply immediately.");
    onSaved?.();
  };

  const autostart = async (enable: boolean) => {
    try {
      const result = await api.post("/api/system/autostart", { enabled: enable });
      set(["autostart", "windows"], Boolean(result.enabled));
      setMsg(
        result.enabled
          ? "Windows logon autostart is on. The dashboard will open at http://127.0.0.1:8787 after you sign in."
          : "Windows logon autostart is off."
      );
      onSaved?.();
    } catch (err) {
      setMsg(String(err).replace(/^Error:\s*/, ""));
    }
  };

  return (
    <form className="stack" onSubmit={save}>
      <div className="card stack">
        <h2>Local runtime</h2>
        <label>Timezone
          <input value={settings.timezone} onChange={(e) => set(["timezone"], e.target.value)} />
        </label>
        <label>Qwen model
          <select value={settings.model.name} onChange={(e) => set(["model", "name"], e.target.value)}>
            <option value="qwen2.5:7b">qwen2.5:7b — best fit for 8GB (recommended)</option>
            <option value="qwen3:8b">qwen3:8b — stronger reasoning, tighter VRAM</option>
          </select>
        </label>
        <label>Context tokens
          <input type="number" value={settings.model.numCtx} onChange={(e) => set(["model", "numCtx"], Number(e.target.value))} />
        </label>
      </div>
      <div className="card stack">
        <h2>Jev (TypeSafe System One)</h2>
        <p className="muted">Fast typed routing for WhatsApp: classify, score complexity, refuse risky asks. Jev cannot write notes — Qwen / Azure do that. Get a key from typesafe.ai early access.</p>
        <label className="row">
          <input type="checkbox" checked={Boolean(settings.typesafe?.enabled)} onChange={(e) => set(["typesafe", "enabled"], e.target.checked)} />
          Enable Jev router
        </label>
        <label>API key {settings.typesafe?.apiKeySet ? "(saved)" : ""}
          <input type="password" autoComplete="off" placeholder={settings.typesafe?.apiKeySet ? "••••••••  leave blank to keep" : "sk-…"} value={settings.typesafe?.apiKey || ""} onChange={(e) => set(["typesafe", "apiKey"], e.target.value)} />
        </label>
      </div>
      <div className="card stack">
        <h2>Azure OpenAI (optional, hard jobs)</h2>
        <p className="muted">Used only when Jev scores the request as high complexity, or for screenshot description. Endpoint looks like https://YOUR-RESOURCE.openai.azure.com</p>
        <label className="row">
          <input type="checkbox" checked={Boolean(settings.azureOpenAI?.enabled)} onChange={(e) => set(["azureOpenAI", "enabled"], e.target.checked)} />
          Enable Azure OpenAI
        </label>
        <label>Endpoint
          <input value={settings.azureOpenAI?.endpoint || ""} onChange={(e) => set(["azureOpenAI", "endpoint"], e.target.value)} placeholder="https://….openai.azure.com" />
        </label>
        <label>API key {settings.azureOpenAI?.apiKeySet ? "(saved)" : ""}
          <input type="password" autoComplete="off" value={settings.azureOpenAI?.apiKey || ""} onChange={(e) => set(["azureOpenAI", "apiKey"], e.target.value)} />
        </label>
        <label>Chat deployment name (vision-capable, e.g. gpt-4o)
          <input value={settings.azureOpenAI?.deployment || ""} onChange={(e) => set(["azureOpenAI", "deployment"], e.target.value)} />
        </label>
      </div>
      <div className="card stack">
        <h2>Computer use</h2>
        <p className="muted">Allowlisted only: screenshot + describe, open Cursor and type a prompt (Ctrl+L), Notepad, Chrome. Move the mouse to a corner to abort pyautogui.</p>
        <label className="row">
          <input type="checkbox" checked={settings.computer?.enabled !== false} onChange={(e) => set(["computer", "enabled"], e.target.checked)} />
          Enable desktop operator
        </label>
        <label className="row">
          <input type="checkbox" checked={settings.computer?.sendCursorPrompt !== false} onChange={(e) => set(["computer", "sendCursorPrompt"], e.target.checked)} />
          Press Enter after typing in Cursor chat
        </label>
        <label>Cursor.exe path (optional)
          <input value={settings.computer?.cursorPath || ""} onChange={(e) => set(["computer", "cursorPath"], e.target.value)} placeholder="C:\Users\…\AppData\Local\Programs\cursor\Cursor.exe" />
        </label>
      </div>
      <div className="card stack">
        <h2>WhatsApp</h2>
        <label>Your number / chat target (E.164, e.g. +91…)
          <input value={settings.whatsapp.target} onChange={(e) => set(["whatsapp", "target"], e.target.value)} />
        </label>
        <WhatsAppQr />
      </div>
      <div className="card stack">
        <h2>Daily clocks</h2>
        <label>Task reminder
          <input type="time" value={settings.schedule.dailyReminderTime} onChange={(e) => set(["schedule", "dailyReminderTime"], e.target.value)} />
        </label>
        <label>Tomorrow's reminders (WhatsApp)
          <input type="time" value={settings.schedule.eveningPreviewTime || "23:00"} onChange={(e) => set(["schedule", "eveningPreviewTime"], e.target.value)} />
        </label>
        <label>Daily lesson
          <input type="time" value={settings.schedule.dailyLessonTime} onChange={(e) => set(["schedule", "dailyLessonTime"], e.target.value)} />
        </label>
        <label>Lesson length (minutes)
          <input type="number" value={settings.learning.lessonMinutes} onChange={(e) => set(["learning", "lessonMinutes"], Number(e.target.value))} />
        </label>
      </div>
      <div className="card stack">
        <h2>Voice</h2>
        <label>Kokoro voice
          <select value={settings.tts.voice} onChange={(e) => set(["tts", "voice"], e.target.value)}>
            <option value="am_michael">am_michael — calm US teacher</option>
            <option value="af_heart">af_heart — warm US</option>
            <option value="bm_george">bm_george — British lecturer</option>
            <option value="bf_emma">bf_emma — British</option>
          </select>
        </label>
        <label>Whisper size
          <select value={settings.stt.model} onChange={(e) => set(["stt", "model"], e.target.value)}>
            <option value="tiny.en">tiny.en — fastest</option>
            <option value="base.en">base.en — recommended</option>
            <option value="small.en">small.en — better notes, slower CPU</option>
          </select>
        </label>
      </div>
      <div className="card stack">
        <h2>Start with Windows</h2>
        <p className="muted">The dashboard stays local. Start/Stop only pauses the GPU assistants; the control page stays available.</p>
        <div className="row">
          <button type="button" className="btn" onClick={() => autostart(true)}>Enable autostart</button>
          <button type="button" className="btn" onClick={() => autostart(false)}>Disable autostart</button>
        </div>
      </div>
      <button className="btn primary" type="submit">Save settings</button>
      {msg && <p className="muted">{msg}</p>}
    </form>
  );
}
