from fastapi import APIRouter, Query

from ..db import Activity, SessionLocal

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("")
def list_activity(limit: int = Query(100, le=500)):
    db = SessionLocal()
    try:
        rows = db.query(Activity).order_by(Activity.ts.desc()).limit(limit).all()
        return [
            {
                "id": row.id,
                "ts": row.ts,
                "agent": row.agent,
                "action": row.action,
                "detail": row.detail,
                "level": row.level,
            }
            for row in rows
        ]
    finally:
        db.close()
