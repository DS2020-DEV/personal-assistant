---
name: pa-tutor
description: Generate and WhatsApp the day's lesson audio and notes.
---

Call `http://127.0.0.1:8787/api/learning/lessons/{id}/generate` with `{"send": true}`.
Do not write your own TTS. The local Kokoro pipeline handles natural speech.
