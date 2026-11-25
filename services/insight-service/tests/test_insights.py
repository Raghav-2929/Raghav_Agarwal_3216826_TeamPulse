"""Insight tests drive the *real* streak processor into a shared in-memory analytics table, exactly
like Lambda → DynamoDB → Insight in AWS."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from insight_service.main import Settings, create_app
from streak_processor.processor import StreakProcessor
from teampulse_common.analytics_store import MemoryAnalyticsStore
from teampulse_common.db import utcnow
from teampulse_common.events import EventEnvelope, InMemoryEventBus
from teampulse_common.events.contracts import ActivityCompleted, Category, Frequency
from teampulse_common.testing import bearer, make_token, running_client, verifier_for_tests

ENG, MKT = uuid.uuid4(), uuid.uuid4()
MEMBERS = [uuid.uuid4() for _ in range(4)]
MAYA, ADMIN = uuid.uuid4(), uuid.uuid4()
TODAY = utcnow().date()
maya = bearer(make_token(MAYA, role="manager", team_id=ENG, managed_team_ids=[ENG], name="Maya Patel"))


def member(i: int) -> dict[str, str]:
    return bearer(make_token(MEMBERS[i], team_id=ENG, name=f"Member {i}"))


@pytest.fixture
def store() -> MemoryAnalyticsStore:
    return MemoryAnalyticsStore()


@pytest.fixture
async def client(tmp_path, store) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(
        _env_file=None, environment="test", data_dir=str(tmp_path), log_level="WARNING", min_cohort_size=3
    )
    app = create_app(settings, store=store, verifier=verifier_for_tests())
    async with running_client(app) as c:
        yield c


async def complete(store, user, *, day, habit=None, category=Category.FITNESS, team=ENG):
    processor = StreakProcessor(store, InMemoryEventBus())
    await processor.handle(
        EventEnvelope.create(
            "activity.completed",
            "event-tracking-service",
            ActivityCompleted(
                activity_id=uuid.uuid4(),
                user_id=user,
                team_id=team,
                habit_id=habit or uuid.uuid4(),
                category=category,
                frequency=Frequency.DAILY,
                target_per_period=1,
                completed_on=day,
                occurred_at=datetime.now(UTC),
            ),
        )
    )


async def test_personal_insights_series_streaks_and_badges(client, store):
    habit = uuid.uuid4()
    for offset in (2, 1, 0):
        await complete(store, MEMBERS[0], day=TODAY - timedelta(days=offset), habit=habit)
    await complete(store, MEMBERS[0], day=TODAY, category=Category.HYDRATION)

    body = (
        await client.get(
            f"/api/v1/insights/me?from={TODAY - timedelta(days=6)}&to={TODAY}", headers=member(0)
        )
    ).json()
    assert body["from"] == (TODAY - timedelta(days=6)).isoformat()
    assert len(body["daily"]) == 7
    assert body["totals"] == {
        "completions": 4,
        "active_days": 3,
        "total_value": 4.0,
        "consistency_rate": 0.43,
    }
    assert {c["category"]: c["completions"] for c in body["by_category"]} == {"fitness": 3, "hydration": 1}
    streak = next(s for s in body["streaks"] if s["habit_id"] == str(habit))
    assert (streak["current"], streak["alive"]) == (3, True)
    assert {b["code"] for b in body["badges"]} == {"first_step", "on_a_roll"}

    fitness_only = (await client.get("/api/v1/insights/me?category=fitness", headers=member(0))).json()
    assert fitness_only["totals"]["completions"] == 3


async def test_broken_streak_reports_zero_current_but_keeps_longest(client, store):
    habit = uuid.uuid4()
    for offset in (6, 5, 4):
        await complete(store, MEMBERS[1], day=TODAY - timedelta(days=offset), habit=habit)
    [streak] = (await client.get("/api/v1/insights/me/streaks", headers=member(1))).json()
    assert (streak["current"], streak["longest"], streak["alive"]) == (0, 3, False)


async def test_users_only_ever_see_their_own_data(client, store):
    await complete(store, MEMBERS[0], day=TODAY)
    other = (await client.get("/api/v1/insights/me", headers=member(1))).json()
    assert other["totals"]["completions"] == 0
    assert other["badges"] == []


async def test_team_view_suppresses_days_below_k_and_never_lists_people(client, store):
    yesterday = TODAY - timedelta(days=1)
    for i in range(3):  # 3 members active today → released
        await complete(store, MEMBERS[i], day=TODAY)
    await complete(store, MEMBERS[0], day=yesterday)  # 1 member yesterday → suppressed
    await complete(store, MEMBERS[1], day=yesterday)

    resp = await client.get(f"/api/v1/insights/teams/{ENG}?from={yesterday}&to={TODAY}", headers=maya)
    assert resp.status_code == 200
    body = resp.json()
    by_date = {d["date"]: d for d in body["daily"]}
    assert by_date[TODAY.isoformat()] == {
        "date": TODAY.isoformat(),
        "completions": 3,
        "active_members": 3,
        "suppressed": False,
    }
    assert by_date[yesterday.isoformat()] == {
        "date": yesterday.isoformat(),
        "completions": None,
        "active_members": None,
        "suppressed": True,
    }
    assert body["totals"] == {
        "completions": 3,
        "active_days": 1,
        "suppressed_days": 1,
        "avg_active_members": 3.0,
    }
    flat = resp.text
    assert all(str(m) not in flat for m in MEMBERS)  # no member ids leak through the response


async def test_category_filter_applies_k_to_members_of_that_category(client, store):
    for i in range(3):
        await complete(store, MEMBERS[i], day=TODAY)
    await complete(store, MEMBERS[0], day=TODAY, category=Category.SLEEP)  # only one sleeper

    sleep = (await client.get(f"/api/v1/insights/teams/{ENG}?category=sleep", headers=maya)).json()
    today = next(d for d in sleep["daily"] if d["date"] == TODAY.isoformat())
    assert today["suppressed"] is True
    overall = (await client.get(f"/api/v1/insights/teams/{ENG}", headers=maya)).json()
    assert [c["category"] for c in overall["by_category"]] == ["fitness"]
    assert overall["suppressed_categories"] == ["sleep"]


async def test_team_view_authorisation(client):
    assert (await client.get(f"/api/v1/insights/teams/{ENG}", headers=member(0))).status_code == 403
    assert (await client.get(f"/api/v1/insights/teams/{MKT}", headers=maya)).status_code == 403
    admin = bearer(make_token(ADMIN, role="admin"))
    assert (await client.get(f"/api/v1/insights/teams/{MKT}", headers=admin)).status_code == 200


async def test_org_view_is_admin_only_and_aggregated(client, store):
    for i in range(3):
        await complete(store, MEMBERS[i], day=TODAY)
    await complete(store, uuid.uuid4(), day=TODAY, team=MKT)
    assert (await client.get("/api/v1/insights/org", headers=maya)).status_code == 403
    body = (await client.get("/api/v1/insights/org", headers=bearer(make_token(ADMIN, role="admin")))).json()
    summary = {t["team_id"]: t for t in body["teams"]}
    assert (summary[str(ENG)]["completions"], summary[str(ENG)]["active_days"]) == (3, 1)
    assert summary[str(MKT)]["completions"] == 0  # 1 member → suppressed
    assert summary[str(MKT)]["active_days"] == 0
    assert summary[str(MKT)]["suppressed_days"] == 30  # every day in the default 30-day range


@pytest.mark.parametrize("query", ["from=2026-02-01&to=2026-01-01", "from=2025-01-01&to=2026-01-01"])
async def test_invalid_ranges(client, query):
    resp = await client.get(f"/api/v1/insights/me?{query}", headers=member(0))
    assert resp.status_code == 422
    assert resp.json()["code"] == "invalid_range"
