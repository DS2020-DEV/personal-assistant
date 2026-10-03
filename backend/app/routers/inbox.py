from fastapi import APIRouter

from ..schemas import InboxIn
from ..services.inbox import handle_inbox

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


@router.post("")
def inbox(payload: InboxIn):
    return handle_inbox(
        text=payload.text,
        media_path=payload.media_path,
        media_kind=payload.media_kind,
        sender=payload.sender,
        source=payload.source,
        deliver_reply=payload.deliver_reply,
    )
