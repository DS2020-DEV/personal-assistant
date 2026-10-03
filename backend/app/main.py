from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import load_settings
from .db import init_db
from .paths import AUDIO_DIR, DASHBOARD_DIST, LEARNING_DIR, MEETINGS_DIR, NOTES_DIR, SCREEN_DIR, ensure_dirs
from .routers import activity, computer, inbox, learning, meetings, notes, reminders, settings as settings_router
from .routers import system, tasks, whatsapp as whatsapp_router
from .services.activity import log_activity
from .services.scheduler import start_scheduler

ensure_dirs()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_dirs()
    init_db()
    start_scheduler()
    settings = load_settings()
    log_activity("system", "dashboard_up", f"http://{settings['bindHost']}:{settings['port']}")
    if settings.get("autostart", {}).get("startAssistantsOnBoot"):
        try:
            from .services.runtime import start_assistants

            start_assistants()
        except Exception as exc:
            log_activity("system", "autostart_failed", str(exc), "warn")
    yield


app = FastAPI(title="Personal Assistant", lifespan=lifespan)
cfg = load_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://127.0.0.1:{cfg['port']}",
        f"http://localhost:{cfg['port']}",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(tasks.router)
app.include_router(reminders.router)
app.include_router(learning.router)
app.include_router(meetings.router)
app.include_router(activity.router)
app.include_router(settings_router.router)
app.include_router(inbox.router)
app.include_router(whatsapp_router.router)
app.include_router(notes.router)
app.include_router(computer.router)

if AUDIO_DIR.exists():
    app.mount("/media/audio", StaticFiles(directory=AUDIO_DIR), name="audio")
if LEARNING_DIR.exists():
    app.mount("/media/learning", StaticFiles(directory=LEARNING_DIR), name="learning")
if MEETINGS_DIR.exists():
    app.mount("/media/meetings", StaticFiles(directory=MEETINGS_DIR), name="meetings")
if NOTES_DIR.exists():
    app.mount("/media/notes", StaticFiles(directory=NOTES_DIR), name="notes")
if SCREEN_DIR.exists():
    app.mount("/media/screens", StaticFiles(directory=SCREEN_DIR), name="screens")


@app.get("/api/health")
def health():
    return {"ok": True, "localOnly": True}


if DASHBOARD_DIST.exists() and (DASHBOARD_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=DASHBOARD_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = DASHBOARD_DIST / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DASHBOARD_DIST / "index.html")
else:

    @app.get("/")
    def fallback_home():
        return HTMLResponse(
            "<h1>Local assistant API is running</h1>"
            "<p>Build the UI with <code>cd dashboard && npm install && npm run build</code> "
            "or run <code>scripts\\bootstrap.ps1</code>.</p>"
        )
