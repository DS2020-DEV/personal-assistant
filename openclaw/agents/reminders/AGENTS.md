# Reminder agent

Create reminders through `http://127.0.0.1:8787/api/reminders`.

JSON fields: title, message, kind (`once|daily|weekly`), run_at (ISO), time_of_day (`HH:MM`), weekday (0=Monday).
