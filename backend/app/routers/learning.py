from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..db import LearningLesson, LearningPlan, SessionLocal
from ..schemas import LearningPlanIn, LessonGenerateIn
from ..services.learning import create_plan, deliver_lesson, generate_lesson

router = APIRouter(prefix="/api/learning", tags=["learning"])


@router.get("/plans")
def list_plans():
    db = SessionLocal()
    try:
        plans = db.query(LearningPlan).order_by(LearningPlan.created_at.desc()).all()
        return [_plan(p, db) for p in plans]
    finally:
        db.close()


@router.post("/plans")
def new_plan(payload: LearningPlanIn):
    plan = create_plan(payload.topic, payload.goal, payload.days, payload.daily_time)
    db = SessionLocal()
    try:
        fresh = db.get(LearningPlan, plan.id)
        return _plan(fresh, db)
    finally:
        db.close()


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int):
    db = SessionLocal()
    try:
        plan = db.get(LearningPlan, plan_id)
        if not plan:
            raise HTTPException(404, "Plan not found")
        return _plan(plan, db)
    finally:
        db.close()


@router.post("/lessons/{lesson_id}/generate")
def gen_lesson(lesson_id: int, payload: LessonGenerateIn):
    lesson = generate_lesson(lesson_id, send=payload.send)
    return _lesson(lesson)


@router.post("/lessons/{lesson_id}/send")
def send_lesson(lesson_id: int):
    return deliver_lesson(lesson_id)


@router.patch("/plans/{plan_id}/status")
def set_status(plan_id: int, status: str):
    db = SessionLocal()
    try:
        plan = db.get(LearningPlan, plan_id)
        if not plan:
            raise HTTPException(404, "Plan not found")
        plan.status = status
        db.commit()
        return {"ok": True, "status": status}
    finally:
        db.close()


def _plan(plan: LearningPlan, db) -> dict:
    lessons = (
        db.query(LearningLesson)
        .filter(LearningLesson.plan_id == plan.id)
        .order_by(LearningLesson.day_index.asc())
        .all()
    )
    return {
        "id": plan.id,
        "topic": plan.topic,
        "goal": plan.goal,
        "status": plan.status,
        "daily_time": plan.daily_time,
        "total_days": plan.total_days,
        "current_day": plan.current_day,
        "created_at": plan.created_at,
        "lessons": [_lesson(item) for item in lessons],
    }


def _lesson(item: LearningLesson) -> dict:
    return {
        "id": item.id,
        "plan_id": item.plan_id,
        "day_index": item.day_index,
        "title": item.title,
        "objectives": item.objectives,
        "notes_md": item.notes_md,
        "script": item.script,
        "audio_path": item.audio_path,
        "audio_url": f"/media/audio/{Path(item.audio_path).name}" if item.audio_path else "",
        "status": item.status,
        "scheduled_date": item.scheduled_date,
        "sent_at": item.sent_at,
    }
