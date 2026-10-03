from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from .paths import DEFAULT_SETTINGS_PATH, SETTINGS_PATH, ensure_dirs

SECRET_KEYS = (("typesafe", "apiKey"), ("azureOpenAI", "apiKey"))


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in override.items():
        if key in {"apiKeySet"}:
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_settings() -> dict[str, Any]:
    ensure_dirs()
    defaults = json.loads(DEFAULT_SETTINGS_PATH.read_text(encoding="utf-8"))
    if SETTINGS_PATH.exists():
        current = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return _deep_merge(defaults, current)
    SETTINGS_PATH.write_text(json.dumps(defaults, indent=2), encoding="utf-8")
    return defaults


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    current = load_settings()
    incoming = deepcopy(settings)
    for section, key in SECRET_KEYS:
        block = incoming.get(section)
        if not isinstance(block, dict):
            continue
        value = str(block.get(key) or "").strip()
        if not value or value.startswith("••••") or value == "********":
            block.pop(key, None)
            if not block:
                incoming.pop(section, None)
    merged = _deep_merge(current, incoming)
    SETTINGS_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return merged


def public_settings() -> dict[str, Any]:
    data = deepcopy(load_settings())
    for section, key in SECRET_KEYS:
        block = data.get(section)
        if not isinstance(block, dict):
            continue
        present = bool(str(block.get(key) or "").strip())
        block[key] = ""
        block["apiKeySet"] = present
    return data
