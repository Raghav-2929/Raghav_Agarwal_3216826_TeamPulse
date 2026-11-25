from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date, timedelta

import httpx
import pytest

from event_tracking_service.habits_client import HabitSnapshot, HttpHabitLookup
from event_tracking_service.main import Settings, create_app
from teampulse_common.db import utcnow
from teampulse_common.events import InMemoryEventBus
from teampulse_common.events.contracts import Category, Frequency
from teampulse_common.resilience import CircuitBreaker
from teampulse_common.testing import (
    bearer,
    flush_outbox,
    make_token,
    running_client,
    sqlite_url,
    verifier_for_tests,
)

TEAM = uuid.uuid4()
ALICE, BEN = uuid.uuid4(), uuid.uuid4()
ALICE_H = bearer(make_token(ALICE, team_id=TEAM, name="Alice"))


class FakeHabits:
    def __init__(self) -> None:
        self.habits: dict[uuid.UUID, HabitSnapshot] = {}

    def add(
        self, owner: uuid.UUID, *, archived: bool = False, category: Category = Category.FITNESS
    ) -> uuid.UUID:
        hid = uuid.uuid4()
        self.habits[hid] = HabitSnapshot(hid, owner, category, Frequency.DAILY, 1, archived)
        return hid

    async def get_habit(self, habit_id, token):
        return self.habits.get(habit_id)

    async def aclose(self) -> None:
        return None


@pytest.fixture
def habits() -> FakeHabits:
    return FakeHabits()


@pytest.fixture
def bus() -> InMemoryEventBus:
    return InMemoryEventBus()


def settings_for(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=sqlite_url(tmp_path),
        data_dir=str(tmp_path),
        log_level="WARNING",
    )


@pytest.fixture
async def client(tmp_path, habits, bus) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(
        settings_for(tmp_path), publisher=bus, verifier=verifier_for_tests(), habit_lookup=habits
    )
    async with running_client(app) as c:
        c.app = app  # type: ignore[attr-defined]
        yield c


async def test_logging_an_activity_publishes_activity_completed_without_private_note(client, habits, bus):
    hid = habits.add(ALICE)
    resp = await client.post(
        "/api/v1/activities",
        headers=ALICE_H,
        json={"habit_id": str(hid), "value": 30, "note": "knee felt sore"},
    )
    assert resp.status_code == 201
    assert resp.json()["note"] == "knee felt sore"  # the owner sees it…

    await flush_outbox(client.app)
    [event] = bus.of_type("activity.completed")
    assert event.data["habit_id"] == str(hid)
    assert event.data["team_id"] == str(TEAM)
    assert event.data["frequency"] == "daily"
    assert "note" not in event.data  # …but it never leaves the service
    assert event.source == "event-tracking-service"


async def test_duplicate_completion_same_day_is_rejected_and_not_republished(client, habits, bus):
    hid = habits.add(ALICE)
    first = await client.post("/api/v1/activities", headers=ALICE_H, json={"habit_id": str(hid)})
    second = await client.post("/api/v1/activities", headers=ALICE_H, json={"habit_id": str(hid)})
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["code"] == "already_logged"
    await flush_outbox(client.app)
    assert len(bus.of_type("activity.completed")) == 1


async def test_double_click_race_returns_409_not_500(client, habits, bus, monkeypatch):
    """Two clicks at the same moment: both pass the "already logged?" check before either saves.

    The test makes the check miss for the second request (as in a real race), so the database's
    unique constraint stops it during flush(). The answer must still be 409, and only one event goes out.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    hid = habits.add(ALICE)
    assert (
        await client.post("/api/v1/activities", headers=ALICE_H, json={"habit_id": str(hid)})
    ).status_code == 201

    original_scalar = AsyncSession.scalar

    async def check_misses(self, statement, *args, **kwargs):
        sql = str(statement)
        if "FROM activities" in sql and "completed_on" in sql and "count(" not in sql:
            return None  # the other request has not committed yet
        return await original_scalar(self, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "scalar", check_misses)
    second = await client.post("/api/v1/activities", headers=ALICE_H, json={"habit_id": str(hid)})
    assert second.status_code == 409
    assert second.json()["code"] == "already_logged"
    monkeypatch.undo()
    await flush_outbox(client.app)
    assert len(bus.of_type("activity.completed")) == 1


@pytest.mark.parametrize(("offset", "status"), [(0, 201), (-7, 201), (-8, 422), (1, 201), (2, 422)])
async def test_date_window(client, habits, offset, status):
    hid = habits.add(ALICE)
    day = utcnow().date() + timedelta(days=offset)
    resp = await client.post(
        "/api/v1/activities", headers=ALICE_H, json={"habit_id": str(hid), "completed_on": day.isoformat()}
    )
    assert resp.status_code == status


async def test_cannot_log_someone_elses_or_archived_habit(client, habits):
    bens = habits.add(BEN)
    assert (
        await client.post("/api/v1/activities", headers=ALICE_H, json={"habit_id": str(bens)})
    ).status_code == 404
    archived = habits.add(ALICE, archived=True)
    resp = await client.post("/api/v1/activities", headers=ALICE_H, json={"habit_id": str(archived)})
    assert resp.status_code == 422
    assert resp.json()["code"] == "habit_archived"


async def test_history_is_private_and_filterable(client, habits):
    run, meditate = habits.add(ALICE), habits.add(ALICE, category=Category.MINDFULNESS)
    today = utcnow().date()
    for hid, day in [(run, today), (run, today - timedelta(days=1)), (meditate, today)]:
        await client.post(
            "/api/v1/activities",
            headers=ALICE_H,
            json={"habit_id": str(hid), "completed_on": day.isoformat()},
        )
    assert (await client.get("/api/v1/activities", headers=ALICE_H)).json()["total"] == 3
    assert (await client.get(f"/api/v1/activities?habit_id={run}", headers=ALICE_H)).json()["total"] == 2
    today_only = await client.get(f"/api/v1/activities?from={today}&to={today}", headers=ALICE_H)
    assert today_only.json()["total"] == 2
    assert (await client.get("/api/v1/activities?category=mindfulness", headers=ALICE_H)).json()["total"] == 1
    ben = bearer(make_token(BEN, team_id=TEAM))
    assert (await client.get("/api/v1/activities", headers=ben)).json()["total"] == 0


async def test_habit_service_outage_opens_circuit_and_fails_fast(tmp_path, bus):
    calls = {"n": 0}

    def failing(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("connection refused", request=request)

    breaker = CircuitBreaker("habit-service", failure_threshold=3, recovery_timeout=60)
    lookup = HttpHabitLookup("http://habit", transport=httpx.MockTransport(failing), breaker=breaker)
    app = create_app(
        settings_for(tmp_path), publisher=bus, verifier=verifier_for_tests(), habit_lookup=lookup
    )
    async with running_client(app) as client:
        body = {"habit_id": str(uuid.uuid4())}
        first = await client.post("/api/v1/activities", headers=ALICE_H, json=body)
        assert first.status_code == 503
        assert first.json()["code"] == "dependency_unavailable"
        assert breaker.state == "open"  # 1 attempt + 2 retries tripped the breaker
        before = calls["n"]
        second = await client.post("/api/v1/activities", headers=ALICE_H, json=body)
        assert second.status_code == 503
        assert "circuit open" in second.json()["detail"]
        assert calls["n"] == before  # fail fast: no network call while the circuit is open


async def test_completed_on_defaults_to_today(client, habits):
    hid = habits.add(ALICE)
    resp = await client.post("/api/v1/activities", headers=ALICE_H, json={"habit_id": str(hid)})
    assert date.fromisoformat(resp.json()["completed_on"]) == utcnow().date()
