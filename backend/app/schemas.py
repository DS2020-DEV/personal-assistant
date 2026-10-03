from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TaskIn(BaseModel):
    title: str
    description: str = ""
    status: str = "open"
    priority: str = "normal"
    due_at: datetime | None = None
    source: str = "dashboard"


class TaskOut(TaskIn):
    id: int
    created_at: datetime
    completed_at: datetime | None = None
    model_config = {"from_attributes": True}


class ReminderIn(BaseModel):
    title: str
    message: str = ""
    kind: Literal["once", "daily", "weekly"] = "once"
    run_at: datetime | None = None
    weekday: int | None = None
    time_of_day: str | None = None
    enabled: bool = True
    task_id: int | None = None


class ReminderOut(ReminderIn):
    id: int
    last_sent_at: datetime | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class LearningPlanIn(BaseModel):
    topic: str
    goal: str = ""
    daily_time: str = "09:00"
    days: int = Field(default=10, ge=3, le=30)


class LessonGenerateIn(BaseModel):
    send: bool = True


class MeetingIn(BaseModel):
    title: str = "Meeting"
    source: str = "dashboard"
    meeting_at: datetime | None = None


class MeetingReminderIn(BaseModel):
    title: str
    message: str = ""
    remind_at: datetime
    meeting_id: int | None = None


class InboxIn(BaseModel):
    text: str = ""
    media_path: str | None = None
    media_kind: str | None = None
    sender: str | None = None
    source: str = "whatsapp"
    deliver_reply: bool = True


class SettingsPatch(BaseModel):
    settings: dict[str, Any]
