from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from challenge_service.main import Settings, create_app
from teampulse_common.db import utcnow
from teampulse_common.events import EventEnvelope, InMemoryEventBus
from teampulse_common.events.contracts import Category, ProgressUpdated
from teampulse_common.testing import (
    bearer,
    flush_outbox,
    make_token,
    running_client,
    sqlite_url,
    verifier_for_tests,
)

ENG, MKT = uuid.uuid4(), uuid.uuid4()
MAYA, ALICE, BEN, CHLOE, EMMA, ADMIN = (uuid.uuid4() for _ in range(6))
TODAY = utcnow().date()

maya = bearer(
    make_token(
        MAYA, role="manager", name="Maya Patel", team_id=ENG, team_name="Engineering", managed_team_ids=[ENG]
    )
)
alice = bearer(make_token(ALICE, name="Alice Johnson", team_id=ENG, team_name="Engineering"))
ben = bearer(make_token(BEN, name="Ben Carter", team_id=ENG, team_name="Engineering"))
chloe = bearer(make_token(CHLOE, name="Chloe Kim", team_id=ENG, team_name="Engineering"))
emma = bearer(make_token(EMMA, name="Emma Davis", team_id=MKT, team_name="Marketing"))
admin = bearer(make_token(ADMIN, role="admin", name="Ada Admin"))


@pytest.fixture
def bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest.fixture
async def client(tmp_path, bus) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=sqlite_url(tmp_path),
        data_dir=str(tmp_path),
        log_level="WARNING",
    )
    app = create_app(settings, publisher=bus, verifier=verifier_for_tests())
    async with running_client(app) as c:
        c.app = app  # type: ignore[attr-defined]
        yield c


async def new_challenge(client, headers=maya, **overrides) -> dict:
    body = {
        "title": "Step-Up November",
        "starts_on": TODAY.isoformat(),
        "ends_on": (TODAY + timedelta(days=14)).isoformat(),
        "target_count": 3,
        **overrides,
    }
    resp = await client.post("/api/v1/challenges", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def progress(user: uuid.UUID, category: Category = Category.FITNESS, day=TODAY, team=ENG) -> EventEnvelope:
    return EventEnvelope.create(
        "progress.updated",
        "streak-processor",
        ProgressUpdated(
            activity_id=uuid.uuid4(),
            user_id=user,
            team_id=team,
            habit_id=uuid.uuid4(),
            category=category,
            completed_on=day,
        ),
    )


async def test_only_managers_and_admins_create_and_managers_only_for_own_team(client, bus):
    resp = await client.post(
        "/api/v1/challenges",
        headers=alice,
        json={"title": "Nope", "starts_on": TODAY.isoformat(), "ends_on": TODAY.isoformat()},
    )
    assert resp.status_code == 403
    other_team = await client.post(
        "/api/v1/challenges",
        headers=maya,
        json={
            "title": "Marketing only",
            "team_id": str(MKT),
            "starts_on": TODAY.isoformat(),
            "ends_on": TODAY.isoformat(),
        },
    )
    assert other_team.status_code == 403
    created = await new_challenge(client, team_id=str(ENG))
    assert created["team_name"] == "Engineering"
    assert created["status"] == "active"
    await flush_outbox(client.app)
    assert bus.of_type("challenge.created")[0].data["team_id"] == str(ENG)


@pytest.mark.parametrize(("start", "end"), [(-1, 3), (2, 1), (0, 91)])
async def test_invalid_windows_are_rejected(client, start, end):
    resp = await client.post(
        "/api/v1/challenges",
        headers=maya,
        json={
            "title": "Bad dates",
            "starts_on": (TODAY + timedelta(days=start)).isoformat(),
            "ends_on": (TODAY + timedelta(days=end)).isoformat(),
        },
    )
    assert resp.status_code == 422


@pytest.mark.parametrize(("days_back", "status"), [(14, 201), (15, 422)])
async def test_only_admins_may_backdate_and_only_14_days(client, days_back, status):
    body = {
        "title": "Running campaign",
        "starts_on": (TODAY - timedelta(days=days_back)).isoformat(),
        "ends_on": (TODAY + timedelta(days=5)).isoformat(),
    }
    assert (await client.post("/api/v1/challenges", headers=admin, json=body)).status_code == status
    assert (await client.post("/api/v1/challenges", headers=maya, json=body)).status_code == 422


async def test_team_challenge_is_hidden_from_other_teams(client):
    team_only = await new_challenge(client, team_id=str(ENG))
    org_wide = await new_challenge(client, title="Org-wide hydration")
    titles = {c["title"] for c in (await client.get("/api/v1/challenges", headers=emma)).json()["items"]}
    assert titles == {org_wide["title"]}
    assert (await client.get(f"/api/v1/challenges/{team_only['id']}", headers=emma)).status_code == 404
    assert (await client.post(f"/api/v1/challenges/{team_only['id']}/join", headers=emma)).status_code == 404


async def test_join_once_and_filter_by_joined_and_status(client):
    active = await new_challenge(client)
    await new_challenge(
        client,
        title="Next month",
        starts_on=(TODAY + timedelta(days=5)).isoformat(),
        ends_on=(TODAY + timedelta(days=10)).isoformat(),
    )
    joined = await client.post(f"/api/v1/challenges/{active['id']}/join", headers=alice, json={})
    assert joined.status_code == 201
    assert joined.json()["joined"] is True
    again = await client.post(f"/api/v1/challenges/{active['id']}/join", headers=alice, json={})
    assert again.status_code == 409
    mine = (await client.get("/api/v1/challenges?joined=true", headers=alice)).json()
    assert [c["id"] for c in mine["items"]] == [active["id"]]
    upcoming = (await client.get("/api/v1/challenges?status=upcoming", headers=alice)).json()
    assert [c["title"] for c in upcoming["items"]] == ["Next month"]


async def test_progress_counts_only_matching_activity_in_window_and_goal_fires_once(client, bus):
    fitness = await new_challenge(client, category="fitness", target_count=2)
    await client.post(f"/api/v1/challenges/{fitness['id']}/join", headers=alice, json={})
    dispatcher = client.app.state.dispatcher

    await dispatcher.dispatch(progress(ALICE, Category.MINDFULNESS))  # wrong category
    await dispatcher.dispatch(progress(ALICE, day=TODAY - timedelta(days=1)))  # before the window
    first = progress(ALICE)
    await dispatcher.dispatch(first)
    await dispatcher.dispatch(first)  # duplicate delivery
    assert (await client.get(f"/api/v1/challenges/{fitness['id']}", headers=alice)).json()["my_score"] == 1

    await dispatcher.dispatch(progress(ALICE))
    await dispatcher.dispatch(progress(ALICE))
    detail = (await client.get(f"/api/v1/challenges/{fitness['id']}", headers=alice)).json()
    assert (detail["my_score"], detail["my_goal_reached"]) == (3, True)
    await flush_outbox(client.app)
    assert len(bus.of_type("challenge.goal_reached")) == 1


async def test_leaderboard_ranks_and_anonymises_opted_out_participants(client):
    c = await new_challenge(client)
    await client.post(f"/api/v1/challenges/{c['id']}/join", headers=alice, json={"show_on_leaderboard": True})
    await client.post(f"/api/v1/challenges/{c['id']}/join", headers=ben, json={"show_on_leaderboard": False})
    await client.post(f"/api/v1/challenges/{c['id']}/join", headers=chloe, json={})
    await client.post(f"/api/v1/challenges/{c['id']}/join", headers=emma, json={})
    dispatcher = client.app.state.dispatcher
    for user, n in [(ALICE, 2), (BEN, 2), (CHLOE, 1), (EMMA, 4)]:
        for _ in range(n):
            await dispatcher.dispatch(progress(user, team=MKT if user == EMMA else ENG))

    board = (await client.get(f"/api/v1/challenges/{c['id']}/leaderboard", headers=chloe)).json()
    names = [(e["rank"], e["display_name"], e["score"]) for e in board["individuals"]]
    assert names == [
        (1, "Emma Davis", 4),
        (2, "Alice Johnson", 2),
        (2, "Anonymous participant", 2),
        (4, "Chloe Kim", 1),
    ]
    assert board["my_rank"] == 4
    assert all(
        e["team_name"] is None for e in board["individuals"] if e["display_name"].startswith("Anonymous")
    )
    teams = [(t["team_name"], t["participants"], t["average_score"]) for t in board["teams"]]
    assert teams == [("Marketing", 1, 4.0), ("Engineering", 3, 1.67)]

    own = (await client.get(f"/api/v1/challenges/{c['id']}/leaderboard", headers=ben)).json()
    assert [e["is_me"] for e in own["individuals"] if e["display_name"] == "Anonymous participant"] == [True]


async def test_leaderboard_works_on_29_february(client, monkeypatch):
    c = await new_challenge(client, target_count=2)
    for headers in (alice, ben, chloe):
        await client.post(f"/api/v1/challenges/{c['id']}/join", headers=headers, json={})
    # Goal times are stamped on a leap day; the old sort key built "year 9999" from the clock and crashed.
    monkeypatch.setattr("challenge_service.service.utcnow", lambda: datetime(2028, 2, 29, 12, 0, tzinfo=UTC))
    dispatcher = client.app.state.dispatcher
    for user, n in [(ALICE, 2), (BEN, 2), (CHLOE, 1)]:
        for _ in range(n):
            await dispatcher.dispatch(progress(user))

    resp = await client.get(f"/api/v1/challenges/{c['id']}/leaderboard", headers=alice)
    assert resp.status_code == 200
    board = [(e["rank"], e["display_name"], e["goal_reached"]) for e in resp.json()["individuals"]]
    assert board == [
        (1, "Alice Johnson", True),  # same score and goal time as Ben: joined first
        (1, "Ben Carter", True),
        (3, "Chloe Kim", False),
    ]


async def test_participant_can_change_visibility_and_leave(client):
    c = await new_challenge(client)
    await client.post(f"/api/v1/challenges/{c['id']}/join", headers=alice, json={})
    hidden = await client.patch(
        f"/api/v1/challenges/{c['id']}/participation", headers=alice, json={"show_on_leaderboard": False}
    )
    assert hidden.json()["show_on_leaderboard"] is False
    assert (
        await client.delete(f"/api/v1/challenges/{c['id']}/participation", headers=alice)
    ).status_code == 204
    assert (await client.get(f"/api/v1/challenges/{c['id']}", headers=alice)).json()["joined"] is False


async def test_creator_or_admin_edits_and_deletes(client):
    upcoming = await new_challenge(
        client,
        starts_on=(TODAY + timedelta(days=3)).isoformat(),
        ends_on=(TODAY + timedelta(days=9)).isoformat(),
    )
    assert (
        await client.patch(f"/api/v1/challenges/{upcoming['id']}", headers=alice, json={"title": "Mine now"})
    ).status_code == 403
    edited = await client.patch(
        f"/api/v1/challenges/{upcoming['id']}", headers=maya, json={"target_count": 5}
    )
    assert edited.json()["target_count"] == 5
    assert (await client.delete(f"/api/v1/challenges/{upcoming['id']}", headers=maya)).status_code == 204
    active = await new_challenge(client)
    assert (await client.delete(f"/api/v1/challenges/{active['id']}", headers=maya)).status_code == 422
    assert (await client.delete(f"/api/v1/challenges/{active['id']}", headers=admin)).status_code == 204


async def test_edit_keeps_the_90_day_limit_and_rejects_nulls(client):
    c = await new_challenge(client)
    too_long = await client.patch(
        f"/api/v1/challenges/{c['id']}",
        headers=maya,
        json={"ends_on": (TODAY + timedelta(days=91)).isoformat()},
    )
    assert too_long.status_code == 422
    assert too_long.json()["code"] == "invalid_dates"
    longest = await client.patch(
        f"/api/v1/challenges/{c['id']}",
        headers=maya,
        json={"ends_on": (TODAY + timedelta(days=90)).isoformat()},
    )
    assert longest.status_code == 200
    for field in ("title", "ends_on", "target_count"):
        resp = await client.patch(f"/api/v1/challenges/{c['id']}", headers=maya, json={field: None})
        assert resp.status_code == 422, field
    cleared = await client.patch(f"/api/v1/challenges/{c['id']}", headers=maya, json={"description": None})
    assert cleared.status_code == 200


async def test_badge_rules_seeded_published_and_admin_managed(client, bus):
    await flush_outbox(client.app)
    [startup] = bus.of_type("badge_rules.changed")
    assert len(startup.data["rules"]) == 9

    rules = (await client.get("/api/v1/badge-rules", headers=alice)).json()
    assert {r["code"] for r in rules} >= {"first_step", "week_warrior"}
    body = {
        "name": "Sleep Champ",
        "criterion": "category_completions",
        "category": "sleep",
        "threshold": 10,
        "icon": "😴",
    }
    assert (await client.put("/api/v1/badge-rules/sleep_champ", json=body, headers=alice)).status_code == 403
    assert (await client.put("/api/v1/badge-rules/sleep_champ", json=body, headers=admin)).status_code == 200
    missing_category = {**body, "category": None}
    assert (
        await client.put("/api/v1/badge-rules/bad_rule", json=missing_category, headers=admin)
    ).status_code == 422
    assert (await client.delete("/api/v1/badge-rules/first_step", headers=admin)).status_code == 204
    await flush_outbox(client.app)
    latest = bus.of_type("badge_rules.changed")[-1]
    codes = {r["code"] for r in latest.data["rules"]}
    assert "sleep_champ" in codes
    assert "first_step" not in codes
