from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from ..config import load_settings
from ..paths import OPENCLAW_DIR, ROOT, RUNTIME_PATH, ensure_dirs
from .activity import log_activity
from .llm import model_loaded, ollama_running, unload_model

_openclaw_proc: subprocess.Popen | None = None
assistants_enabled = False
_autostart_cache: tuple[float, bool] = (0.0, False)


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


def _runtime() -> dict[str, Any]:
    if RUNTIME_PATH.exists():
        try:
            return json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_runtime(data: dict[str, Any]) -> None:
    ensure_dirs()
    RUNTIME_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _which_ollama() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    home = Path.home()
    candidates = [
        home / "AppData/Local/Programs/Ollama/ollama.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe",
        Path("C:/Program Files/Ollama/ollama.exe"),
        Path("C:/Program Files (x86)/Ollama/ollama.exe"),
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def _which_openclaw() -> str | None:
    cmd = _openclaw_argv()
    return cmd[0] if cmd else None


def _openclaw_argv() -> list[str] | None:
    node = shutil.which("node")
    mjs = Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "openclaw" / "openclaw.mjs"
    if node and mjs.is_file():
        return [node, str(mjs)]
    cmd = Path(os.environ.get("APPDATA", "")) / "npm" / "openclaw.cmd"
    if cmd.is_file():
        return ["cmd.exe", "/c", str(cmd)]
    found = shutil.which("openclaw")
    return [found] if found else None


def openclaw_env() -> dict[str, str]:
    env = os.environ.copy()
    env["OPENCLAW_STATE_DIR"] = str(OPENCLAW_DIR)
    env["OPENCLAW_CONFIG_PATH"] = str(OPENCLAW_DIR / "openclaw.json")
    env["NO_COLOR"] = "1"
    return env


def popen_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def ensure_openclaw() -> None:
    _start_openclaw()


def windows_autostart_enabled() -> bool:
    global _autostart_cache
    now = time.time()
    if now - _autostart_cache[0] < 300:
        return _autostart_cache[1]
    startup = (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft/Windows/Start Menu/Programs/Startup/PersonalAssistantLocal.cmd"
    )
    if startup.is_file():
        _autostart_cache = (now, True)
        return True
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", "Get-ScheduledTask -TaskName PersonalAssistantLocal -ErrorAction SilentlyContinue | Select-Object -ExpandProperty TaskName"],
        capture_output=True,
        text=True,
        timeout=4,
        creationflags=popen_flags(),
    )
    enabled = "PersonalAssistantLocal" in (result.stdout or "")
    _autostart_cache = (now, enabled)
    return enabled


def set_windows_autostart(enabled: bool) -> dict[str, Any]:
    script = ROOT / "scripts" / ("install-autostart.ps1" if enabled else "uninstall-autostart.ps1")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True,
        text=True,
        timeout=40,
        cwd=str(ROOT),
        creationflags=popen_flags(),
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "autostart script failed").strip()
        raise RuntimeError(detail)
    global _autostart_cache
    _autostart_cache = (0.0, False)
    from ..config import load_settings, save_settings

    settings = load_settings()
    settings.setdefault("autostart", {})["windows"] = enabled
    save_settings(settings)
    log_activity("system", "autostart_windows", "enabled" if enabled else "disabled")
    return {
        "ok": True,
        "enabled": windows_autostart_enabled(),
        "detail": (result.stdout or "").strip(),
    }


def status() -> dict[str, Any]:
    settings = load_settings()
    rt = _runtime()
    ollama = _which_ollama()
    openclaw = _which_openclaw()
    missing: list[str] = []
    if not ollama:
        missing.append("ollama")
    if not openclaw:
        missing.append("openclaw")
    payload = {
        "ok": assistants_enabled and ollama_running(),
        "assistants": assistants_enabled,
        "ollama": ollama_running(),
        "ollamaBinary": ollama,
        "modelLoaded": model_loaded(),
        "model": settings["model"]["name"],
        "openclaw": _openclaw_running(rt),
        "openclawBinary": openclaw,
        "whatsappConfigured": bool(settings["whatsapp"].get("target")),
        "whatsappLinked": (OPENCLAW_DIR / "credentials" / "whatsapp" / "default" / "creds.json").is_file(),
        "jevConfigured": bool((settings.get("typesafe") or {}).get("enabled") and (settings.get("typesafe") or {}).get("apiKey")),
        "azureConfigured": bool((settings.get("azureOpenAI") or {}).get("enabled") and (settings.get("azureOpenAI") or {}).get("apiKey")),
        "autostartWindows": windows_autostart_enabled(),
        "bind": f"{settings['bindHost']}:{settings['port']}",
        "gpuHint": "Jev routes WhatsApp. Qwen 7B on 8GB GPU writes notes. Azure OpenAI only for hard chat + screen vision.",
        "missing": missing,
        "error": None,
        "nextStep": (
            'In PowerShell: cd "D:\\Personal assistant"; powershell -ExecutionPolicy Bypass -File scripts\\bootstrap.ps1'
            if missing
            else None
        ),
    }
    return payload


def start_assistants() -> dict[str, Any]:
    global assistants_enabled
    errors: list[str] = []
    try:
        _ensure_ollama()
    except Exception as exc:
        errors.append(str(exc))
        log_activity("system", "start_ollama_failed", str(exc), "error")
    if ollama_running():
        try:
            _ensure_model()
        except Exception as exc:
            errors.append(f"Model load failed: {exc}")
            log_activity("system", "start_model_failed", str(exc), "error")
    try:
        _start_openclaw()
    except Exception as exc:
        errors.append(str(exc))
        log_activity("system", "start_openclaw_failed", str(exc), "error")

    assistants_enabled = ollama_running()
    result = status()
    result["ok"] = assistants_enabled
    result["error"] = " ".join(errors) if errors else None
    if assistants_enabled:
        log_activity("system", "assistants_started", "Ollama ready")
    elif errors:
        log_activity("system", "start_blocked", result["error"] or "", "warn")
    return result


def stop_assistants() -> dict[str, Any]:
    global assistants_enabled, _openclaw_proc
    assistants_enabled = False
    _stop_openclaw()
    unload_model()
    try:
        from . import stt, tts

        tts.unload()
        stt.unload()
    except Exception:
        pass
    log_activity("system", "assistants_stopped", "GPU model unloaded")
    result = status()
    result["ok"] = True
    return result


def _ensure_ollama() -> None:
    if ollama_running():
        return
    ollama = _which_ollama()
    if not ollama:
        raise RuntimeError(
            "Ollama is not installed, so Start cannot load Qwen. "
            'Run: powershell -ExecutionPolicy Bypass -File scripts\\bootstrap.ps1'
        )
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen([ollama, "serve"], cwd=str(ROOT), creationflags=flags)
    rt = _runtime()
    rt["ollamaPid"] = proc.pid
    _save_runtime(rt)
    log_activity("system", "ollama_spawned", str(proc.pid))
    for _ in range(20):
        if ollama_running():
            return
        time.sleep(0.5)
    raise RuntimeError("Ollama started but is not answering on http://127.0.0.1:11434 yet. Try Start again in a few seconds.")


def _ensure_model() -> None:
    settings = load_settings()
    name = settings["model"]["name"]
    url = settings["model"]["baseUrl"].rstrip("/")
    with httpx.Client(timeout=30.0) as client:
        tags = client.get(url + "/api/tags").json()
        have = {m.get("name") for m in tags.get("models", [])}
        if name not in have and f"{name}:latest" not in have:
            log_activity("system", "pulling_model", name)
            ollama = _which_ollama()
            if ollama:
                subprocess.run([ollama, "pull", name], check=False, cwd=str(ROOT))
        client.post(
            url + "/api/generate",
            json={"model": name, "prompt": "ok", "stream": False, "keep_alive": settings["model"].get("keepAlive", "24h")},
            timeout=180.0,
        )


def _start_openclaw() -> None:
    global _openclaw_proc
    if _gateway_listening():
        return
    if _openclaw_proc and _openclaw_proc.poll() is None:
        _wait_for_gateway()
        return
    argv = _openclaw_argv()
    if not argv:
        log_activity("system", "openclaw_missing", "Install with scripts/bootstrap.ps1", "warn")
        raise RuntimeError(
            "OpenClaw CLI is not installed (needed for WhatsApp). "
            "Dashboard tasks still work. Run scripts\\bootstrap.ps1 then pair WhatsApp."
        )
    env = openclaw_env()
    flags = popen_flags()
    log_path = ROOT / "data" / "logs" / "openclaw.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "a", encoding="utf-8")
    _openclaw_proc = subprocess.Popen(
        argv + ["gateway"],
        cwd=str(ROOT),
        env=env,
        creationflags=flags,
        stdout=log_file,
        stderr=log_file,
    )
    rt = _runtime()
    rt["openclawPid"] = _openclaw_proc.pid
    _save_runtime(rt)
    log_activity("system", "openclaw_started", str(_openclaw_proc.pid))
    _wait_for_gateway()


def _stop_openclaw() -> None:
    global _openclaw_proc
    rt = _runtime()
    pid = rt.get("openclawPid")
    if _openclaw_proc and _openclaw_proc.poll() is None:
        _openclaw_proc.terminate()
        _openclaw_proc = None
    elif pid:
        _kill(pid)
    rt.pop("openclawPid", None)
    _save_runtime(rt)


def _openclaw_running(_rt: dict[str, Any] | None = None) -> bool:
    return _gateway_listening()


def _gateway_listening() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 18789), timeout=0.4):
            return True
    except OSError:
        return False


def _wait_for_gateway(seconds: float = 25.0) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if _gateway_listening():
            return
        if _openclaw_proc and _openclaw_proc.poll() is not None:
            break
        time.sleep(0.4)
    if not _gateway_listening():
        raise RuntimeError(
            "OpenClaw gateway started but is not listening on ws://127.0.0.1:18789 yet. "
            "Wait a few seconds and press Show pairing QR again."
        )


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _kill(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.kill(int(pid), 15)
        except OSError:
            pass
