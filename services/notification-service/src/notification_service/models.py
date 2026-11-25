from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, Index, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from teampulse_common.db import UTCDateTime, new_metadata, utcnow


class Base(DeclarativeBase):
    metadata = new_metadata()


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_unread", "user_id", "is_read", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(140))
    body: Mapped[str] = mapped_column(String(500))
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Preference(Base):
    __tablename__ = "preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    reminders_enabled: Mapped[bool] = mapped_column(default=True)
    reminder_hour: Mapped[int] = mapped_column(default=9)  # local hour in `timezone`
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    email_enabled: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class Contact(Base):
    """Local projection of identity + activity events — lets reminders target only people who have
    not logged anything today, without a synchronous call to another service."""

    __tablename__ = "contacts"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    team_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="employee")
    is_active: Mapped[bool] = mapped_column(default=True)
    last_activity_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_reminded_on: Mapped[date | None] = mapped_column(Date, nullable=True)
