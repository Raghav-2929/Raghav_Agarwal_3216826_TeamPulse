"""Activity logging (command side). Streaks/badges/analytics are computed asynchronously by the
streak processor (AWS Lambda) from the ``activity.completed`` event."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from event_tracking_service.habits_client import HabitLookup
from event_tracking_service.models import Activity
from teampulse_common.db import utcnow
from teampulse_common.errors import ConflictError, NotFoundError, UnprocessableError
from teampulse_common.events import EventEnvelope, EventType, enqueue
from teampulse_common.events.contracts import ActivityCompleted, Category
from teampulse_common.pagination import Page, PageParams
from teampulse_common.security import Principal

SOURCE = "event-tracking-service"


class ActivityCreate(BaseModel):
    habit_id: uuid.UUID
    completed_on: date | None = Field(default=None, description="Defaults to today (UTC)")
    value: float = Field(default=1.0, gt=0, le=10_000, description="e.g. minutes, glasses, km")
    note: str | None = Field(default=None, max_length=280, description="Private note; never shared")


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    habit_id: uuid.UUID
    category: Category
    value: float
    note: str | None
    completed_on: date
    occurred_at: datetime
    created_at: datetime


class ActivityService:
    def __init__(
        self,
        session: AsyncSession,
        habits: HabitLookup,
        *,
        backfill_days: int,
        on_commit: Callable[[], None] = lambda: None,
        today: Callable[[], date] | None = None,
    ) -> None:
        self.session = session
        self.habits = habits
        self.backfill_days = backfill_days
        self._on_commit = on_commit
        self._today = today or (lambda: utcnow().date())

    def _validate_date(self, completed_on: date) -> None:
        today = self._today()
        # +1 day tolerance: an employee east of UTC may already be on "tomorrow".
        if completed_on > today + timedelta(days=1):
            raise UnprocessableError("Activities cannot be logged in the future", code="invalid_date")
        if completed_on < today - timedelta(days=self.backfill_days):
            raise UnprocessableError(
                f"Activities can be back-filled for at most {self.backfill_days} days", code="invalid_date"
            )

    async def log(self, principal: Principal, body: ActivityCreate) -> ActivityOut:
        completed_on = body.completed_on or self._today()
        self._validate_date(completed_on)

        habit = await self.habits.get_habit(body.habit_id, principal.token)
        if habit is None or habit.owner_id != principal.user_id:
            raise NotFoundError("Habit not found")
        if habit.is_archived:
            raise UnprocessableError("Cannot log activity for an archived habit", code="habit_archived")

        duplicate = await self.session.scalar(
            select(Activity.id).where(
                Activity.user_id == principal.user_id,
                Activity.habit_id == habit.id,
                Activity.completed_on == completed_on,
            )
        )
        if duplicate:
            raise ConflictError("This habit is already logged for that day", code="already_logged")

        activity = Activity(
            user_id=principal.user_id,
            team_id=principal.team_id,
            habit_id=habit.id,
            category=habit.category.value,
            value=body.value,
            note=body.note,
            completed_on=completed_on,
            occurred_at=utcnow(),
        )
        self.session.add(activity)
        try:
            # flush() sends the INSERT, so a second click at the same moment can already fail here on
            # the unique (user, habit, day) constraint, not only at commit().
            await self.session.flush()
            enqueue(
                self.session,
                EventEnvelope.create(
                    EventType.ACTIVITY_COMPLETED,
                    SOURCE,
                    ActivityCompleted(
                        activity_id=activity.id,
                        user_id=principal.user_id,
                        team_id=principal.team_id,
                        habit_id=habit.id,
                        category=habit.category,
                        frequency=habit.frequency,
                        target_per_period=habit.target_per_period,
                        value=body.value,
                        completed_on=completed_on,
                        occurred_at=activity.occurred_at,
                    ),
                    subject=f"user:{principal.user_id}",
                ),
            )
            await self.session.commit()
        except IntegrityError as exc:  # concurrent double-submit
            await self.session.rollback()
            raise ConflictError("This habit is already logged for that day", code="already_logged") from exc
        self._on_commit()
        return ActivityOut.model_validate(activity)

    async def list(
        self,
        principal: Principal,
        *,
        habit_id: uuid.UUID | None,
        category: Category | None,
        date_from: date | None,
        date_to: date | None,
        page: PageParams,
    ) -> Page[ActivityOut]:
        stmt = select(Activity).where(Activity.user_id == principal.user_id)
        if habit_id:
            stmt = stmt.where(Activity.habit_id == habit_id)
        if category:
            stmt = stmt.where(Activity.category == category.value)
        if date_from:
            stmt = stmt.where(Activity.completed_on >= date_from)
        if date_to:
            stmt = stmt.where(Activity.completed_on <= date_to)
        total = await self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = (
            await self.session.scalars(
                stmt.order_by(Activity.completed_on.desc(), Activity.created_at.desc())
                .offset(page.offset)
                .limit(page.size)
            )
        ).all()
        return Page(
            items=[ActivityOut.model_validate(r) for r in rows], total=total, page=page.page, size=page.size
        )
