from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Index, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from teampulse_common.db import UTCDateTime, new_metadata, utcnow


class Base(DeclarativeBase):
    metadata = new_metadata()


class Habit(Base):
    __tablename__ = "habits"
    __table_args__ = (Index("ix_habits_team_visibility", "team_id", "visibility"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    owner_name: Mapped[str] = mapped_column(String(120))  # denormalised, refreshed from user.updated
    team_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    title: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str] = mapped_column(String(20), index=True)
    frequency: Mapped[str] = mapped_column(String(10))
    target_per_period: Mapped[int] = mapped_column(default=1)
    visibility: Mapped[str] = mapped_column(String(10), default="private")
    color: Mapped[str] = mapped_column(String(7), default="#4F46E5")
    is_archived: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
