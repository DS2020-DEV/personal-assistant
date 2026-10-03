from ..db import Activity, SessionLocal, utcnow


def log_activity(agent: str, action: str, detail: str = "", level: str = "info") -> None:
    db = SessionLocal()
    try:
        db.add(Activity(ts=utcnow(), agent=agent, action=action, detail=detail[:4000], level=level))
        db.commit()
    finally:
        db.close()
