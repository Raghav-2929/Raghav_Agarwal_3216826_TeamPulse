"""Integration-event contracts (the published language between bounded contexts).

Payloads deliberately carry identifiers, categories and counts only. Free text a user typed (habit
titles, notes) never leaves the owning service, which keeps wellness details out of the event bus,
the analytics store and CloudWatch logs.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EventType(StrEnum):
    USER_REGISTERED = "user.registered"
    USER_UPDATED = "user.updated"
    ACTIVITY_COMPLETED = "activity.completed"
    PROGRESS_UPDATED = "progress.updated"
    STREAK_MILESTONE = "streak.milestone"
    BADGE_AWARDED = "badge.awarded"
    BADGE_RULES_CHANGED = "badge_rules.changed"
    CHALLENGE_CREATED = "challenge.created"
    CHALLENGE_JOINED = "challenge.joined"
    CHALLENGE_GOAL_REACHED = "challenge.goal_reached"
    REMINDER_TICK = "reminder.tick"


class Category(StrEnum):
    FITNESS = "fitness"
    MINDFULNESS = "mindfulness"
    NUTRITION = "nutrition"
    SLEEP = "sleep"
    HYDRATION = "hydration"
    LEARNING = "learning"


class Frequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"


class BadgeCriterion(StrEnum):
    STREAK_DAYS = "streak_days"
    TOTAL_COMPLETIONS = "total_completions"
    CATEGORY_COMPLETIONS = "category_completions"


class UserRegistered(BaseModel):
    user_id: uuid.UUID
    team_id: uuid.UUID | None
    role: str
    display_name: str
    email: str


class UserUpdated(UserRegistered):
    is_active: bool = True


class ActivityCompleted(BaseModel):
    activity_id: uuid.UUID
    user_id: uuid.UUID
    team_id: uuid.UUID | None
    habit_id: uuid.UUID
    category: Category
    frequency: Frequency
    target_per_period: int = Field(ge=1, le=7)
    value: float = 1.0
    completed_on: date
    occurred_at: datetime


class ProgressUpdated(BaseModel):
    activity_id: uuid.UUID
    user_id: uuid.UUID
    team_id: uuid.UUID | None
    habit_id: uuid.UUID
    category: Category
    completed_on: date
    value: float = 1.0
    current_streak: int = 0


class StreakMilestone(BaseModel):
    user_id: uuid.UUID
    habit_id: uuid.UUID
    streak: int
    frequency: Frequency


class BadgeAwarded(BaseModel):
    user_id: uuid.UUID
    code: str
    name: str
    description: str
    icon: str


class BadgeRule(BaseModel):
    code: str = Field(pattern=r"^[a-z0-9_]{3,40}$")
    name: str = Field(min_length=2, max_length=60)
    description: str = Field(default="", max_length=200)
    icon: str = Field(default="🏅", max_length=8)
    criterion: BadgeCriterion
    category: Category | None = None
    threshold: int = Field(ge=1, le=10_000)
    is_active: bool = True


class BadgeRulesChanged(BaseModel):
    rules: list[BadgeRule]


class ChallengeCreated(BaseModel):
    challenge_id: uuid.UUID
    title: str
    team_id: uuid.UUID | None
    starts_on: date
    ends_on: date
    created_by: uuid.UUID


class ChallengeJoined(BaseModel):
    challenge_id: uuid.UUID
    title: str
    user_id: uuid.UUID


class ChallengeGoalReached(BaseModel):
    challenge_id: uuid.UUID
    title: str
    user_id: uuid.UUID
    score: int


class ReminderTick(BaseModel):
    hour_utc: int | None = None


DEFAULT_BADGE_RULES: list[BadgeRule] = [
    BadgeRule(
        code="first_step",
        name="First Step",
        description="Logged your very first activity",
        icon="👣",
        criterion=BadgeCriterion.TOTAL_COMPLETIONS,
        threshold=1,
    ),
    BadgeRule(
        code="habit_builder",
        name="Habit Builder",
        description="10 activities completed",
        icon="🧱",
        criterion=BadgeCriterion.TOTAL_COMPLETIONS,
        threshold=10,
    ),
    BadgeRule(
        code="half_century",
        name="Half Century",
        description="50 activities completed",
        icon="🏆",
        criterion=BadgeCriterion.TOTAL_COMPLETIONS,
        threshold=50,
    ),
    BadgeRule(
        code="on_a_roll",
        name="On a Roll",
        description="3-period streak on any habit",
        icon="⚡",
        criterion=BadgeCriterion.STREAK_DAYS,
        threshold=3,
    ),
    BadgeRule(
        code="week_warrior",
        name="Week Warrior",
        description="7-period streak on any habit",
        icon="🔥",
        criterion=BadgeCriterion.STREAK_DAYS,
        threshold=7,
    ),
    BadgeRule(
        code="unstoppable",
        name="Unstoppable",
        description="30-period streak on any habit",
        icon="🚀",
        criterion=BadgeCriterion.STREAK_DAYS,
        threshold=30,
    ),
    BadgeRule(
        code="zen_master",
        name="Zen Master",
        description="20 mindfulness sessions",
        icon="🧘",
        criterion=BadgeCriterion.CATEGORY_COMPLETIONS,
        category=Category.MINDFULNESS,
        threshold=20,
    ),
    BadgeRule(
        code="hydration_hero",
        name="Hydration Hero",
        description="20 hydration check-ins",
        icon="💧",
        criterion=BadgeCriterion.CATEGORY_COMPLETIONS,
        category=Category.HYDRATION,
        threshold=20,
    ),
    BadgeRule(
        code="move_it",
        name="Move It",
        description="15 fitness activities",
        icon="🏃",
        criterion=BadgeCriterion.CATEGORY_COMPLETIONS,
        category=Category.FITNESS,
        threshold=15,
    ),
]
