from __future__ import annotations

import threading
from pathlib import Path

from ..config import load_settings
from .activity import log_activity

_model = None
_lock = threading.Lock()


def transcribe(audio_path: str | Path) -> str:
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(path)
    settings = load_settings()["stt"]
    with _lock:
        model = _load(settings)
        segments, info = model.transcribe(str(path), beam_size=1, vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments).strip()
    log_activity("stt", "transcribed", f"{path.name} ({info.language})")
    return text


def _load(settings: dict):
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(
            settings.get("model", "base.en"),
            device=settings.get("device", "cpu"),
            compute_type=settings.get("computeType", "int8"),
        )
        log_activity("stt", "model_loaded", settings.get("model", "base.en"))
    return _model


def unload() -> None:
    global _model
    with _lock:
        _model = None
