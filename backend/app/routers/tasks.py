from fastapi import APIRouter, HTTPException

from ..db import SessionLocal, Task, utcnow
from ..schemas import TaskIn
from ..services.activity import log_activity

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
def list_tasks(status: str | None = None):
    db = SessionLocal()
    try:
        q = db.query(Task).order_by(Task.created_at.desc())
        if status:
            q = q.filter(Task.status == status)
        return [_task(t) for t in q.all()]
    finally:
        db.close()


@router.post("")
def create_task(payload: TaskIn):
    db = SessionLocal()
    try:
        task = Task(**payload.model_dump())
        db.add(task)
        db.commit()
        db.refresh(task)
        log_activity("tasks", "created", task.title)
        return _task(task)
    finally:
        db.close()


@router.patch("/{task_id}")
def update_task(task_id: int, payload: TaskIn):
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        for key, value in payload.model_dump().items():
            setattr(task, key, value)
        if payload.status == "done" and not task.completed_at:
            task.completed_at = utcnow()
        db.commit()
        db.refresh(task)
        return _task(task)
    finally:
        db.close()


@router.delete("/{task_id}")
def delete_task(task_id: int):
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        db.delete(task)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


def _task(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "due_at": task.due_at,
        "source": task.source,
        "created_at": task.created_at,
        "completed_at": task.completed_at,
    }
