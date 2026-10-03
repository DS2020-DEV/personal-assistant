from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("PA_ROOT", str(ROOT))
os.environ.setdefault("OPENCLAW_STATE_DIR", str(ROOT / ".openclaw"))
os.environ.setdefault("OPENCLAW_CONFIG_PATH", str(ROOT / ".openclaw" / "openclaw.json"))


def _extend_path() -> None:
    extras = [
        Path.home() / "AppData/Local/Programs/Ollama",
        Path(os.environ.get("APPDATA", "")) / "npm",
        Path.home() / "AppData/Local/Microsoft/WinGet/Links",
        Path("C:/Program Files/eSpeak NG"),
        Path("C:/Program Files (x86)/eSpeak NG"),
    ]
    winget_pkg = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    extras.extend(winget_pkg.glob("Gyan.FFmpeg*/ffmpeg-*/bin"))
    current = os.environ.get("PATH", "")
    parts = [str(p) for p in extras if p.exists() and str(p) not in current]
    if parts:
        os.environ["PATH"] = os.pathsep.join(parts + [current])


_extend_path()

import uvicorn
from app.config import load_settings
from app.paths import ensure_dirs


def main() -> None:
    ensure_dirs()
    settings = load_settings()
    uvicorn.run(
        "app.main:app",
        host=settings["bindHost"],
        port=int(settings["port"]),
        reload=False,
        app_dir=str(ROOT / "backend"),
    )


if __name__ == "__main__":
    main()
