from __future__ import annotations

import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re

from ..config import load_settings
from ..db import Reminder, SessionLocal, Task
from .activity import log_activity
from .classifier import classify_inbox
from .computer import run_computer_job
from .extract import extract_fields, parse_local_datetime, strip_prefix
from .learning import create_plan, generate_lesson, todays_lesson
from .llm import generate
from .meetings import ingest_audio
from .notes import save_note
from .whatsapp import send_whatsapp


def handle_inbox(
    text: str,
    media_path: str | None = None,
    media_kind: str | None = None,
    sender: str | None = None,
    source: str = "whatsapp",
    deliver_reply: bool = True,
) -> dict:
    try:
        return _handle_inbox(
            text=text,
            media_path=media_path,
            media_kind=media_kind,
            sender=sender,
            source=source,
            deliver_reply=deliver_reply,
        )
    except Exception as exc:
        log_activity("inbox", "failed", str(exc), "error")
        reply = "Message received. I hit a snag handling that — send it again in a moment."
        _maybe_send(source, reply, deliver_reply)
        return {"intent": "error", "reply": reply, "error": str(exc)}


def _handle_inbox(
    text: str,
    media_path: str | None = None,
    media_kind: str | None = None,
    sender: str | None = None,
    source: str = "whatsapp",
    deliver_reply: bool = True,
) -> dict:
    classified = classify_inbox(text, media_kind)
    intent = classified.get("intent")
    if intent == "chat" and (media_path or len(text or "") > 1500):
        intent = "meeting_audio" if media_path else "notes"
        classified = {**classified, "intent": intent, "router": classified.get("router") or "heuristic"}
    extracted = classified.get("extracted") or {}
    intelligence = classified.get("intelligence") or "local"
    if (
        not media_path
        and parse_local_datetime(text)
        and re.search(r"\b(meeting|call|standup)\b", text or "", re.I)
    ):
        intent = "reminder"
        extracted = {**extracted, **extract_fields(text, "reminder")}
        classified = {**classified, "intent": intent}
    log_activity("whatsapp" if source == "whatsapp" else "inbox", "received", (text or str(media_path))[:240])

    if classified.get("refuse"):
        reply = "I won't run that. Ask me for notes, tasks, study plans, meeting recordings, or allowlisted computer help (Cursor / screenshot)."
        _maybe_send(source, reply, deliver_reply)
        return {"intent": "refused", "reply": reply, "classified": classified}

    if intent == "computer_use":
        result = run_computer_job(
            text,
            extracted,
            desktop_action=classified.get("desktop_action"),
        )
        reply = result.get("reply") or "Done."
        _maybe_send(source, reply[:3500], deliver_reply)
        return {"intent": intent, "reply": reply, "job_id": result.get("job_id"), "classified": classified}

    if intent in {"meeting_audio", "meeting"} and media_path:
        kind = classified.get("audio_kind")
        if intent == "study_notes" or kind == "lecture":
            note = save_note(
                extracted.get("title") or extracted.get("topic") or "Study recording",
                text,
                source=source,
                audio_path=media_path,
                kind="study",
                intelligence=intelligence,
            )
            topic = extracted.get("topic") or note.title
            plan = create_plan(topic, days=7)
            _kick_lesson(plan.id)
            reply = f"Study notes saved ({note.title}). Started a 7-day plan for {plan.topic}."
            _maybe_send(source, reply, deliver_reply)
            return {"intent": "study_notes", "note_id": note.id, "plan_id": plan.id, "reply": reply, "classified": classified}
        title = extracted.get("title") or text[:80] or "Meeting"
        ack = "Message received. Transcribing your meeting recording now — notes will follow."
        log_activity("meetings", "received", f"{title} · {media_path}")
        _maybe_send(source, ack, deliver_reply)
        threading.Thread(
            target=_ingest_meeting_later,
            kwargs={
                "media_path": media_path,
                "title": title,
                "source": source,
                "intelligence": intelligence,
            },
            daemon=True,
        ).start()
        return {"intent": "meeting_audio", "status": "processing", "reply": ack, "classified": classified}

    if intent in {"meeting_audio", "meeting"} and not media_path:
        when = parse_local_datetime(text) or parse_local_datetime(str(extracted.get("when") or ""))
        if when:
            reminder = _create_reminder_from_text(
                text,
                {**extracted, "when": when.isoformat(), "title": extracted.get("title") or text[:120]},
                source,
            )
            reply = _reminder_reply(reminder)
            _maybe_send(source, reply, deliver_reply)
            return {"intent": "reminder", "reminder_id": reminder.id, "reply": reply, "classified": classified}
        note = save_note(
            extracted.get("title") or "Meeting",
            extracted.get("details") or text,
            source=source,
            intelligence=intelligence,
        )
        reply = f"Saved meeting note: {note.title}"
        _maybe_send(source, reply, deliver_reply)
        return {"intent": "notes", "note_id": note.id, "reply": reply, "classified": classified}

    if intent == "study_notes":
        if media_path and media_kind in {"audio", "voice", "ptt"}:
            note = save_note(
                extracted.get("topic") or "Study recording",
                text,
                source=source,
                audio_path=media_path,
                kind="study",
                intelligence=intelligence,
            )
        else:
            note = save_note(
                extracted.get("topic") or extracted.get("title") or "Study notes",
                extracted.get("details") or text,
                source=source,
                kind="study",
                intelligence=intelligence,
            )
        topic = extracted.get("topic") or note.title
        plan = create_plan(topic)
        _kick_lesson(plan.id)
        reply = (
            f"Saved study notes for {topic} and created a {plan.total_days}-day plan. "
            "I'll send one lesson a day."
        )
        _maybe_send(source, reply, deliver_reply)
        return {"intent": intent, "note_id": note.id, "plan_id": plan.id, "reply": reply, "classified": classified}

    if intent == "notes":
        body = extracted.get("body") or extracted.get("details") or text
        if len(text or "") > len(body or ""):
            body = text
        heavy = bool(media_path) or len(body or "") > 800
        if heavy:
            ack = "Message received. Saving your note now — the polished version will follow."
            log_activity("notes", "received", (extracted.get("title") or body or "Note")[:240])
            _maybe_send(source, ack, deliver_reply)
            threading.Thread(
                target=_save_note_later,
                kwargs={
                    "title": extracted.get("title") or "Note",
                    "body": body,
                    "source": source,
                    "media_path": media_path if media_kind in {"audio", "voice", "ptt"} else None,
                    "intelligence": intelligence,
                },
                daemon=True,
            ).start()
            return {"intent": intent, "status": "processing", "reply": ack, "classified": classified}
        note = save_note(
            extracted.get("title") or "Note",
            body,
            source=source,
            audio_path=media_path if media_kind in {"audio", "voice", "ptt"} else None,
            intelligence=intelligence,
        )
        reply = f"Saved note: {note.title}\n\n{note.body_md[:2500]}"
        _maybe_send(source, reply, deliver_reply)
        return {"intent": intent, "note_id": note.id, "reply": reply, "classified": classified}

    if intent == "task":
        title = extracted.get("title") or strip_prefix(text, ["add task", "create task", "new task", "todo", "task:"])
        db = SessionLocal()
        try:
            task = Task(title=title[:400], description=extracted.get("details") or text, source=source)
            db.add(task)
            db.commit()
            db.refresh(task)
            reply = f"Task saved: {task.title}"
            _maybe_send(source, reply, deliver_reply)
            log_activity("tasks", "created", task.title)
            return {"intent": intent, "task_id": task.id, "reply": reply, "classified": classified}
        finally:
            db.close()

    if intent == "reminder":
        reminder = _create_reminder_from_text(text, extracted, source)
        reply = _reminder_reply(reminder)
        _maybe_send(source, reply, deliver_reply)
        return {"intent": intent, "reminder_id": reminder.id, "reply": reply, "classified": classified}

    if intent == "learning":
        topic = extracted.get("topic") or strip_prefix(
            text, ["learn", "teach me", "research", "study", "start learning"]
        )
        plan = create_plan(topic)
        _kick_lesson(plan.id)
        reply = (
            f"Created a {plan.total_days}-day plan for {plan.topic}. "
            "I'll send one lesson a day, with notes and a spoken teaching audio."
        )
        _maybe_send(source, reply, deliver_reply)
        return {"intent": intent, "plan_id": plan.id, "reply": reply, "classified": classified}

    if intent == "meeting" and media_path:
        meeting = ingest_audio(media_path, title=extracted.get("title") or "Meeting", source=source)
        return {"intent": intent, "meeting_id": meeting.id, "classified": classified}

    reply = generate(
        [
            {
                "role": "system",
                "content": (
                    "You are the user's local personal assistant on their Windows laptop. "
                    "Be concise. You can create tasks, reminders, learning plans, meeting notes, "
                    "study notes, and (when asked) operate allowlisted desktop actions: "
                    "open Cursor, type a prompt in Cursor chat, screenshot and describe the screen. "
                    "If they need one of those, say so clearly."
                ),
            },
            {"role": "user", "content": (text or "Hello")[:4000]},
        ],
        temperature=0.5,
        intelligence=intelligence,
    )
    _maybe_send(source, reply, deliver_reply)
    log_activity("orchestrator", "chat", reply[:240])
    return {"intent": "chat", "reply": reply, "classified": classified}


def _ingest_meeting_later(*, media_path: str, title: str, source: str, intelligence: str) -> None:
    try:
        ingest_audio(media_path, title=title, source=source, intelligence=intelligence)
    except Exception as exc:
        log_activity("meetings", "failed", str(exc), "error")
        if source == "whatsapp":
            send_whatsapp(f"Got the recording, but transcription failed: {exc}")


def _save_note_later(*, title: str, body: str, source: str, media_path: str | None, intelligence: str) -> None:
    try:
        note = save_note(
            title,
            body,
            source=source,
            audio_path=media_path,
            intelligence=intelligence,
        )
        if source == "whatsapp":
            send_whatsapp(f"Saved note: {note.title}\n\n{note.body_md[:2500]}")
    except Exception as exc:
        log_activity("notes", "failed", str(exc), "error")
        if source == "whatsapp":
            send_whatsapp(f"Got the note, but polishing failed: {exc}")


def _kick_lesson(plan_id: int) -> None:
    lesson = todays_lesson(plan_id)
    if lesson:
        threading.Thread(target=generate_lesson, args=(lesson.id,), kwargs={"send": True}, daemon=True).start()


_OVERFLOW = (
    "context compaction",
    "auto-compaction could not recover",
    "use /compact",
    "context limit exceeded",
)


def _maybe_send(source: str, reply: str, deliver_reply: bool = True) -> None:
    if not deliver_reply or source != "whatsapp" or not reply:
        return
    lowered = reply.lower()
    if any(marker in lowered for marker in _OVERFLOW):
        send_whatsapp("Message received. I'm processing that locally.")
        return
    send_whatsapp(reply)


def _reminder_reply(reminder: Reminder) -> str:
    when = reminder.run_at
    stamp = when.strftime("%d %b, %I:%M %p") if when else ""
    line = f"Reminder set: {reminder.title}" + (f" ({stamp})" if stamp else "")
    if getattr(reminder, "_lead_at", None):
        lead = reminder._lead_at.strftime("%d %b, %I:%M %p")
        line += f". I'll also ping you 30 minutes before ({lead})."
    elif when and reminder.kind == "once":
        line += ". The 30-minute warning already passed, so you'll only get the on-time ping."
    return line


def _create_reminder_from_text(text: str, extracted: dict, source: str) -> Reminder:
    tz = ZoneInfo(load_settings().get("timezone", "Asia/Kolkata"))
    title = extracted.get("title") or text[:120]
    when = extracted.get("when")
    run_at = None
    kind = "once"
    time_of_day = None
    parsed = parse_local_datetime(text) if text else None
    if isinstance(when, str) and "every day" in when.lower():
        kind = "daily"
        time_of_day = load_settings()["schedule"]["dailyReminderTime"]
    elif isinstance(when, str):
        try:
            run_at = datetime.fromisoformat(when)
        except ValueError:
            run_at = parsed or datetime.now(tz) + timedelta(hours=1)
    else:
        run_at = parsed or datetime.now(tz) + timedelta(hours=1)
    if run_at and run_at.tzinfo is None:
        run_at = run_at.replace(tzinfo=tz)
    now = datetime.now(tz)
    db = SessionLocal()
    try:
        reminder = Reminder(
            title=title[:400],
            message=extracted.get("details") or text,
            kind=kind,
            run_at=run_at,
            time_of_day=time_of_day,
        )
        db.add(reminder)
        lead_at = None
        if kind == "once" and run_at:
            lead_at = run_at - timedelta(minutes=30)
            if lead_at > now:
                stamp = run_at.strftime("%I:%M %p")
                db.add(
                    Reminder(
                        title=f"In 30 min: {title}"[:400],
                        message=f"{extracted.get('details') or text}\nStarts at {stamp}.",
                        kind="once",
                        run_at=lead_at,
                    )
                )
                log_activity("reminders", "created", f"30-min warning for {title}")
            else:
                lead_at = None
        db.commit()
        db.refresh(reminder)
        reminder._lead_at = lead_at
        log_activity("reminders", "created", reminder.title)
        return reminder
    finally:
        db.close()
