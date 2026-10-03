from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import load_settings
from ..db import ComputerJob, SessionLocal
from ..paths import SCREEN_DIR
from .activity import log_activity
from .llm import describe_image

_lock = threading.Lock()

BLOCKED = re.compile(
    r"\b(password|passwd|credential|api[_-]?key|secret|sudo|format\s+c:|regedit|rm\s+-rf|"
    r"powershell\s+-enc|mimikatz|keylog|bank login|otp)\b",
    re.I,
)


def run_computer_job(text: str, extracted: dict[str, Any] | None = None, desktop_action: str | None = None) -> dict[str, Any]:
    extracted = extracted or {}
    if BLOCKED.search(text or ""):
        return {
            "ok": False,
            "reply": "I will not type secrets or run destructive commands from WhatsApp.",
        }
    if not (load_settings().get("computer") or {}).get("enabled", True):
        return {"ok": False, "reply": "Computer use is disabled in Settings."}

    action = desktop_action or extracted.get("desktop_action") or _infer_action(text)
    prompt = (extracted.get("prompt") or "").strip()
    app = (extracted.get("app") or "cursor").lower()

    with _lock:
        job = _record(action, text, "running")
        try:
            if action == "refuse":
                result = {"ok": False, "reply": "That desktop request is outside the allowlist."}
            elif action == "screenshot_describe":
                result = _screenshot_and_describe(text)
            elif action == "open_cursor_chat":
                result = _open_cursor_and_type(prompt or text)
            elif action == "open_app":
                result = _open_app(app)
                if result.get("ok"):
                    shot = _screenshot_and_describe(f"After opening {app}. {text}")
                    result["reply"] = f"{result['reply']}\n\n{shot.get('reply', '')}"
                    result["screenshot"] = shot.get("screenshot")
            else:
                result = _screenshot_and_describe(text)
            _finish(job.id, "ok" if result.get("ok") else "error", result.get("reply", ""), result.get("screenshot"))
            result["job_id"] = job.id
            return result
        except Exception as exc:
            _finish(job.id, "error", str(exc), None)
            log_activity("computer", "failed", str(exc), "error")
            return {"ok": False, "reply": f"Computer use failed: {exc}", "job_id": job.id}


def _infer_action(text: str) -> str:
    lower = (text or "").lower()
    if "cursor" in lower:
        return "open_cursor_chat"
    if any(word in lower for word in ("screenshot", "what do you see", "what's on", "on screen", "on my screen")):
        return "screenshot_describe"
    if "open" in lower:
        return "open_app"
    return "screenshot_describe"


def _open_cursor_and_type(prompt: str) -> dict[str, Any]:
    exe = _cursor_exe()
    if not exe:
        return {"ok": False, "reply": "Could not find Cursor.exe. Install Cursor or set computer.cursorPath in Settings."}
    subprocess.Popen([str(exe)], cwd=str(exe.parent))
    time.sleep(2.5)
    _focus_title("cursor")
    time.sleep(0.4)
    pyautogui = _pyautogui()
    pyautogui.hotkey("ctrl", "l")
    time.sleep(0.6)
    clean = _sanitize_typed(prompt)
    if clean:
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.write(clean[:4000], interval=0.015)
        send = bool((load_settings().get("computer") or {}).get("sendCursorPrompt", True))
        if send:
            time.sleep(0.2)
            pyautogui.press("enter")
    shot = _screenshot_and_describe("Describe the Cursor window after typing the user's prompt. Say whether the chat box is visible.")
    typed = clean[:240] + ("…" if len(clean) > 240 else "")
    reply = (
        f"Opened Cursor and {'sent' if (load_settings().get('computer') or {}).get('sendCursorPrompt', True) else 'typed'} this prompt:\n{typed}\n\n"
        f"{shot.get('reply', '')}"
    )
    log_activity("computer", "cursor_chat", typed)
    return {"ok": True, "reply": reply, "screenshot": shot.get("screenshot")}


def _open_app(name: str) -> dict[str, Any]:
    name = (name or "").lower()
    if name == "cursor":
        exe = _cursor_exe()
        if not exe:
            return {"ok": False, "reply": "Cursor.exe not found."}
        subprocess.Popen([str(exe)])
        time.sleep(2)
        _focus_title("cursor")
        return {"ok": True, "reply": "Opened Cursor."}
    if name == "notepad":
        subprocess.Popen(["notepad.exe"])
        time.sleep(0.8)
        return {"ok": True, "reply": "Opened Notepad."}
    if name == "chrome":
        chrome = (
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"
        )
        if not chrome.exists():
            return {"ok": False, "reply": "Chrome not found."}
        subprocess.Popen([str(chrome)])
        time.sleep(1.2)
        return {"ok": True, "reply": "Opened Chrome."}
    return {"ok": False, "reply": f"{name} is not on the allowlist (cursor, notepad, chrome)."}


def _screenshot_and_describe(question: str) -> dict[str, Any]:
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = SCREEN_DIR / f"screen-{stamp}.png"
    image = _pyautogui().screenshot()
    image.save(path)
    description = describe_image(
        path,
        question=(
            "You are looking at the user's Windows desktop screenshot. "
            "Describe the visible windows, the focused app, and any text that matters. "
            "Be specific about Cursor chat if it is open. "
            f"User request: {question[:800]}"
        ),
    )
    log_activity("computer", "screenshot", str(path))
    return {"ok": True, "reply": description, "screenshot": str(path)}


def _cursor_exe() -> Path | None:
    configured = (load_settings().get("computer") or {}).get("cursorPath")
    if configured and Path(configured).is_file():
        return Path(configured)
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    candidates = [
        local / "Programs/cursor/Cursor.exe",
        local / "Programs/Cursor/Cursor.exe",
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "cursor/Cursor.exe",
    ]
    which = shutil.which("cursor")
    if which:
        candidates.insert(0, Path(which))
    for path in candidates:
        if path.is_file():
            return path
    return None


def _focus_title(needle: str) -> None:
    try:
        import ctypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def enum_proc(hwnd, _lparam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length < 1:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if needle.lower() in buf.value.lower() and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True

        user32.EnumWindows(enum_proc, 0)
        if found:
            hwnd = found[0]
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def _sanitize_typed(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = BLOCKED.sub("[blocked]", cleaned)
    cleaned = cleaned.replace("\r", " ").replace("\t", " ")
    return cleaned[:4000]


def _pyautogui():
    import pyautogui

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.08
    return pyautogui


def _record(action: str, request: str, status: str) -> ComputerJob:
    db = SessionLocal()
    try:
        job = ComputerJob(action=action, request=request[:4000], status=status)
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    finally:
        db.close()


def _finish(job_id: int, status: str, result: str, screenshot: str | None) -> None:
    db = SessionLocal()
    try:
        job = db.get(ComputerJob, job_id)
        if not job:
            return
        job.status = status
        job.result = (result or "")[:8000]
        job.screenshot_path = screenshot or ""
        db.commit()
    finally:
        db.close()
