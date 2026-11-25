from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from teampulse_common.events.contracts import BadgeCriterion, Category
from teampulse_common.validation import forbid_null

MAX_DURATION_DAYS = 90


class ChallengeStatus(StrEnum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    COMPLETED = "completed"


def status_for(starts_on: date, ends_on: date, today: date) -> ChallengeStatus:
    if today < starts_on:
        return ChallengeStatus.UPCOMING
    if today > ends_on:
        return ChallengeStatus.COMPLETED
    return ChallengeStatus.ACTIVE


class ChallengeCreate(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    category: Category | None = Field(default=None, description="Restrict to one activity type (null = any)")
    team_id: uuid.UUID | None = Field(
        default=None, description="Team-only challenge (null = organisation-wide)"
    )
    starts_on: date
    ends_on: date
    target_count: int = Field(default=10, ge=1, le=365)

    @model_validator(mode="after")
    def _window(self) -> ChallengeCreate:
        if self.ends_on < self.starts_on:
            raise ValueError("ends_on must be on or after starts_on")
        if self.ends_on - self.starts_on > timedelta(days=MAX_DURATION_DAYS):
            raise ValueError(f"challenges can last at most {MAX_DURATION_DAYS} days")
        return self


class ChallengeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    ends_on: date | None = None
    target_count: int | None = Field(default=None, ge=1, le=365)

    _no_nulls = forbid_null("title", "ends_on", "target_count")  # description may be cleared


class JoinRequest(BaseModel):
    show_on_leaderboard: bool = True


class ParticipationUpdate(BaseModel):
    show_on_leaderboard: bool


class ChallengeOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    category: Category | None
    team_id: uuid.UUID | None
    team_name: str | None
    starts_on: date
    ends_on: date
    target_count: int
    status: ChallengeStatus
    created_by: uuid.UUID
    created_at: datetime
    participant_count: int
    joined: bool
    my_score: int | None
    my_goal_reached: bool
    show_on_leaderboard: bool | None


class LeaderboardEntry(BaseModel):
    rank: int
    display_name: str
    team_name: str | None
    score: int
    goal_reached: bool
    is_me: bool


class TeamStanding(BaseModel):
    rank: int
    team_id: uuid.UUID | None
    team_name: str
    participants: int
    total_score: int
    average_score: float


class LeaderboardOut(BaseModel):
    challenge_id: uuid.UUID
    my_rank: int | None
    individuals: list[LeaderboardEntry]
    teams: list[TeamStanding]


class BadgeRuleIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    description: str = Field(default="", max_length=200)
    icon: str = Field(default="🏅", max_length=8)
    criterion: BadgeCriterion
    category: Category | None = None
    threshold: int = Field(ge=1, le=10_000)
    is_active: bool = True

    @model_validator(mode="after")
    def _category_rule(self) -> BadgeRuleIn:
        if self.criterion is BadgeCriterion.CATEGORY_COMPLETIONS and self.category is None:
            raise ValueError("category_completions rules need a category")
        return self
