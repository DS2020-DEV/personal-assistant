from fastapi import APIRouter, HTTPException

from ..db import Reminder, SessionLocal
from ..schemas import ReminderIn
from ..services.activity import log_activity

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


@router.get("")
def list_reminders():
    db = SessionLocal()
    try:
        rows = db.query(Reminder).order_by(Reminder.created_at.desc()).all()
        return [_row(r) for r in rows]
    finally:
        db.close()


@router.post("")
def create_reminder(payload: ReminderIn):
    db = SessionLocal()
    try:
        item = Reminder(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        log_activity("reminders", "created", item.title)
        return _row(item)
    finally:
        db.close()


@router.patch("/{reminder_id}")
def update_reminder(reminder_id: int, payload: ReminderIn):
    db = SessionLocal()
    try:
        item = db.get(Reminder, reminder_id)
        if not item:
            raise HTTPException(404, "Reminder not found")
        for key, value in payload.model_dump().items():
            setattr(item, key, value)
        db.commit()
        db.refresh(item)
        return _row(item)
    finally:
        db.close()


@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: int):
    db = SessionLocal()
    try:
        item = db.get(Reminder, reminder_id)
        if not item:
            raise HTTPException(404, "Reminder not found")
        db.delete(item)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


def _row(item: Reminder) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "message": item.message,
        "kind": item.kind,
        "run_at": item.run_at,
        "weekday": item.weekday,
        "time_of_day": item.time_of_day,
        "enabled": item.enabled,
        "task_id": item.task_id,
        "last_sent_at": item.last_sent_at,
        "created_at": item.created_at,
    }
