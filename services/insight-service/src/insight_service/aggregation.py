"""Pure aggregation over analytics items, including the k-anonymity rule for team views.

Privacy rule (business goal: *managers view only aggregated trends*):

* A team-day bucket is released only when at least ``k`` distinct members contributed to it;
  otherwise the whole bucket — completions *and* member count — is suppressed (``null``), so nobody
  can infer an individual's activity. This includes days with *zero* activity: releasing "0" would
  tell a manager that every single member was inactive that day.
* With a category filter, ``k`` is checked against the members active *in that category*.
* The per-category breakdown only includes categories with at least ``k`` distinct members across the
  whole range; the rest are listed by name in ``suppressed_categories``.
"""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from teampulse_common.events.contracts import Category, Frequency
from teampulse_common.periods import is_alive

CATEGORIES = [c.value for c in Category]


def days_between(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _by_day(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["sk"].removeprefix("DAY#"): item for item in items}


# ---------------------------------------------------------------------------------------- models
class _Ranged(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: date = Field(alias="from")
    to: date


class DailyPoint(BaseModel):
    date: date
    completions: int
    value: float


class CategoryCount(BaseModel):
    category: Category
    completions: int


class PersonalTotals(BaseModel):
    completions: int
    active_days: int
    total_value: float
    consistency_rate: float


class StreakOut(BaseModel):
    habit_id: uuid.UUID
    frequency: Frequency
    current: int
    longest: int
    alive: bool
    last_period: str | None
    total_completions: int


class BadgeOut(BaseModel):
    code: str
    name: str
    description: str
    icon: str
    awarded_at: datetime


class PersonalInsights(_Ranged):
    totals: PersonalTotals
    daily: list[DailyPoint]
    by_category: list[CategoryCount]
    streaks: list[StreakOut]
    badges: list[BadgeOut]


class TeamDay(BaseModel):
    date: date
    completions: int | None
    active_members: int | None
    suppressed: bool


class TeamTotals(BaseModel):
    completions: int
    active_days: int
    suppressed_days: int
    avg_active_members: float


class TeamInsights(_Ranged):
    team_id: uuid.UUID
    min_cohort_size: int
    totals: TeamTotals
    daily: list[TeamDay]
    by_category: list[CategoryCount]
    suppressed_categories: list[Category]


class OrgTeamSummary(BaseModel):
    team_id: uuid.UUID
    completions: int
    active_days: int
    suppressed_days: int
    avg_active_members: float


class OrgInsights(_Ranged):
    min_cohort_size: int
    teams: list[OrgTeamSummary]


# ---------------------------------------------------------------------------------------- personal
def personal_series(
    items: Iterable[dict[str, Any]], start: date, end: date, category: Category | None
) -> tuple[list[DailyPoint], list[CategoryCount], PersonalTotals]:
    by_day = _by_day(items)
    daily: list[DailyPoint] = []
    per_category: Counter[str] = Counter()
    for day in days_between(start, end):
        item = by_day.get(day.isoformat(), {})
        if category:
            completions = int(item.get(f"cat_{category.value}", 0))
            value = float(completions)
        else:
            completions = int(item.get("completions", 0))
            value = float(item.get("value", 0))
        for cat in CATEGORIES:
            if not category or cat == category.value:
                per_category[cat] += int(item.get(f"cat_{cat}", 0))
        daily.append(DailyPoint(date=day, completions=completions, value=round(value, 2)))
    active_days = sum(1 for d in daily if d.completions > 0)
    totals = PersonalTotals(
        completions=sum(d.completions for d in daily),
        active_days=active_days,
        total_value=round(sum(d.value for d in daily), 2),
        consistency_rate=round(active_days / len(daily), 2) if daily else 0.0,
    )
    breakdown = [
        CategoryCount(category=Category(c), completions=n) for c, n in per_category.most_common() if n
    ]
    return daily, breakdown, totals


def streaks_from(items: Iterable[dict[str, Any]], today: date) -> list[StreakOut]:
    out = []
    for item in items:
        frequency = Frequency(item.get("frequency", "daily"))
        alive = is_alive(item.get("last_period"), frequency, today)
        out.append(
            StreakOut(
                habit_id=uuid.UUID(item["sk"].removeprefix("STREAK#")),
                frequency=frequency,
                current=int(item.get("current", 0)) if alive else 0,
                longest=int(item.get("longest", 0)),
                alive=alive,
                last_period=item.get("last_period"),
                total_completions=int(item.get("total", 0)),
            )
        )
    return sorted(out, key=lambda s: (-s.current, -s.longest))


def badges_from(items: Iterable[dict[str, Any]]) -> list[BadgeOut]:
    badges = [
        BadgeOut(
            code=i["code"],
            name=i["name"],
            description=i.get("description", ""),
            icon=i.get("icon", "🏅"),
            awarded_at=i["awarded_at"],
        )
        for i in items
    ]
    return sorted(badges, key=lambda b: b.awarded_at, reverse=True)


# ---------------------------------------------------------------------------------------- team
def team_series(
    items: Iterable[dict[str, Any]], start: date, end: date, k: int, category: Category | None
) -> tuple[list[TeamDay], TeamTotals, list[CategoryCount], list[Category]]:
    by_day = _by_day(items)
    members_key = f"active_users_cat_{category.value}" if category else "active_users"
    count_key = f"cat_{category.value}" if category else "completions"
    daily: list[TeamDay] = []
    category_members: dict[str, set[str]] = {c: set() for c in CATEGORIES}
    category_counts: Counter[str] = Counter()
    for day in days_between(start, end):
        item = by_day.get(day.isoformat(), {})
        members = len(item.get(members_key, ()))
        if members < k:
            daily.append(TeamDay(date=day, completions=None, active_members=None, suppressed=True))
            continue
        daily.append(
            TeamDay(
                date=day, completions=int(item.get(count_key, 0)), active_members=members, suppressed=False
            )
        )
        for cat in CATEGORIES:
            if category and cat != category.value:
                continue
            category_members[cat] |= set(item.get(f"active_users_cat_{cat}", ()))
            category_counts[cat] += int(item.get(f"cat_{cat}", 0))

    released = [d for d in daily if not d.suppressed]
    members_per_active_day = [d.active_members for d in released if d.active_members]
    totals = TeamTotals(
        completions=sum(d.completions for d in released if d.completions),
        active_days=len(members_per_active_day),
        suppressed_days=len(daily) - len(released),
        avg_active_members=round(sum(members_per_active_day) / len(members_per_active_day), 2)
        if members_per_active_day
        else 0.0,
    )
    by_category = [
        CategoryCount(category=Category(c), completions=n)
        for c, n in category_counts.most_common()
        if n and len(category_members[c]) >= k
    ]
    suppressed = [Category(c) for c, n in category_counts.items() if n and len(category_members[c]) < k]
    return daily, totals, by_category, suppressed
