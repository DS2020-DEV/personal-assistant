from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..db import Activity, Meeting, MeetingReminder, SessionLocal
from ..paths import MEETINGS_DIR
from ..schemas import MeetingReminderIn
from ..services.meetings import ingest_audio

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


@router.get("")
def list_meetings():
    db = SessionLocal()
    try:
        rows = db.query(Meeting).order_by(Meeting.created_at.desc()).all()
        reminders = db.query(MeetingReminder).order_by(MeetingReminder.remind_at.asc()).all()
        inbox = (
            db.query(Activity)
            .filter(Activity.agent.in_(["whatsapp", "meetings", "inbox"]))
            .filter(Activity.action.in_(["received", "notes_ready", "failed"]))
            .order_by(Activity.ts.desc())
            .limit(20)
            .all()
        )
        return {
            "meetings": [_meeting(m) for m in rows],
            "reminders": [_reminder(r) for r in reminders],
            "inbox": [
                {
                    "id": row.id,
                    "ts": row.ts,
                    "agent": row.agent,
                    "action": row.action,
                    "detail": row.detail,
                    "level": row.level,
                }
                for row in inbox
            ],
        }
    finally:
        db.close()


@router.post("/upload")
async def upload_meeting(file: UploadFile = File(...), title: str = Form("Meeting"), send: bool = Form(True)):
    MEETINGS_DIR.mkdir(parents=True, exist_ok=True)
    dest = MEETINGS_DIR / file.filename
    dest.write_bytes(await file.read())
    meeting = ingest_audio(dest, title=title, source="dashboard", send=send)
    return _meeting(meeting)


@router.post("/from-path")
def from_path(path: str, title: str = "Meeting", send: bool = True):
    audio = Path(path)
    if not audio.exists():
        raise HTTPException(404, "Audio file not found")
    meeting = ingest_audio(audio, title=title, source="whatsapp", send=send)
    return _meeting(meeting)


@router.post("/reminders")
def create_meeting_reminder(payload: MeetingReminderIn):
    db = SessionLocal()
    try:
        item = MeetingReminder(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return _reminder(item)
    finally:
        db.close()


@router.delete("/reminders/{reminder_id}")
def delete_meeting_reminder(reminder_id: int):
    db = SessionLocal()
    try:
        item = db.get(MeetingReminder, reminder_id)
        if not item:
            raise HTTPException(404, "Not found")
        db.delete(item)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


def _meeting(item: Meeting) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "source": item.source,
        "audio_path": item.audio_path,
        "audio_url": f"/media/meetings/{Path(item.audio_path).name}" if item.audio_path else "",
        "transcript": item.transcript,
        "notes_md": item.notes_md,
        "action_items": item.action_items,
        "meeting_at": item.meeting_at,
        "created_at": item.created_at,
    }


def _reminder(item: MeetingReminder) -> dict:
    return {
        "id": item.id,
        "meeting_id": item.meeting_id,
        "title": item.title,
        "message": item.message,
        "remind_at": item.remind_at,
        "sent": item.sent,
        "created_at": item.created_at,
    }
