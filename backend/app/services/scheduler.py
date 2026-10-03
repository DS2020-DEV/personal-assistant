from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..config import load_settings
from ..db import MeetingReminder, Reminder, SessionLocal, Task, utcnow
from .activity import log_activity
from .learning import run_daily_lesson
from .whatsapp import notify_desktop, send_whatsapp

scheduler = BackgroundScheduler()
_started = False


def start_scheduler() -> None:
    global _started
    if _started:
        return
    settings = load_settings()
    tz = ZoneInfo(settings.get("timezone", "Asia/Kolkata"))
    reminder_h, reminder_m = _hhmm(settings["schedule"]["dailyReminderTime"])
    lesson_h, lesson_m = _hhmm(settings["schedule"]["dailyLessonTime"])
    preview_h, preview_m = _hhmm(settings["schedule"].get("eveningPreviewTime") or "23:00")
    scheduler.add_job(send_daily_tasks, CronTrigger(hour=reminder_h, minute=reminder_m, timezone=tz), id="daily_tasks", replace_existing=True)
    scheduler.add_job(run_daily_lesson, CronTrigger(hour=lesson_h, minute=lesson_m, timezone=tz), id="daily_lesson", replace_existing=True)
    scheduler.add_job(send_tomorrow_preview, CronTrigger(hour=preview_h, minute=preview_m, timezone=tz), id="evening_preview", replace_existing=True)
    scheduler.add_job(tick_due, IntervalTrigger(minutes=1), id="due_tick", replace_existing=True)
    scheduler.start()
    _started = True
    log_activity("system", "scheduler_started", "daily tasks + lessons + 11pm preview + due tick")


def reload_scheduler() -> None:
    if not _started:
        start_scheduler()
        return
    settings = load_settings()
    tz = ZoneInfo(settings.get("timezone", "Asia/Kolkata"))
    reminder_h, reminder_m = _hhmm(settings["schedule"]["dailyReminderTime"])
    lesson_h, lesson_m = _hhmm(settings["schedule"]["dailyLessonTime"])
    preview_h, preview_m = _hhmm(settings["schedule"].get("eveningPreviewTime") or "23:00")
    scheduler.reschedule_job("daily_tasks", trigger=CronTrigger(hour=reminder_h, minute=reminder_m, timezone=tz))
    scheduler.reschedule_job("daily_lesson", trigger=CronTrigger(hour=lesson_h, minute=lesson_m, timezone=tz))
    scheduler.add_job(
        send_tomorrow_preview,
        CronTrigger(hour=preview_h, minute=preview_m, timezone=tz),
        id="evening_preview",
        replace_existing=True,
    )


def send_daily_tasks() -> None:
    db = SessionLocal()
    try:
        open_tasks = db.query(Task).filter(Task.status == "open").order_by(Task.priority.desc(), Task.due_at.asc()).all()
        if not open_tasks:
            send_whatsapp("Daily briefing: no open tasks. Nice — inbox is clear.")
            return
        lines = ["Good morning. Here are today's open tasks:"]
        for task in open_tasks[:20]:
            due = task.due_at.strftime("%d %b %H:%M") if task.due_at else "no due date"
            lines.append(f"• {task.title} ({task.priority}, {due})")
        body = "\n".join(lines)
        send_whatsapp(body)
        notify_desktop("Daily tasks", f"{len(open_tasks)} open task(s)")
        log_activity("reminders", "daily_digest", f"{len(open_tasks)} tasks")
    finally:
        db.close()


def send_tomorrow_preview() -> None:
    tz = ZoneInfo(load_settings().get("timezone", "Asia/Kolkata"))
    tomorrow = datetime.now(tz).date() + timedelta(days=1)
    items = _tomorrow_items(tomorrow, tz)
    heading = tomorrow.strftime("%A, %d %b")
    if not items:
        body = f"Tomorrow ({heading}): no reminders scheduled."
    else:
        lines = [f"Tomorrow ({heading}) — {len(items)} reminder(s):"]
        for stamp, title in items:
            lines.append(f"• {stamp}  {title}")
        body = "\n".join(lines)
    send_whatsapp(body)
    notify_desktop("Tomorrow's reminders", heading)
    log_activity("reminders", "evening_preview", f"{len(items)} for {tomorrow.isoformat()}")


def _tomorrow_items(day, tz) -> list[tuple[str, str]]:
    start = datetime.combine(day, datetime.min.time(), tzinfo=tz)
    end = start + timedelta(days=1)
    weekday = day.weekday()
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    db = SessionLocal()
    try:
        once = (
            db.query(Reminder)
            .filter(Reminder.enabled.is_(True), Reminder.kind == "once", Reminder.run_at != None)
            .all()
        )
        for item in once:
            if (item.title or "").startswith("In 30 min:"):
                continue
            when = _as_local(item.run_at, tz)
            if start <= when < end:
                _push_item(out, seen, when.strftime("%I:%M %p"), item.title)
        for item in db.query(Reminder).filter(Reminder.enabled.is_(True), Reminder.kind == "daily").all():
            _push_item(out, seen, item.time_of_day or "all day", item.title)
        for item in db.query(Reminder).filter(Reminder.enabled.is_(True), Reminder.kind == "weekly").all():
            if item.weekday == weekday:
                _push_item(out, seen, item.time_of_day or "all day", item.title)
        for item in db.query(MeetingReminder).filter(MeetingReminder.sent.is_(False)).all():
            when = _as_local(item.remind_at, tz)
            if start <= when < end:
                _push_item(out, seen, when.strftime("%I:%M %p"), item.title)
    finally:
        db.close()
    out.sort(key=lambda row: _clock_sort(row[0]))
    return out


def _clock_sort(stamp: str) -> tuple[int, int]:
    text = (stamp or "").strip()
    for fmt in ("%I:%M %p", "%H:%M"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.hour, parsed.minute
        except ValueError:
            continue
    return 99, 0


def _push_item(out: list[tuple[str, str]], seen: set[tuple[str, str]], stamp: str, title: str) -> None:
    key = (stamp, (title or "").strip().lower())
    if not title or key in seen:
        return
    seen.add(key)
    out.append((stamp, title.strip()))


def _as_local(value: datetime | None, tz) -> datetime:
    utc = _as_utc(value)
    return utc.astimezone(tz)


def tick_due() -> None:
    from .runtime import assistants_enabled

    if not assistants_enabled:
        return
    now = utcnow()
    db = SessionLocal()
    try:
        due_reminders = (
            db.query(Reminder)
            .filter(Reminder.enabled.is_(True), Reminder.kind == "once", Reminder.run_at != None, Reminder.last_sent_at == None)
            .all()
        )
        for item in due_reminders:
            if item.run_at and _as_utc(item.run_at) <= now:
                _fire_reminder(item)
                item.last_sent_at = now
                item.enabled = False
        daily = db.query(Reminder).filter(Reminder.enabled.is_(True), Reminder.kind == "daily").all()
        tz = ZoneInfo(load_settings().get("timezone", "Asia/Kolkata"))
        local_now = datetime.now(tz)
        hhmm = local_now.strftime("%H:%M")
        for item in daily:
            if item.time_of_day == hhmm and _not_sent_today(item.last_sent_at, now):
                _fire_reminder(item)
                item.last_sent_at = now
        weekly = db.query(Reminder).filter(Reminder.enabled.is_(True), Reminder.kind == "weekly").all()
        for item in weekly:
            if item.weekday == local_now.weekday() and item.time_of_day == hhmm and _not_sent_today(item.last_sent_at, now):
                _fire_reminder(item)
                item.last_sent_at = now
        meetings = db.query(MeetingReminder).filter(MeetingReminder.sent.is_(False)).all()
        for item in meetings:
            if _as_utc(item.remind_at) > now:
                continue
            send_whatsapp(f"Meeting reminder: {item.title}\n{item.message}")
            notify_desktop("Meeting reminder", item.title)
            item.sent = True
            log_activity("meetings", "reminder_sent", item.title)
        db.commit()
    finally:
        db.close()


def _fire_reminder(item: Reminder) -> None:
    title = item.title or "Reminder"
    body = (item.message or "").strip()
    if body and body.split("\n", 1)[0] != title:
        text = f"Reminder: {title}\n{body}"
    else:
        text = f"Reminder: {title}"
    send_whatsapp(text)
    notify_desktop("Reminder", title)
    log_activity("reminders", "fired", title)


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        tz = ZoneInfo(load_settings().get("timezone", "Asia/Kolkata"))
        return value.replace(tzinfo=tz).astimezone(timezone.utc)
    return value.astimezone(timezone.utc)


def _not_sent_today(last, now) -> bool:
    if last is None:
        return True
    return last.date() != now.date()


def _hhmm(value: str) -> tuple[int, int]:
    parts = (value or "09:00").split(":")
    return int(parts[0]), int(parts[1] if len(parts) > 1 else 0)
