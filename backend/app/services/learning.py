from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ..config import load_settings
from ..db import LearningLesson, LearningPlan, SessionLocal, utcnow
from ..paths import LEARNING_DIR
from .activity import log_activity
from .llm import chat, chat_json
from .research import research_topic
from .tts import synthesize, to_voice_note
from .whatsapp import notify_desktop, send_whatsapp

PLAN_PROMPT = """You are a curriculum designer for a busy engineer.
Create a day-by-day learning plan.
Return JSON: {{"goal": "...", "days": [{{"day": 1, "title": "...", "objectives": ["..."]}}]}}
Rules:
- One focused subtopic per day
- Start from foundations, then patterns, then trade-offs, then a recap/practice day
- {days} days total
- Titles should be concrete, not vague
"""

NOTES_PROMPT = """You are a senior engineer writing compact study notes for one day's lesson.
Write GitHub-flavored markdown with:
- A 3-line hook
- Core idea
- How it works
- A whiteboard-style example
- Common pitfalls
- A 5-question self-check
Keep it under 900 words. No fluff.
"""

SCRIPT_PROMPT = """You write spoken teaching scripts for a one-on-one voice lesson.
Voice: warm, clear, natural teacher. Like a great mentor walking someone through a whiteboard.
Constraints:
- Plain speech only. No markdown, no bullet symbols, no stage directions.
- Short spoken sentences. Use questions. Use analogies.
- Start with a 15-second hook, then teach, then a recap the student can remember on a commute.
- About {minutes} minutes when spoken out loud (roughly 130 words per minute).
- Never say you are an AI.
"""


def local_tz():
    return ZoneInfo(load_settings().get("timezone", "Asia/Kolkata"))


def create_plan(topic: str, goal: str = "", days: int = 10, daily_time: str = "09:00") -> LearningPlan:
    db = SessionLocal()
    try:
        planned = chat_json(
            [
                {"role": "system", "content": PLAN_PROMPT.format(days=days)},
                {
                    "role": "user",
                    "content": f"Topic: {topic}\nLearner goal: {goal or 'Become interview- and job-ready on this topic.'}",
                },
            ]
        )
        plan = LearningPlan(
            topic=topic.strip(),
            goal=planned.get("goal") or goal,
            daily_time=daily_time,
            total_days=days,
            current_day=1,
            status="active",
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        today = datetime.now(local_tz()).date()
        for item in planned.get("days") or []:
            day_index = int(item.get("day") or 0)
            if day_index < 1:
                continue
            objectives = item.get("objectives") or []
            if isinstance(objectives, list):
                objectives_text = "\n".join(f"- {o}" for o in objectives)
            else:
                objectives_text = str(objectives)
            lesson = LearningLesson(
                plan_id=plan.id,
                day_index=day_index,
                title=item.get("title") or f"Day {day_index}",
                objectives=objectives_text,
                status="planned",
                scheduled_date=(today + timedelta(days=day_index - 1)).isoformat(),
            )
            db.add(lesson)
        db.commit()
        log_activity("learning", "plan_created", f"{topic} · {days} days")
        return plan
    finally:
        db.close()


def generate_lesson(lesson_id: int, send: bool = True) -> LearningLesson:
    db = SessionLocal()
    try:
        lesson = db.get(LearningLesson, lesson_id)
        if not lesson:
            raise ValueError("Lesson not found")
        plan = db.get(LearningPlan, lesson.plan_id)
        minutes = int(load_settings()["learning"].get("lessonMinutes", 8))
        brief = ""
        if load_settings()["learning"].get("includeResearch", True):
            brief = research_topic(plan.topic, f"{lesson.title} {lesson.objectives}")
            lesson.research_brief = brief
        notes = chat(
            [
                {"role": "system", "content": NOTES_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Overall topic: {plan.topic}\n"
                        f"Day {lesson.day_index}: {lesson.title}\n"
                        f"Objectives:\n{lesson.objectives}\n\n"
                        f"Research brief:\n{brief}"
                    ),
                },
            ],
            temperature=0.4,
        )
        script = chat(
            [
                {"role": "system", "content": SCRIPT_PROMPT.format(minutes=minutes)},
                {
                    "role": "user",
                    "content": (
                        f"Teach day {lesson.day_index} of {plan.total_days} on {plan.topic}.\n"
                        f"Today's focus: {lesson.title}\n"
                        f"Objectives:\n{lesson.objectives}\n\n"
                        f"Study notes to teach from:\n{notes}"
                    ),
                },
            ],
            temperature=0.7,
        )
        lesson.notes_md = notes
        lesson.script = script
        stem = f"lesson-{plan.id}-{lesson.day_index}"
        wav = synthesize(script, stem)
        media = to_voice_note(wav)
        lesson.audio_path = str(media)
        notes_file = LEARNING_DIR / f"{stem}.md"
        notes_file.write_text(
            f"# {plan.topic} — Day {lesson.day_index}: {lesson.title}\n\n{notes}\n",
            encoding="utf-8",
        )
        lesson.status = "ready"
        db.commit()
        if send:
            deliver_lesson(lesson.id)
            db.refresh(lesson)
        log_activity("tutor", "lesson_generated", f"{plan.topic} day {lesson.day_index}")
        return lesson
    finally:
        db.close()


def deliver_lesson(lesson_id: int) -> dict:
    db = SessionLocal()
    try:
        lesson = db.get(LearningLesson, lesson_id)
        plan = db.get(LearningPlan, lesson.plan_id)
        settings = load_settings()["learning"]
        from pathlib import Path

        caption = (
            f"Today's lesson ({lesson.day_index}/{plan.total_days}) — {plan.topic}\n"
            f"*{lesson.title}*\n\n"
        )
        if settings.get("sendNotesToWhatsapp"):
            send_whatsapp(caption + lesson.notes_md[:3500])
        if settings.get("sendAudioToWhatsapp") and lesson.audio_path:
            send_whatsapp(
                f"Voice lesson: {lesson.title}",
                Path(lesson.audio_path),
            )
        notify_desktop("Daily lesson ready", f"{plan.topic}: {lesson.title}")
        lesson.sent_at = utcnow()
        lesson.status = "sent"
        plan.current_day = max(plan.current_day, lesson.day_index)
        db.commit()
        log_activity("tutor", "lesson_sent", lesson.title)
        return {"ok": True, "lesson_id": lesson.id}
    finally:
        db.close()


def todays_lesson(plan_id: int | None = None) -> LearningLesson | None:
    db = SessionLocal()
    try:
        q = db.query(LearningPlan).filter(LearningPlan.status == "active")
        plan = db.get(LearningPlan, plan_id) if plan_id else q.order_by(LearningPlan.id.desc()).first()
        if not plan:
            return None
        today = datetime.now(local_tz()).date().isoformat()
        lesson = (
            db.query(LearningLesson)
            .filter(LearningLesson.plan_id == plan.id, LearningLesson.scheduled_date == today)
            .first()
        )
        if not lesson:
            lesson = (
                db.query(LearningLesson)
                .filter(LearningLesson.plan_id == plan.id, LearningLesson.status.in_(["planned", "ready"]))
                .order_by(LearningLesson.day_index.asc())
                .first()
            )
        return lesson
    finally:
        db.close()


def run_daily_lesson() -> None:
    lesson = todays_lesson()
    if not lesson:
        log_activity("tutor", "no_lesson", "No active learning plan")
        return
    if lesson.status == "sent" and lesson.scheduled_date == datetime.now(local_tz()).date().isoformat():
        return
    if lesson.status == "planned":
        generate_lesson(lesson.id, send=True)
    elif lesson.status == "ready":
        deliver_lesson(lesson.id)
