from __future__ import annotations

from ..db import Note, SessionLocal
from ..paths import NOTES_DIR
from .activity import log_activity
from .chunking import chunk_text
from .llm import generate
from .stt import transcribe
from .whatsapp import notify_desktop


def save_note(
    title: str,
    body: str = "",
    *,
    source: str = "whatsapp",
    audio_path: str | None = None,
    kind: str = "note",
    polish: bool = True,
    intelligence: str = "local",
) -> Note:
    text = body.strip()
    transcript = ""
    if audio_path:
        transcript = transcribe(audio_path)
        text = (text + "\n\n" + transcript).strip() if text else transcript
    if polish and text:
        notes = _polish_long_text(text, intelligence=intelligence)
    else:
        notes = text
    db = SessionLocal()
    try:
        note = Note(
            title=(title or "Note")[:400],
            kind=kind,
            body_md=notes,
            source=source,
            audio_path=audio_path or "",
            transcript=transcript,
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        (NOTES_DIR / f"note-{note.id}.md").write_text(f"# {note.title}\n\n{notes}\n", encoding="utf-8")
        log_activity("notes", "saved", note.title)
        notify_desktop("Note saved", note.title)
        return note
    finally:
        db.close()


def _polish_long_text(text: str, *, intelligence: str) -> str:
    system = (
        "Turn the user's message or transcript into clean markdown notes. "
        "Keep facts. Add headings, bullets, and a 3-line summary. "
        "If it is study material, include key definitions and a mini quiz. "
        "If it is a voice memo of tasks, list them."
    )
    sections = chunk_text(text, max_chars=2800)
    if len(sections) <= 1:
        return generate(
            [{"role": "system", "content": system}, {"role": "user", "content": text[:4000]}],
            temperature=0.3,
            intelligence=intelligence,
        )
    log_activity("notes", "batching", f"{len(sections)} chunks")
    parts = []
    for i, section in enumerate(sections, start=1):
        parts.append(
            generate(
                [
                    {"role": "system", "content": "Summarize this section as markdown bullets. No preamble."},
                    {"role": "user", "content": f"Section {i}/{len(sections)}:\n{section}"},
                ],
                temperature=0.3,
                intelligence=intelligence,
            )
        )
    return generate(
        [
            {"role": "system", "content": system + " Merge the section notes; drop duplicates."},
            {"role": "user", "content": "\n\n".join(parts)[:7000]},
        ],
        temperature=0.3,
        intelligence=intelligence,
    )


def list_notes(limit: int = 50) -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.query(Note).order_by(Note.created_at.desc()).limit(limit).all()
        return [
            {
                "id": n.id,
                "title": n.title,
                "kind": n.kind,
                "body_md": n.body_md,
                "source": n.source,
                "created_at": n.created_at,
            }
            for n in rows
        ]
    finally:
        db.close()


def note_to_dict(note: Note) -> dict:
    return {
        "id": note.id,
        "title": note.title,
        "kind": note.kind,
        "body_md": note.body_md,
        "source": note.source,
        "audio_path": note.audio_path,
        "transcript": note.transcript,
        "created_at": note.created_at,
    }
