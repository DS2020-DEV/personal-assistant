from __future__ import annotations

import json
import re
import subprocess
from typing import Any

from ..paths import ROOT
from .runtime import _openclaw_argv, openclaw_env, popen_flags


class OpenClawRpcError(RuntimeError):
    pass


_JSON_OBJECT = re.compile(r"\{.*\}\s*$", re.S)


def extract_json(text: str) -> Any:
    blob = (text or "").strip()
    if not blob:
        return None
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        match = _JSON_OBJECT.search(blob)
        if not match:
            return None
        return json.loads(match.group(0))


def gateway_call(method: str, params: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    argv = _openclaw_argv()
    if not argv:
        raise OpenClawRpcError("OpenClaw CLI is not installed")
    cmd = argv + ["--no-color", "gateway", "call", method, "--json"]
    if params:
        cmd += ["--params", json.dumps(params)]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout + 5,
        cwd=str(ROOT),
        env=openclaw_env(),
        creationflags=popen_flags(),
    )
    payload = extract_json(result.stdout) or extract_json(result.stderr)
    if isinstance(payload, dict) and payload.get("type") == "cli_error":
        raise OpenClawRpcError(str(payload.get("message") or payload))
    if result.returncode != 0:
        detail = ""
        if isinstance(payload, dict):
            err = payload.get("error") or payload.get("message") or payload
            detail = err if isinstance(err, str) else json.dumps(err)
        raise OpenClawRpcError(detail or (result.stderr or result.stdout or f"{method} failed").strip())
    if not isinstance(payload, dict):
        preview = (result.stdout or result.stderr or "").replace("data:image", "[image]")[:240].strip()
        raise OpenClawRpcError(preview or f"{method} returned no JSON")
    if payload.get("ok") is False:
        err = payload.get("error") or payload.get("message") or payload
        raise OpenClawRpcError(err if isinstance(err, str) else json.dumps(err))
    inner = payload.get("result")
    if isinstance(inner, dict):
        nested = inner.get("payload")
        if isinstance(nested, dict):
            return nested
        return inner
    nested = payload.get("payload")
    if isinstance(nested, dict):
        return nested
    return payload


def channels_status() -> dict[str, Any]:
    argv = _openclaw_argv()
    if not argv:
        raise OpenClawRpcError("OpenClaw CLI is not installed")
    result = subprocess.run(
        argv + ["--no-color", "channels", "status", "--json"],
        capture_output=True,
        text=True,
        timeout=25,
        cwd=str(ROOT),
        env=openclaw_env(),
        creationflags=popen_flags(),
    )
    payload = extract_json(result.stdout) or extract_json(result.stderr)
    if isinstance(payload, dict):
        return payload
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    return {"ok": result.returncode == 0, "raw": text.strip()}
