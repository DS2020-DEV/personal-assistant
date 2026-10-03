# Research and learning agent

Turn a topic into a multi-day curriculum via `POST http://127.0.0.1:8787/api/learning/plans`
Body: `{"topic":"System design","goal":"...","days":10,"daily_time":"09:00"}`

Then ask the daily tutor to generate today's lesson.
Never invent files that the API did not create.
