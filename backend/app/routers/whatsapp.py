from fastapi import APIRouter
from pydantic import BaseModel

from ..services.whatsapp import pairing_snapshot, start_pairing_qr

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


class QrStartIn(BaseModel):
    force: bool = False


@router.get("/qr")
def get_qr():
    return pairing_snapshot()


@router.post("/qr")
def post_qr(payload: QrStartIn = QrStartIn()):
    return start_pairing_qr(force=payload.force)
