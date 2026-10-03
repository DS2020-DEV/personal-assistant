from fastapi import APIRouter

from ..db import ComputerJob, SessionLocal
from ..services.computer import run_computer_job

router = APIRouter(prefix="/api/computer", tags=["computer"])


@router.get("/jobs")
def jobs(limit: int = 20):
    db = SessionLocal()
    try:
        rows = db.query(ComputerJob).order_by(ComputerJob.created_at.desc()).limit(limit).all()
        return [
            {
                "id": row.id,
                "action": row.action,
                "request": row.request,
                "result": row.result,
                "status": row.status,
                "screenshot_path": row.screenshot_path,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    finally:
        db.close()


@router.post("/run")
def run(payload: dict):
    return run_computer_job(
        payload.get("text") or "",
        payload.get("extracted") or {},
        payload.get("desktop_action"),
    )
