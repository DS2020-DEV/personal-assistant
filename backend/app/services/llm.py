from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import httpx

from ..config import load_settings
from .activity import log_activity


class LLMError(RuntimeError):
    pass


def model_name() -> str:
    return load_settings()["model"]["name"]


def azure_configured() -> bool:
    cfg = load_settings().get("azureOpenAI") or {}
    return bool(cfg.get("enabled") and cfg.get("endpoint") and cfg.get("apiKey") and cfg.get("deployment"))


def _options() -> dict[str, Any]:
    settings = load_settings()["model"]
    return {
        "temperature": settings.get("temperature", 0.4),
        "num_ctx": settings.get("numCtx", 8192),
    }


def chat(
    messages: list[dict[str, Any]],
    *,
    json_mode: bool = False,
    temperature: float | None = None,
    use_azure: bool = False,
) -> str:
    if use_azure and azure_configured():
        return _azure_chat(messages, json_mode=json_mode, temperature=temperature)
    return _ollama_chat(messages, json_mode=json_mode, temperature=temperature)


def generate(
    messages: list[dict[str, Any]],
    *,
    json_mode: bool = False,
    temperature: float | None = None,
    intelligence: str = "local",
) -> str:
    """local = Qwen on 8GB GPU. premium = Azure OpenAI when configured."""
    use_azure = intelligence in {"premium", "azure"} and azure_configured()
    return chat(messages, json_mode=json_mode, temperature=temperature, use_azure=use_azure)


def chat_json(
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    *,
    intelligence: str = "local",
) -> dict[str, Any]:
    raw = generate(messages, json_mode=True, temperature=temperature, intelligence=intelligence)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            raise LLMError(f"Model did not return JSON: {raw[:400]}")
        return json.loads(match.group(0))


def describe_image(image_path: str | Path, question: str = "Describe what is on screen. Be concrete.") -> str:
    path = Path(image_path)
    if not path.exists():
        raise LLMError(f"Screenshot not found: {path}")
    if azure_configured():
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ]
        return _azure_chat(messages, temperature=0.2)
    vision = (load_settings().get("model") or {}).get("visionName") or "qwen2.5vl:7b"
    if ollama_has(vision):
        return _ollama_chat(
            [
                {
                    "role": "user",
                    "content": question,
                    "images": [base64.b64encode(path.read_bytes()).decode("ascii")],
                }
            ],
            model=vision,
            temperature=0.2,
        )
    return (
        f"Screenshot saved at {path}. No Azure OpenAI vision and no local vision model "
        f"({vision}) is loaded. Add Azure credentials or `ollama pull qwen2.5vl:7b` (unload the text model first on 8GB)."
    )


def _ollama_chat(
    messages: list[dict[str, Any]],
    *,
    json_mode: bool = False,
    temperature: float | None = None,
    model: str | None = None,
) -> str:
    settings = load_settings()
    url = settings["model"]["baseUrl"].rstrip("/") + "/api/chat"
    options = _options()
    if temperature is not None:
        options["temperature"] = temperature
    payload: dict[str, Any] = {
        "model": model or settings["model"]["name"],
        "messages": messages,
        "stream": False,
        "keep_alive": settings["model"].get("keepAlive", "24h"),
        "options": options,
    }
    if json_mode:
        payload["format"] = "json"
    try:
        with httpx.Client(timeout=180.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        log_activity("llm", "chat_failed", str(exc), "error")
        raise LLMError(f"Ollama chat failed: {exc}") from exc
    text = (data.get("message") or {}).get("content") or ""
    return text.strip()


def _azure_chat(
    messages: list[dict[str, Any]],
    *,
    json_mode: bool = False,
    temperature: float | None = None,
) -> str:
    cfg = load_settings()["azureOpenAI"]
    endpoint = str(cfg["endpoint"]).rstrip("/")
    deployment = cfg["deployment"]
    api_version = cfg.get("apiVersion") or "2024-10-21"
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    payload: dict[str, Any] = {
        "messages": messages,
        "temperature": 0.2 if temperature is None else temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                url,
                json=payload,
                headers={"api-key": cfg["apiKey"], "Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        log_activity("azure", "chat_failed", str(exc), "error")
        raise LLMError(f"Azure OpenAI failed: {exc}") from exc
    choice = (data.get("choices") or [{}])[0]
    text = ((choice.get("message") or {}).get("content")) or ""
    log_activity("azure", "chat", deployment)
    return text.strip()


def ollama_running() -> bool:
    settings = load_settings()
    url = settings["model"]["baseUrl"].rstrip("/") + "/api/tags"
    try:
        with httpx.Client(timeout=0.4) as client:
            return client.get(url).status_code == 200
    except Exception:
        return False


def ollama_has(name: str) -> bool:
    settings = load_settings()
    url = settings["model"]["baseUrl"].rstrip("/") + "/api/tags"
    try:
        with httpx.Client(timeout=2.0) as client:
            data = client.get(url).json()
        names = [item.get("name") or item.get("model") for item in data.get("models", [])]
        return any(name in (n or "") or (n or "").startswith(name.split(":")[0]) for n in names)
    except Exception:
        return False


def model_loaded() -> bool:
    settings = load_settings()
    url = settings["model"]["baseUrl"].rstrip("/") + "/api/ps"
    try:
        with httpx.Client(timeout=0.4) as client:
            data = client.get(url).json()
            names = [item.get("name") or item.get("model") for item in data.get("models", [])]
            return settings["model"]["name"] in names
    except Exception:
        return False


def unload_model() -> None:
    settings = load_settings()
    url = settings["model"]["baseUrl"].rstrip("/") + "/api/generate"
    try:
        with httpx.Client(timeout=10.0) as client:
            client.post(url, json={"model": settings["model"]["name"], "keep_alive": 0})
    except Exception:
        pass
