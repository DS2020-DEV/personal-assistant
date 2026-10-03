from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..config import load_settings


def strip_prefix(text: str, prefixes: list[str]) -> str:
    lower = (text or "").strip()
    for prefix in prefixes:
        if lower.lower().startswith(prefix.lower()):
            return lower[len(prefix) :].strip(" :-")
    return lower[:400]


def extract_fields(text: str, intent: str) -> dict[str, Any]:
    raw = (text or "").strip()
    extracted: dict[str, Any] = {"title": raw[:120], "details": raw}

    if intent == "task":
        extracted["title"] = strip_prefix(raw, ["add task", "create task", "new task", "todo", "task:"])[:400]
    elif intent in {"reminder", "meeting"}:
        extracted["title"] = strip_prefix(raw, ["remind me to", "remind me", "reminder:", "set a reminder"])[:120]
        extracted["when"] = _guess_when(raw)
    elif intent in {"learning", "study_notes"}:
        extracted["topic"] = strip_prefix(
            raw,
            ["learn", "teach me", "research", "study", "start learning", "make a plan for", "study notes for"],
        )
    elif intent == "notes":
        extracted["title"] = strip_prefix(raw, ["note:", "save note", "take a note", "remember:"])[:120]
        extracted["body"] = strip_prefix(raw, ["note:", "save note", "take a note", "remember:"])
    elif intent == "computer_use":
        extracted["prompt"] = _cursor_prompt(raw)
        extracted["app"] = _app_name(raw)
        extracted["goal"] = raw
    return extracted


def _guess_when(text: str) -> str | None:
    if re.search(r"\bevery day\b|\bdaily\b", text, re.I):
        return "every day"
    parsed = parse_local_datetime(text)
    if parsed:
        return parsed.isoformat()
    match = re.search(r"\b(in \d+\s+(minutes?|hours?|days?))\b", text, re.I)
    return match.group(1) if match else None


def parse_local_datetime(text: str) -> datetime | None:
    raw = (text or "").strip()
    if not raw:
        return None
    from ..config import load_settings

    tz = ZoneInfo(load_settings().get("timezone", "Asia/Kolkata"))
    now = datetime.now(tz)
    relative = re.search(r"\bin\s+(\d+)\s+(minutes?|hours?|days?)\b", raw, re.I)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2).lower()
        delta = timedelta(minutes=amount) if unit.startswith("minute") else timedelta(hours=amount) if unit.startswith("hour") else timedelta(days=amount)
        return now + delta
    match = re.search(
        r"\b(?:at|@)\s*(\d{1,2})(?:[.:](\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?\b",
        raw,
        re.I,
    ) or re.search(r"\b(\d{1,2})[.:](\d{2})\s*(a\.?m\.?|p\.?m\.?)?\b", raw, re.I)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = (match.group(3) or "").lower().replace(".", "")
    if hour > 23 or minute > 59:
        return None
    if meridiem.startswith("p") and hour < 12:
        hour += 12
    elif meridiem.startswith("a") and hour == 12:
        hour = 0
    elif not meridiem and hour <= 6:
        hour += 12
    run_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if run_at <= now:
        run_at += timedelta(days=1)
    return run_at


def _cursor_prompt(text: str) -> str:
    patterns = [
        r"(?:cursor|composer|agent chat).{0,40}(?:prompt|write|type|paste)\s*[:\-]\s*(.+)$",
        r"(?:write|type|paste)\s+(?:this\s+)?(?:prompt\s+)?(?:in|into)\s+cursor.{0,20}[:\-]?\s*(.+)$",
        r"(?:open cursor and ).{0,40}[:\-]\s*(.+)$",
        r"prompt\s*[:\-]\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.S)
        if match and match.group(1).strip():
            return match.group(1).strip()
    cleaned = re.sub(r"open cursor( and)?", "", text, flags=re.I).strip()
    return cleaned or text


def _app_name(text: str) -> str:
    lower = text.lower()
    if "cursor" in lower:
        return "cursor"
    if "notepad" in lower:
        return "notepad"
    if "chrome" in lower or "browser" in lower:
        return "chrome"
    return "desktop"
