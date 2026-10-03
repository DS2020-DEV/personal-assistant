---
name: pa-learning
description: Create a multi-day learning plan from a topic such as system design.
---

POST `http://127.0.0.1:8787/api/learning/plans` with topic, goal, days, daily_time.
Then POST `http://127.0.0.1:8787/api/learning/lessons/{id}/generate` with `{"send": true}` for day 1.
