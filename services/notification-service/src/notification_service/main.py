"""Notification Service — reminders, challenge updates and milestone messages."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from datetime import datetime
from functools import lru_cache
from typing import Any, Literal
from zoneinfo import available_timezones

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update

from notification_service.handlers import register_handlers
from notification_service.models import Base, Notification, Preference
from teampulse_common.app import create_service_app
from teampulse_common.db import SessionDep, utcnow
from teampulse_common.errors import NotFoundError
from teampulse_common.events import EventEnvelope, EventPublisher, EventType
from teampulse_common.events.contracts import ReminderTick
from teampulse_common.pagination import Page, PageDep
from teampulse_common.security import CurrentPrincipal, JwtVerifier
from teampulse_common.settings import ServiceSettings

logger = logging.getLogger("notification")


class Settings(ServiceSettings):
    service_name: str = "notification-service"
    # internal: a local loop emits reminder ticks; external: EventBridge Scheduler does (AWS).
    reminder_scheduler: Literal["internal", "external"] = "internal"
    reminder_interval_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    title: str
    body: str
    data: dict[str, Any]
    is_read: bool
    created_at: datetime


class PreferencesIO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reminders_enabled: bool = True
    reminder_hour: int = Field(default=9, ge=0, le=23, description="Local hour in `timezone`")
    timezone: str = "UTC"
    email_enabled: bool = False

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        if value != "UTC" and value not in _timezones():
            raise ValueError("unknown IANA timezone")
        return value


@lru_cache(maxsize=1)
def _timezones() -> frozenset[str]:
    return frozenset(available_timezones())


router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationOut], summary="My notifications (newest first)")
async def list_notifications(
    principal: CurrentPrincipal, session: SessionDep, page: PageDep, unread_only: bool = False
) -> Page[NotificationOut]:
    stmt = select(Notification).where(Notification.user_id == principal.user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        await session.scalars(
            stmt.order_by(Notification.created_at.desc()).offset(page.offset).limit(page.size)
        )
    ).all()
    return Page(
        items=[NotificationOut.model_validate(r) for r in rows], total=total, page=page.page, size=page.size
    )


@router.get("/unread-count", summary="Unread badge counter")
async def unread_count(principal: CurrentPrincipal, session: SessionDep) -> dict[str, int]:
    count = await session.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == principal.user_id, Notification.is_read.is_(False)
        )
    )
    return {"count": count or 0}


@router.post("/read-all", summary="Mark everything as read")
async def read_all(principal: CurrentPrincipal, session: SessionDep) -> dict[str, int]:
    result = await session.execute(
        update(Notification)
        .where(Notification.user_id == principal.user_id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=utcnow())
    )
    await session.commit()
    return {"updated": result.rowcount or 0}  # type: ignore[attr-defined]


@router.get("/preferences", response_model=PreferencesIO, summary="My reminder preferences")
async def get_preferences(principal: CurrentPrincipal, session: SessionDep) -> PreferencesIO:
    prefs = await session.get(Preference, principal.user_id)
    return PreferencesIO.model_validate(prefs) if prefs else PreferencesIO()


@router.put("/preferences", response_model=PreferencesIO, summary="Update my reminder preferences")
async def put_preferences(
    body: PreferencesIO, principal: CurrentPrincipal, session: SessionDep
) -> PreferencesIO:
    prefs = await session.get(Preference, principal.user_id)
    if prefs is None:
        prefs = Preference(user_id=principal.user_id)
        session.add(prefs)
    for field, value in body.model_dump().items():
        setattr(prefs, field, value)
    await session.commit()
    return PreferencesIO.model_validate(prefs)


@router.post("/{notification_id}/read", response_model=NotificationOut, summary="Mark one as read")
async def mark_read(
    notification_id: uuid.UUID, principal: CurrentPrincipal, session: SessionDep
) -> NotificationOut:
    notification = await session.get(Notification, notification_id)
    if notification is None or notification.user_id != principal.user_id:
        raise NotFoundError("Notification not found")
    if not notification.is_read:
        notification.is_read, notification.read_at = True, utcnow()
        await session.commit()
    return NotificationOut.model_validate(notification)


def create_app(
    settings: Settings | None = None,
    *,
    publisher: EventPublisher | None = None,
    verifier: JwtVerifier | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    state: dict[str, asyncio.Task[None]] = {}

    async def _scheduler(app: FastAPI) -> None:
        while True:
            await asyncio.sleep(settings.reminder_interval_seconds)
            tick = EventEnvelope.create(
                EventType.REMINDER_TICK, "scheduler", ReminderTick(hour_utc=utcnow().hour)
            )
            try:
                await app.state.dispatcher.dispatch(tick)
            except Exception:
                logger.exception("reminders.tick_failed")

    async def _start(app: FastAPI) -> None:
        if settings.reminder_scheduler == "internal":
            state["scheduler"] = asyncio.create_task(_scheduler(app), name="reminder-scheduler")

    async def _stop(app: FastAPI) -> None:
        if task := state.get("scheduler"):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    return create_service_app(
        settings,
        title="TeamPulse Notification Service",
        description="In-app notifications (+ simulated e-mail via structured logs) for reminders, "
        "challenge updates, streak milestones and badges.",
        routers=[router],
        metadata=[Base.metadata],
        default_db_name="notifications",
        register_handlers=register_handlers,
        publisher=publisher,
        verifier=verifier,
        on_startup=[_start],
        on_shutdown=[_stop],
        openapi_tags=[{"name": "notifications", "description": "Inbox and reminder preferences"}],
    )
