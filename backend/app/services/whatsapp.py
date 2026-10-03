from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from ..config import load_settings
from ..paths import AUDIO_DIR, OPENCLAW_DIR, OUTBOX_DIR, ensure_dirs
from .activity import log_activity
from .openclaw_rpc import OpenClawRpcError, channels_status, gateway_call

_lock = threading.Lock()
_wait_thread: threading.Thread | None = None
_status_thread: threading.Thread | None = None
_status_cache: tuple[float, dict[str, Any]] = (0.0, {})
_pairing: dict[str, Any] = {
    "active": False,
    "linked": False,
    "connected": False,
    "qrDataUrl": None,
    "sessionKey": None,
    "message": "",
    "error": None,
}


def send_whatsapp(text: str = "", media: Path | None = None) -> dict:
    lowered = (text or "").lower()
    if any(
        marker in lowered
        for marker in (
            "context compaction",
            "auto-compaction could not recover",
            "use /compact",
            "context limit exceeded",
        )
    ):
        text = "Message received. I'm processing that locally."
    settings = load_settings()["whatsapp"]
    target = (settings.get("target") or "").strip()
    ensure_dirs()
    if not target or not settings.get("enabled"):
        queued = _queue(text, media)
        log_activity("whatsapp", "queued", f"No WhatsApp target configured. Saved {queued}")
        return {"ok": False, "queued": str(queued), "reason": "WhatsApp target not configured"}

    cmd = ["openclaw", "message", "send", "--channel", "whatsapp", "--target", target]
    if text:
        cmd += ["--message", text]
    if media and media.exists():
        cmd += ["--media", str(media)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            queued = _queue(text, media)
            log_activity("whatsapp", "send_failed", result.stderr or result.stdout, "error")
            return {"ok": False, "queued": str(queued), "stderr": result.stderr}
        log_activity("whatsapp", "sent", text[:180] or str(media))
        return {"ok": True, "stdout": result.stdout}
    except FileNotFoundError:
        queued = _queue(text, media)
        log_activity("whatsapp", "openclaw_missing", "openclaw CLI not on PATH", "warn")
        return {"ok": False, "queued": str(queued), "reason": "openclaw not installed"}
    except Exception as exc:
        queued = _queue(text, media)
        log_activity("whatsapp", "send_failed", str(exc), "error")
        return {"ok": False, "queued": str(queued), "reason": str(exc)}


def notify_desktop(title: str, body: str) -> None:
    if not load_settings().get("desktopNotifications"):
        return
    try:
        from win10toast import ToastNotifier

        ToastNotifier().show_toast(title, body, duration=8, threaded=True)
    except Exception:
        try:
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    (
                        "New-BurntToastNotification -Text "
                        f"'{title.replace(chr(39), '')}', '{body.replace(chr(39), '')}'"
                    ),
                ],
                capture_output=True,
                timeout=10,
            )
        except Exception:
            pass


def _queue(text: str, media: Path | None) -> Path:
    from datetime import datetime

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = OUTBOX_DIR / stamp
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "message.json").write_text(
        json.dumps({"text": text, "media": str(media) if media else None}, indent=2),
        encoding="utf-8",
    )
    if media and media.exists():
        shutil.copy2(media, folder / media.name)
    return folder


def _channel_flags(payload: Any) -> dict[str, bool]:
    text = json.dumps(payload).lower() if not isinstance(payload, str) else payload.lower()
    return {
        "linked": "linked" in text and "unlinked" not in text,
        "connected": "connected" in text or "listening" in text,
        "healthy": "healthy" in text or '"connected": true' in text,
    }


def _creds_linked() -> bool:
    return (OPENCLAW_DIR / "credentials" / "whatsapp" / "default" / "creds.json").is_file()


def _refresh_channel_status() -> dict[str, Any]:
    global _status_cache
    now = time.time()
    if now - _status_cache[0] < 15 and _status_cache[1]:
        return _status_cache[1]
    try:
        raw = channels_status()
        flags = _channel_flags(raw)
        data = {
            "linked": flags["linked"] or flags["connected"] or _creds_linked(),
            "connected": flags["connected"],
        }
    except Exception as exc:
        data = {"linked": _creds_linked(), "connected": False, "error": str(exc)}
    _status_cache = (now, data)
    return data


def _status_loop() -> None:
    while True:
        try:
            _refresh_channel_status()
        except Exception:
            pass
        time.sleep(12)


def ensure_status_thread() -> None:
    global _status_thread
    if _status_thread and _status_thread.is_alive():
        return
    _status_thread = threading.Thread(target=_status_loop, daemon=True, name="whatsapp-status")
    _status_thread.start()


def pairing_snapshot() -> dict[str, Any]:
    ensure_status_thread()
    channel = _status_cache[1] if _status_cache[0] else {"linked": _creds_linked(), "connected": False}
    with _lock:
        snap = dict(_pairing)
    snap["linked"] = bool(channel.get("linked") or snap.get("connected") or snap.get("linked") or _creds_linked())
    snap["channelConnected"] = bool(channel.get("connected"))
    snap["ok"] = True
    return snap


def start_pairing_qr(*, force: bool = False) -> dict[str, Any]:
    from .runtime import ensure_openclaw

    ensure_status_thread()
    snap = pairing_snapshot()
    if snap.get("channelConnected") and not force:
        snap["message"] = "WhatsApp is already linked and connected. Use Relink only if you need a new QR."
        snap["error"] = None
        snap["qrDataUrl"] = None
        return snap

    ensure_openclaw()
    with _lock:
        _pairing.update(
            {
                "active": True,
                "message": "Starting WhatsApp login…",
                "error": None,
                "qrDataUrl": None if force else _pairing.get("qrDataUrl"),
            }
        )
    threading.Thread(target=_run_login, kwargs={"force": force}, daemon=True, name="whatsapp-qr-login").start()
    return pairing_snapshot()


def _run_login(*, force: bool = False) -> None:
    from .runtime import ensure_openclaw

    log_activity("whatsapp", "qr_login_start", "force" if force else "link")
    try:
        result = _login_start(force)
    except OpenClawRpcError as exc:
        text = str(exc)
        if "ECONNREFUSED" in text or "not reachable" in text.lower():
            time.sleep(2)
            try:
                ensure_openclaw()
                result = _login_start(force)
            except Exception as retry_exc:
                _qr_fail(str(retry_exc))
                return
        else:
            _qr_fail(text)
            return

    qr = result.get("qrDataUrl")
    message = str(result.get("message") or "")
    already = "already linked" in message.lower()
    connected = bool(result.get("connected") or already)
    with _lock:
        _pairing.update(
            {
                "active": bool(qr) and not connected,
                "connected": connected,
                "linked": connected or already or _pairing.get("linked"),
                "qrDataUrl": None if already else qr,
                "sessionKey": result.get("sessionKey"),
                "message": message or ("Linked." if connected else "Scan this QR in WhatsApp → Linked devices."),
                "error": None,
            }
        )
    if qr and not connected:
        _ensure_wait_loop()
    elif connected:
        global _status_cache
        _status_cache = (0.0, {})
        log_activity("whatsapp", "qr_already_linked", result.get("message") or "connected")


def _login_start(force: bool) -> dict[str, Any]:
    return gateway_call(
        "web.login.start",
        {"channel": "whatsapp", "force": force, "timeoutMs": 45000},
        timeout=55,
    )


def _qr_fail(detail: str) -> dict[str, Any]:
    with _lock:
        _pairing["active"] = False
        _pairing["error"] = detail
        _pairing["message"] = detail
    log_activity("whatsapp", "qr_login_failed", detail, "error")
    snap = pairing_snapshot()
    snap["ok"] = False
    snap["error"] = detail
    return snap


def _ensure_wait_loop() -> None:
    global _wait_thread
    if _wait_thread and _wait_thread.is_alive():
        return
    _wait_thread = threading.Thread(target=_wait_loop, daemon=True, name="whatsapp-qr-wait")
    _wait_thread.start()


def _wait_loop() -> None:
    while True:
        with _lock:
            if not _pairing.get("active") or _pairing.get("connected"):
                return
            params = {
                "channel": "whatsapp",
                "timeoutMs": 12000,
            }
            if _pairing.get("sessionKey"):
                params["sessionKey"] = _pairing["sessionKey"]
            if _pairing.get("qrDataUrl"):
                params["currentQrDataUrl"] = _pairing["qrDataUrl"]
        try:
            result = gateway_call("web.login.wait", params, timeout=25)
        except Exception as exc:
            with _lock:
                _pairing["error"] = str(exc)
                _pairing["message"] = str(exc)
                _pairing["active"] = False
            log_activity("whatsapp", "qr_wait_failed", str(exc), "warn")
            return
        qr = result.get("qrDataUrl")
        connected = bool(result.get("connected"))
        with _lock:
            if qr:
                _pairing["qrDataUrl"] = qr
            _pairing["connected"] = connected
            _pairing["message"] = result.get("message") or _pairing.get("message")
            if connected:
                _pairing["active"] = False
                _pairing["linked"] = True
                _pairing["qrDataUrl"] = None
        if connected:
            global _status_cache
            _status_cache = (0.0, {})
            log_activity("whatsapp", "qr_linked", "WhatsApp linked from dashboard")
            return
        time.sleep(0.4)
