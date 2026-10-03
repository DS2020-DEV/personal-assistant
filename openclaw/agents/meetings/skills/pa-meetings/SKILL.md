---
name: pa-meetings
description: Transcribe WhatsApp audio, write meeting notes, and set meeting reminders.
---

Inbox audio: POST `http://127.0.0.1:8787/api/inbox` with media_path.
Reminders: POST `http://127.0.0.1:8787/api/meetings/reminders` with title, message, remind_at (ISO).
