from pathlib import Path
import os

ROOT = Path(os.environ.get("PA_ROOT", Path(__file__).resolve().parents[2]))
DATA_DIR = ROOT / "data"
AUDIO_DIR = DATA_DIR / "audio"
LEARNING_DIR = DATA_DIR / "learning"
MEETINGS_DIR = DATA_DIR / "meetings"
NOTES_DIR = DATA_DIR / "notes"
SCREEN_DIR = DATA_DIR / "screens"
OUTBOX_DIR = DATA_DIR / "outbox"
LOG_DIR = DATA_DIR / "logs"
SETTINGS_PATH = DATA_DIR / "settings.json"
DEFAULT_SETTINGS_PATH = ROOT / "config" / "settings.default.json"
DB_PATH = DATA_DIR / "assistant.db"
RUNTIME_PATH = DATA_DIR / "runtime.json"
OPENCLAW_DIR = ROOT / ".openclaw"
DASHBOARD_DIST = ROOT / "dashboard" / "dist"


def ensure_dirs() -> None:
    for path in (DATA_DIR, AUDIO_DIR, LEARNING_DIR, MEETINGS_DIR, NOTES_DIR, SCREEN_DIR, OUTBOX_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)
