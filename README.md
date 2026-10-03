# Local OpenClaw assistant

Laptop-only personal assistant: **OpenClaw** agents, **TypeSafe Jev** for routing, **Ollama + Qwen 2.5 7B** (fits an 8GB GPU), optional **Azure OpenAI** for hard jobs and screen vision, WhatsApp, daily tutoring, meeting/study notes, allowlisted computer use (Cursor chat), and a dashboard bound to `127.0.0.1`.

## Why this Qwen

Your GPU is an **RTX 5050 Laptop (8GB)**.

| Model | Why |
| --- | --- |
| **`qwen2.5:7b`** (default) | ~4.7GB Q4, room for 8k context and tool calls. Best daily driver. |
| `qwen3:8b` (Settings) | Stronger reasoning, tighter VRAM. Use 4k context. |

Whisper and Kokoro TTS stay on **CPU** so the GPU is left for Qwen.

## What you get

- **Jev router** — [System One](https://typesafe.ai/blog/introducing-system-one-models-and-jev) classifies each WhatsApp message (intent, complexity, risk, desktop action) in one typed call. Jev does **not** write text; code + Qwen/Azure do the work.
- **WhatsApp agent** — inbound messages hit `/api/inbox`
- **Computer use** — screenshot + describe, open Cursor, type/send a prompt in chat (`Ctrl+L`). Allowlisted apps only.
- **Notes** — `note: …`, voice memos, study writeups from WhatsApp audio/text
- **Task agent** — create/complete tasks from chat or the dashboard
- **Reminder agent** — one-off, daily, weekly, plus a morning task digest
- **Learning agent** — turn `system design` (or any topic) into a multi-day plan
- **Daily tutor sub-agent** — one lesson/day as notes + natural teaching audio on WhatsApp
- **Meeting agent** — transcribe WhatsApp voice notes, notes, action items, meeting reminders
- **Dashboard** — monitor activity, set tasks/reminders, Start/Stop, Settings on every page

## One-time setup

In PowerShell:

```powershell
cd "D:\Personal assistant"
powershell -ExecutionPolicy Bypass -File ".\scripts\bootstrap.ps1"
powershell -ExecutionPolicy Bypass -File ".\scripts\start.ps1"
powershell -ExecutionPolicy Bypass -File ".\scripts\pair-whatsapp.ps1"
```

Or double-click `pair-whatsapp.cmd` in this folder.

Open [http://127.0.0.1:8787](http://127.0.0.1:8787). Put your WhatsApp number in **Settings**.

Start with Windows:

```powershell
powershell -File scripts\install-autostart.ps1
```

## Daily use

- **Start / Stop** in the header starts or pauses OpenClaw + the GPU model. The dashboard stays up so you can start again.
- WhatsApp: `create task …`, `remind me …`, `learn system design`, `note: …`, send a meeting or lecture voice note.
- Computer: unlock the laptop, then `open cursor and write this prompt: …` or `what's on my screen`.
- Paste a TypeSafe API key and (optional) Azure OpenAI endpoint/key/deployment in **Settings**. Jev routes; Azure only runs when the job is hard or needs vision.
- Learning: create a plan in the UI (or via WhatsApp). At the daily lesson time the tutor sends notes + audio.

## Stack

OpenClaw · TypeSafe Jev · Ollama · Qwen2.5-7B · optional Azure OpenAI · FastAPI · SQLite · Kokoro TTS · faster-whisper · pyautogui computer use · ffmpeg

Everything is intended to listen on localhost only.
