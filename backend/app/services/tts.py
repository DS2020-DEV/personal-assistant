from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path

import numpy as np
import soundfile as sf

from ..config import load_settings
from ..paths import AUDIO_DIR, ensure_dirs
from .activity import log_activity

_kokoro = None
_kokoro_lock = threading.Lock()
_kokoro_failed = False


def synthesize(text: str, stem: str) -> Path:
    ensure_dirs()
    wav_path = AUDIO_DIR / f"{stem}.wav"
    settings = load_settings()["tts"]
    engine = settings.get("engine", "kokoro")
    if engine == "kokoro" and not _kokoro_failed:
        try:
            _synthesize_kokoro(text, wav_path, settings)
            log_activity("tts", "kokoro", stem)
            return wav_path
        except Exception as exc:
            log_activity("tts", "kokoro_failed", str(exc), "warn")
    _synthesize_sapi(text, wav_path)
    log_activity("tts", "sapi_fallback", stem)
    return wav_path


def to_voice_note(wav_path: Path) -> Path:
    ogg_path = wav_path.with_suffix(".ogg")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return wav_path
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(wav_path),
        "-ac",
        "1",
        "-ar",
        "48000",
        "-c:a",
        "libopus",
        "-b:a",
        "64k",
        str(ogg_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not ogg_path.exists():
        log_activity("tts", "ffmpeg_failed", result.stderr[-400:], "warn")
        return wav_path
    return ogg_path


def _synthesize_kokoro(text: str, wav_path: Path, settings: dict) -> None:
    global _kokoro, _kokoro_failed
    with _kokoro_lock:
        if _kokoro is None:
            from kokoro import KPipeline

            _kokoro = KPipeline(lang_code=settings.get("langCode", "a"))
        chunks = []
        generator = _kokoro(
            _prepare_spoken_text(text),
            voice=settings.get("voice", "am_michael"),
            speed=float(settings.get("speed", 0.95)),
            split_pattern=r"\n+",
        )
        for _gs, _ps, audio in generator:
            chunks.append(np.asarray(audio))
        if not chunks:
            raise RuntimeError("Kokoro produced no audio")
        audio = np.concatenate(chunks)
        sf.write(str(wav_path), audio, 24000)


def _synthesize_sapi(text: str, wav_path: Path) -> None:
    import pyttsx3

    engine = pyttsx3.init()
    engine.setProperty("rate", 175)
    engine.save_to_file(_prepare_spoken_text(text), str(wav_path))
    engine.runAndWait()
    if not wav_path.exists():
        raise RuntimeError("Windows SAPI did not write audio")


def _prepare_spoken_text(text: str) -> str:
    cleaned = text.replace("*", "").replace("#", "").replace("`", "")
    cleaned = cleaned.replace(" - ", ". ")
    return cleaned.strip()


def unload() -> None:
    global _kokoro
    with _kokoro_lock:
        _kokoro = None
