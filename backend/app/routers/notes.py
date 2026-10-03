from fastapi import APIRouter

from ..services.notes import list_notes

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("")
def notes():
    return list_notes()
