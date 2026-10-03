# Meeting agent

When WhatsApp audio is a meeting or lecture recording, POST it to
`http://127.0.0.1:8787/api/inbox` with `media_kind: "audio"` or
`POST /api/meetings/from-path?path=...&title=...`

Create meeting reminders with `POST /api/meetings/reminders`.
Action items become tasks automatically.
