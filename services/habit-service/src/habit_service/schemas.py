from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from teampulse_common.events.contracts import Category, Frequency
from teampulse_common.validation import forbid_null


class Visibility(StrEnum):
    PRIVATE = "private"
    TEAM = "team"


HEX_COLOR = r"^#[0-9A-Fa-f]{6}$"


def check_target(frequency: Frequency, target: int) -> None:
    if frequency is Frequency.DAILY and target != 1:
        raise ValueError("daily habits have target_per_period = 1")
    if frequency is Frequency.WEEKLY and not 1 <= target <= 7:
        raise ValueError("weekly habits need target_per_period between 1 and 7")


class HabitCreate(BaseModel):
    title: str = Field(min_length=3, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    category: Category
    frequency: Frequency = Frequency.DAILY
    target_per_period: int = Field(default=1, ge=1, le=7)
    visibility: Visibility = Visibility.PRIVATE
    color: str = Field(default="#4F46E5", pattern=HEX_COLOR)

    @model_validator(mode="after")
    def _target_matches_frequency(self) -> HabitCreate:
        check_target(self.frequency, self.target_per_period)
        return self


class HabitUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    category: Category | None = None
    frequency: Frequency | None = None
    target_per_period: int | None = Field(default=None, ge=1, le=7)
    visibility: Visibility | None = None
    color: str | None = Field(default=None, pattern=HEX_COLOR)
    is_archived: bool | None = None

    # Only the description may be cleared with null; the other fields always need a value.
    _no_nulls = forbid_null(
        "title", "category", "frequency", "target_per_period", "visibility", "color", "is_archived"
    )


class HabitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    owner_name: str
    team_id: uuid.UUID | None
    title: str
    description: str | None
    category: Category
    frequency: Frequency
    target_per_period: int
    visibility: Visibility
    color: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
