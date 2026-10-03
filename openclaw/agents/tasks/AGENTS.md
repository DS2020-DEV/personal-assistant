# Task agent

Create, list, and complete tasks through `http://127.0.0.1:8787/api/tasks`.

POST JSON: `{"title":"...","description":"...","priority":"normal","source":"whatsapp"}`
GET lists tasks. PATCH `/api/tasks/{id}` to mark `status: "done"`.
