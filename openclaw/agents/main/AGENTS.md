# WhatsApp orchestrator

WhatsApp inbound is claimed by the `pa-inbox` plugin and posted to `http://127.0.0.1:8787/api/inbox`. Do not run a long local-model turn on audio or long messages.

If you ever handle a message yourself, POST `/api/inbox` and reply only with the API `reply` field. Never send compaction, `/compact`, or `/new` status text to WhatsApp.

