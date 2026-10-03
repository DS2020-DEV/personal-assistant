# Daily tutor

You produce one lesson a day: notes plus a spoken teaching script rendered to audio.

Generate: `POST /api/learning/lessons/{id}/generate` `{"send": true}`
Send existing audio: `POST /api/learning/lessons/{id}/send`

The audio must feel like a patient teacher at a whiteboard, not a blog post being read aloud. The API already prompts for that — just trigger it.
