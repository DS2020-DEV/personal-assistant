from __future__ import annotations

import re
from typing import Any

from .activity import log_activity
from .extract import extract_fields
from .jev import JevError, choice, evaluate, jev_configured, noul, score
from .llm import chat_json


TASK_RE = re.compile(r"\b(add|create|new)\s+(a\s+)?(task|todo)\b|\btodo\b|\btask:\s*", re.I)
REMIND_RE = re.compile(r"\bremind(er| me)?\b|\breminders?\b", re.I)
LEARN_RE = re.compile(r"\b(learn|teach me|research|lesson|curriculum|study plan|make a plan)\b", re.I)
MEETING_RE = re.compile(r"\b(meeting|standup|call notes|transcribe|recording)\b", re.I)
NOTES_RE = re.compile(r"(take a note|save note|note:|remember this|write this down)", re.I)
COMPUTER_RE = re.compile(
    r"\b(open cursor|in cursor|type in (chat|composer)|use (my )?computer|on (my )?screen|screenshot|what (do you|does it) see|click|type this)\b",
    re.I,
)

INTENTS = (
    "task",
    "reminder",
    "learning",
    "meeting",
    "meeting_audio",
    "notes",
    "study_notes",
    "computer_use",
    "chat",
)

JEV_QUESTIONS = {
    "intent": {
        "type": "choice",
        "instructions": (
            "What should the personal assistant do with this WhatsApp message? "
            "Prefer the most specific handler. computer_use means operate the user's own Windows desktop "
            "(open Cursor, type a prompt, screenshot, describe the screen). "
            "study_notes is educational material that should become a learning plan or study notes. "
            "notes is a personal note to save. meeting_audio is a voice note or recording to transcribe."
        ),
        "criteria": {
            "task": "Create or update a to-do / daily work item.",
            "reminder": "Schedule a reminder or ping at a time.",
            "learning": "Start a multi-day study plan / tutor lessons.",
            "meeting": "Meeting discussion without audio, or schedule a meeting reminder.",
            "meeting_audio": "Voice note, call recording, or audio that should become meeting notes and action items.",
            "notes": "Save a personal note, not a task or reminder.",
            "study_notes": "Turn attached or pasted study material into notes and a plan.",
            "computer_use": "Operate the PC: Cursor chat, screenshot, describe what is on screen, open an allowlisted app.",
            "chat": "Ordinary conversation or a question that does not need a specialist handler.",
        },
    },
    "complexity": {
        "type": "score",
        "instructions": "How much intelligence does fulfilling this request need?",
        "criteria": [
            "Local Qwen 7B is enough (short notes, simple chat, obvious routing).",
            "Needs a careful writeup but still local-sized.",
            "Needs a frontier / Azure OpenAI model (hard reasoning, screen understanding, high-stakes wording).",
        ],
    },
    "risk": {
        "type": "noul",
        "instructions": "Would acting on this harm the user, other people, or their machine (destructive commands, credentials, malware, bypassing accounts)?",
        "criteria": {
            "true": "Unsafe / should refuse",
            "false": "Ordinary personal-assistant request on the user's own laptop",
        },
    },
    "desktop_action": {
        "type": "choice",
        "instructions": "If this is computer use, which allowlisted desktop action fits? If it is not computer use, pick none.",
        "criteria": {
            "none": "Not a desktop-control request.",
            "screenshot_describe": "Capture the screen and describe what it shows.",
            "open_cursor_chat": "Open Cursor and type a prompt into the chat/composer.",
            "open_app": "Open a named allowlisted app (Cursor, Notepad, Chrome).",
            "refuse": "Looks like computer use but is too dangerous or unbounded (passwords, admin, files outside the user session).",
        },
    },
    "audio_kind": {
        "type": "choice",
        "instructions": "If there is audio or the message is about a recording, what kind of audio is it? If there is no audio, pick none.",
        "criteria": {
            "none": "No audio.",
            "meeting": "Work meeting, standup, or 1:1 that should produce notes and tasks.",
            "lecture": "Class, tutorial, or study recording that should produce study notes.",
            "voice_memo": "Short personal voice memo — save as a note or task list.",
        },
    },
}


def classify_inbox(text: str, media_kind: str | None) -> dict[str, Any]:
    text = (text or "").strip()
    media_kind = (media_kind or "").lower() or None
    if "<media:audio>" in text.lower() and not media_kind:
        media_kind = "audio"
    heuristic = _heuristic(text, media_kind)

    if jev_configured():
        try:
            routed = _jev_route(text, media_kind, heuristic)
            routed["extracted"] = extract_fields(text, routed["intent"])
            log_activity(
                "jev",
                "routed",
                f"{routed['intent']} conf={routed.get('confidence'):.2f} via={routed.get('router')}",
            )
            return routed
        except (JevError, Exception) as exc:
            log_activity("jev", "fallback", str(exc), "warn")

    heuristic["extracted"] = extract_fields(text, heuristic["intent"])
    if heuristic.get("router") == "heuristic" and text and heuristic["intent"] == "chat" and len(text) < 800:
        try:
            parsed = chat_json(
                [
                    {
                        "role": "system",
                        "content": (
                            "Classify a personal-assistant WhatsApp message. "
                            "Return JSON with keys intent and extracted. "
                            f"intent must be one of: {', '.join(INTENTS)}. "
                            "extracted should include title, details, topic, when, prompt if present."
                        ),
                    },
                    {"role": "user", "content": text[:1500]},
                ]
            )
            intent = str(parsed.get("intent") or "chat")
            if intent not in INTENTS:
                intent = "chat"
            parsed["intent"] = intent
            parsed["confidence"] = 0.55
            parsed["router"] = "qwen"
            parsed["extracted"] = {**extract_fields(text, intent), **(parsed.get("extracted") or {})}
            parsed["intelligence"] = "local"
            return parsed
        except Exception:
            pass
    return heuristic


def _heuristic(text: str, media_kind: str | None) -> dict[str, Any]:
    if media_kind in {"audio", "voice", "ptt"}:
        intent = "study_notes" if LEARN_RE.search(text or "") else "meeting_audio"
        return {"intent": intent, "confidence": 0.85, "router": "heuristic", "intelligence": "local"}
    if COMPUTER_RE.search(text):
        return {
            "intent": "computer_use",
            "confidence": 0.8,
            "router": "heuristic",
            "desktop_action": "open_cursor_chat" if "cursor" in text.lower() else "screenshot_describe",
            "intelligence": "premium",
        }
    if NOTES_RE.search(text):
        return {"intent": "notes", "confidence": 0.8, "router": "heuristic", "intelligence": "local"}
    if TASK_RE.search(text):
        return {"intent": "task", "confidence": 0.8, "router": "heuristic", "intelligence": "local"}
    if REMIND_RE.search(text):
        return {"intent": "reminder", "confidence": 0.8, "router": "heuristic", "intelligence": "local"}
    if MEETING_RE.search(text) and _has_clock(text):
        return {"intent": "reminder", "confidence": 0.85, "router": "heuristic", "intelligence": "local"}
    if LEARN_RE.search(text):
        return {"intent": "learning", "confidence": 0.8, "router": "heuristic", "intelligence": "local"}
    if MEETING_RE.search(text):
        return {"intent": "meeting", "confidence": 0.7, "router": "heuristic", "intelligence": "local"}
    if not text:
        return {"intent": "chat", "confidence": 0.4, "router": "heuristic", "intelligence": "local"}
    if len(text) > 1200:
        return {"intent": "notes", "confidence": 0.7, "router": "heuristic", "intelligence": "local"}
    return {"intent": "chat", "confidence": 0.35, "router": "heuristic", "intelligence": "local"}


def _has_clock(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:at|@)\s*\d{1,2}(?:[.:]\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?\b|\b\d{1,2}[.:]\d{2}\s*(?:a\.?m\.?|p\.?m\.?)?\b",
            text or "",
            re.I,
        )
    )


def _jev_route(text: str, media_kind: str | None, heuristic: dict[str, Any]) -> dict[str, Any]:
    state = {
        "channel": "whatsapp",
        "text": (text or "(empty caption)")[:1500],
        "media_kind": media_kind or "none",
        "heuristic_intent": heuristic.get("intent"),
        "product": (
            "Local laptop personal assistant. Handlers: tasks, reminders, learning plans, "
            "meeting notes from audio, study notes, personal notes, allowlisted computer use "
            "(Cursor chat, screenshot + describe), and chat."
        ),
    }
    result = evaluate(state, JEV_QUESTIONS)
    intent, confidence, probs = choice(result, "intent", heuristic.get("intent") or "chat")
    if intent not in INTENTS:
        intent = heuristic.get("intent") or "chat"
    if confidence < 0.45:
        intent = heuristic.get("intent") or intent
        confidence = max(confidence, float(heuristic.get("confidence") or 0))

    complexity, complexity_conf = score(result, "complexity")
    risk = noul(result, "risk")
    desktop, desktop_conf, _ = choice(result, "desktop_action", "none")
    audio_kind, _, _ = choice(result, "audio_kind", "none")

    if media_kind in {"audio", "voice", "ptt"} and intent in {"chat", "meeting"}:
        if audio_kind == "lecture":
            intent = "study_notes"
        elif audio_kind in {"meeting", "voice_memo"}:
            intent = "meeting_audio"

    intelligence = "premium" if complexity >= 1.4 and complexity_conf >= 0.4 else "local"
    if intent == "computer_use" and desktop == "screenshot_describe":
        intelligence = "premium"

    if risk >= 0.7:
        return {
            "intent": "chat",
            "confidence": confidence,
            "router": "jev",
            "refuse": True,
            "risk": risk,
            "intelligence": "local",
            "jev": _compact(result),
        }

    return {
        "intent": intent,
        "confidence": confidence,
        "router": "jev",
        "probabilities": probs,
        "complexity": complexity,
        "risk": risk,
        "desktop_action": desktop,
        "desktop_confidence": desktop_conf,
        "audio_kind": audio_kind,
        "intelligence": intelligence,
        "jev": _compact(result),
    }


def _compact(result: dict[str, Any]) -> dict[str, Any]:
    answers = result.get("answers") or {}
    compact = {}
    for key, value in answers.items():
        if not isinstance(value, dict):
            compact[key] = value
            continue
        compact[key] = {
            k: value[k]
            for k in ("type", "choice", "noul", "score", "confidence")
            if k in value
        }
    return {"model": result.get("model"), "answers": compact, "usage": result.get("usage")}
