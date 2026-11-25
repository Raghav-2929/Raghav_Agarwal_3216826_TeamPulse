from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from teampulse_common.db import UTCDateTime, new_metadata, utcnow


class Base(DeclarativeBase):
    metadata = new_metadata()


class Activity(Base):
    """One completion of one habit on one day (the unique constraint makes logging idempotent)."""

    __tablename__ = "activities"
    __table_args__ = (
        UniqueConstraint("user_id", "habit_id", "completed_on", name="uq_activity_user_habit_day"),
        Index("ix_activities_user_day", "user_id", "completed_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    team_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    habit_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    category: Mapped[str] = mapped_column(String(20))
    value: Mapped[float] = mapped_column(default=1.0)
    note: Mapped[str | None] = mapped_column(String(280), nullable=True)  # private; never leaves this service
    completed_on: Mapped[date] = mapped_column(Date)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
