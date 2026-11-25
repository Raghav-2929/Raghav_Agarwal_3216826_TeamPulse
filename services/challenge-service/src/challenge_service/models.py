from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from teampulse_common.db import UTCDateTime, new_metadata, utcnow


class Base(DeclarativeBase):
    metadata = new_metadata()


class Challenge(Base):
    __tablename__ = "challenges"
    __table_args__ = (Index("ix_challenges_window", "starts_on", "ends_on"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    category: Mapped[str | None] = mapped_column(String(20), nullable=True)  # None = any activity type
    team_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)  # None = org-wide
    team_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    target_count: Mapped[int] = mapped_column(default=10)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (UniqueConstraint("challenge_id", "user_id", name="uq_participant_challenge_user"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("challenges.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    team_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    team_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    display_name: Mapped[str] = mapped_column(String(120))
    show_on_leaderboard: Mapped[bool] = mapped_column(default=True)
    score: Mapped[int] = mapped_column(default=0)
    goal_reached_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_progress_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class BadgeRuleRow(Base):
    __tablename__ = "badge_rules"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(String(200), default="")
    icon: Mapped[str] = mapped_column(String(8), default="🏅")
    criterion: Mapped[str] = mapped_column(String(30))
    category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    threshold: Mapped[int] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
