from fastapi import APIRouter

from ..config import public_settings, save_settings
from ..schemas import SettingsPatch
from ..services.scheduler import reload_scheduler

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings():
    return public_settings()


@router.put("")
def put_settings(payload: SettingsPatch):
    saved = save_settings(payload.settings)
    reload_scheduler()
    return saved
