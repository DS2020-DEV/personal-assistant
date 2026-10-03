from fastapi import APIRouter
from pydantic import BaseModel

from ..services.runtime import set_windows_autostart, start_assistants, status, stop_assistants, windows_autostart_enabled

router = APIRouter(prefix="/api/system", tags=["system"])


class AutostartIn(BaseModel):
    enabled: bool


@router.get("/status")
def get_status():
    return status()


@router.post("/start")
def start():
    return start_assistants()


@router.post("/stop")
def stop():
    return stop_assistants()


@router.get("/autostart")
def get_autostart():
    return {"ok": True, "enabled": windows_autostart_enabled()}


@router.post("/autostart")
def post_autostart(payload: AutostartIn):
    return set_windows_autostart(payload.enabled)
