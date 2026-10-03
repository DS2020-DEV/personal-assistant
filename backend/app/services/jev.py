from __future__ import annotations

from typing import Any

import httpx

from ..config import load_settings
from .activity import log_activity


class JevError(RuntimeError):
    pass


def jev_configured() -> bool:
    cfg = load_settings().get("typesafe") or {}
    return bool(cfg.get("enabled") and (cfg.get("apiKey") or "").strip())


def evaluate(state: Any, questions: dict[str, Any]) -> dict[str, Any]:
    """Call TypeSafe Jev (System One). Returns answers keyed by question id."""
    cfg = load_settings().get("typesafe") or {}
    key = (cfg.get("apiKey") or "").strip()
    if not cfg.get("enabled") or not key:
        raise JevError("TypeSafe Jev is not configured")
    url = (cfg.get("baseUrl") or "https://api.typesafe.ai").rstrip("/") + "/v1/systemone"
    payload = {
        "model": cfg.get("model") or "jev-latest",
        "state": state,
        "questions": questions,
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        log_activity("jev", "evaluate_failed", str(exc), "error")
        raise JevError(str(exc)) from exc
    log_activity("jev", "evaluated", ",".join(questions.keys()))
    return data


def choice(answers: dict[str, Any], key: str, default: str = "") -> tuple[str, float, dict[str, float]]:
    item = (answers.get("answers") or answers).get(key) or {}
    if item.get("type") != "choice" and "choice" not in item:
        return default, 0.0, {}
    probs = item.get("probabilities") or {}
    return str(item.get("choice") or default), float(item.get("confidence") or 0), {str(k): float(v) for k, v in probs.items()}


def noul(answers: dict[str, Any], key: str) -> float:
    item = (answers.get("answers") or answers).get(key) or {}
    return float(item.get("noul") or 0)


def score(answers: dict[str, Any], key: str) -> tuple[float, float]:
    item = (answers.get("answers") or answers).get(key) or {}
    return float(item.get("score") or 0), float(item.get("confidence") or 0)
