from __future__ import annotations

import json
from pathlib import Path

from ..db import Meeting, SessionLocal, Task, utcnow
from ..paths import MEETINGS_DIR
from .activity import log_activity
from .chunking import chunk_text
from .llm import generate, chat_json
from .stt import transcribe
from .whatsapp import notify_desktop, send_whatsapp

NOTES_PROMPT = """You are a meeting notes agent.
Turn a transcript (or a batch of section summaries) into useful notes.
Return JSON with keys:
title, summary, decisions (array of strings), action_items (array of {title, owner, due}), follow_ups (array of strings).
If the audio is a lecture rather than a meeting, still extract the core takeaways and action items for the learner.
"""

SECTION_PROMPT = """Summarize this meeting transcript section only.
Return JSON: {"bullets": ["..."], "decisions": ["..."], "action_items": [{"title": "...", "owner": "", "due": ""}]}
Do not invent speakers or facts not in this section.
"""


def ingest_audio(
    audio_path: str | Path,
    title: str = "",
    source: str = "whatsapp",
    send: bool = True,
    intelligence: str = "local",
) -> Meeting:
    path = Path(audio_path)
    transcript = transcribe(path)
    parsed = _notes_from_transcript(transcript, intelligence=intelligence)
    notes = generate(
        [
            {
                "role": "system",
                "content": "Write clean markdown meeting notes from the JSON. Include summary, decisions, action items. Do not paste a full transcript.",
            },
            {"role": "user", "content": json.dumps(parsed)[:6000]},
        ],
        temperature=0.3,
        intelligence=intelligence,
    )
    db = SessionLocal()
    try:
        meeting = Meeting(
            title=title or parsed.get("title") or path.stem,
            source=source,
            audio_path=str(path),
            transcript=transcript,
            notes_md=notes,
            action_items=json.dumps(parsed.get("action_items") or []),
            meeting_at=utcnow(),
        )
        db.add(meeting)
        for item in parsed.get("action_items") or []:
            if isinstance(item, dict) and item.get("title"):
                db.add(
                    Task(
                        title=str(item["title"]),
                        description=f"From meeting: {meeting.title}",
                        source="meeting",
                        priority="normal",
                    )
                )
        db.commit()
        db.refresh(meeting)
        out = MEETINGS_DIR / f"meeting-{meeting.id}.md"
        out.write_text(f"# {meeting.title}\n\n{notes}\n", encoding="utf-8")
        if send:
            send_whatsapp(f"Meeting notes — {meeting.title}\n\n{notes[:3500]}")
            notify_desktop("Meeting notes ready", meeting.title)
        log_activity("meetings", "notes_ready", meeting.title)
        return meeting
    finally:
        db.close()


def _notes_from_transcript(transcript: str, *, intelligence: str) -> dict:
    sections = chunk_text(transcript, max_chars=2800)
    if len(sections) <= 1:
        return chat_json(
            [
                {"role": "system", "content": NOTES_PROMPT},
                {"role": "user", "content": (transcript or "")[:4000]},
            ],
            intelligence=intelligence,
        )
    log_activity("meetings", "batching", f"{len(sections)} transcript chunks")
    mapped: list[dict] = []
    for i, section in enumerate(sections, start=1):
        mapped.append(
            chat_json(
                [
                    {"role": "system", "content": SECTION_PROMPT},
                    {"role": "user", "content": f"Section {i}/{len(sections)}:\n{section}"},
                ],
                intelligence=intelligence,
            )
        )
    return chat_json(
        [
            {"role": "system", "content": NOTES_PROMPT},
            {
                "role": "user",
                "content": "Merge these section extracts into one meeting JSON. Deduplicate action items.\n"
                + json.dumps(mapped)[:7000],
            },
        ],
        intelligence=intelligence,
    )
