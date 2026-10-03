---
name: pa-router
description: Forward WhatsApp text and audio to the local personal assistant API. Use for every inbound user message.
metadata:
  openclaw:
    emoji: "🦞"
    os: ["win32", "linux", "darwin"]
---

The source of truth is `http://127.0.0.1:8787`.

When a WhatsApp message arrives:

1. If it includes audio or a voice note, save the file to disk, then POST:

```
POST http://127.0.0.1:8787/api/inbox
Content-Type: application/json

{
  "text": "<caption or empty>",
  "media_path": "<absolute path to the audio>",
  "media_kind": "audio",
  "sender": "<peer id if known>",
  "source": "whatsapp"
}
```

2. If it is text only, POST:

```
{
  "text": "<full message>",
  "source": "whatsapp"
}
```

3. Answer the user with the JSON field `reply`. Never send compaction, `/compact`, or `/new` status text.
4. If the API fails, say the local assistant is paused and they should press Start on http://127.0.0.1:8787

Examples (still always POST `/api/inbox`; do not improvise local files):
- `create task …` / `remind me …` / `learn system design`
- `note: …` or a voice memo
- meeting / lecture audio
- `open cursor and write this prompt: …`
- `what's on my screen`

Use `exec` with curl.exe if needed:

`curl.exe -s -X POST http://127.0.0.1:8787/api/inbox -H "Content-Type: application/json" -d "{...}"`
