from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from habit_service.main import Settings, create_app
from teampulse_common.events import EventEnvelope, InMemoryEventBus
from teampulse_common.events.contracts import UserUpdated
from teampulse_common.testing import bearer, make_token, running_client, sqlite_url, verifier_for_tests

ENG = uuid.uuid4()
MKT = uuid.uuid4()
ALICE, BEN, EMMA = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def tok(user: uuid.UUID, team: uuid.UUID, name: str) -> dict[str, str]:
    return bearer(make_token(user, team_id=team, name=name))


@pytest.fixture
async def client(tmp_path) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=sqlite_url(tmp_path),
        data_dir=str(tmp_path),
        log_level="WARNING",
    )
    app = create_app(settings, publisher=InMemoryEventBus(), verifier=verifier_for_tests())
    async with running_client(app) as c:
        c.app = app  # type: ignore[attr-defined]
        yield c


async def create(client, headers, **overrides) -> dict:
    body = {
        "title": "Morning run",
        "category": "fitness",
        "frequency": "daily",
        "visibility": "private",
        **overrides,
    }
    resp = await client.post("/api/v1/habits", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_and_list_own_habits_with_filters(client):
    alice = tok(ALICE, ENG, "Alice Johnson")
    await create(client, alice, title="Morning run")
    await create(client, alice, title="Meditate", category="mindfulness", visibility="team")
    page = (await client.get("/api/v1/habits", headers=alice)).json()
    assert page["total"] == 2
    filtered = (await client.get("/api/v1/habits?category=mindfulness", headers=alice)).json()
    assert [h["title"] for h in filtered["items"]] == ["Meditate"]
    searched = (await client.get("/api/v1/habits?search=RUN", headers=alice)).json()
    assert [h["title"] for h in searched["items"]] == ["Morning run"]


@pytest.mark.parametrize(
    ("frequency", "target", "ok"),
    [("daily", 1, True), ("daily", 2, False), ("weekly", 3, True), ("weekly", 7, True), ("weekly", 8, False)],
)
async def test_target_must_match_frequency(client, frequency, target, ok):
    resp = await client.post(
        "/api/v1/habits",
        headers=tok(ALICE, ENG, "Alice"),
        json={"title": "Stretch", "category": "fitness", "frequency": frequency, "target_per_period": target},
    )
    assert (resp.status_code == 201) is ok


async def test_private_habit_is_invisible_to_teammates_and_returns_404(client):
    private = await create(client, tok(ALICE, ENG, "Alice"))
    resp = await client.get(f"/api/v1/habits/{private['id']}", headers=tok(BEN, ENG, "Ben"))
    assert resp.status_code == 404  # not 403 — existence is not leaked


async def test_team_habit_visible_to_same_team_only(client):
    shared = await create(client, tok(ALICE, ENG, "Alice Johnson"), visibility="team")
    assert (
        await client.get(f"/api/v1/habits/{shared['id']}", headers=tok(BEN, ENG, "Ben"))
    ).status_code == 200
    assert (
        await client.get(f"/api/v1/habits/{shared['id']}", headers=tok(EMMA, MKT, "Emma"))
    ).status_code == 404
    team_feed = (await client.get("/api/v1/habits/team", headers=tok(BEN, ENG, "Ben"))).json()
    assert [h["owner_name"] for h in team_feed["items"]] == ["Alice Johnson"]
    assert (await client.get("/api/v1/habits/team", headers=tok(EMMA, MKT, "Emma"))).json()["total"] == 0


async def test_only_owner_can_update_or_archive(client):
    habit = await create(client, tok(ALICE, ENG, "Alice"), visibility="team")
    ben = tok(BEN, ENG, "Ben")
    assert (
        await client.patch(f"/api/v1/habits/{habit['id']}", json={"title": "Hacked"}, headers=ben)
    ).status_code == 404
    assert (await client.delete(f"/api/v1/habits/{habit['id']}", headers=ben)).status_code == 404

    alice = tok(ALICE, ENG, "Alice")
    upd = await client.patch(
        f"/api/v1/habits/{habit['id']}", headers=alice, json={"frequency": "weekly", "target_per_period": 3}
    )
    assert upd.json()["target_per_period"] == 3
    bad = await client.patch(
        f"/api/v1/habits/{habit['id']}", headers=alice, json={"frequency": "daily", "target_per_period": 3}
    )
    assert bad.status_code == 422
    assert (await client.delete(f"/api/v1/habits/{habit['id']}", headers=alice)).status_code == 204
    assert (await client.get("/api/v1/habits", headers=alice)).json()["total"] == 0
    assert (await client.get("/api/v1/habits?include_archived=true", headers=alice)).json()["total"] == 1


async def test_patch_rejects_null_for_required_fields(client):
    alice = tok(ALICE, ENG, "Alice")
    habit = await create(client, alice, description="Before work")
    for field in (
        "title",
        "category",
        "frequency",
        "target_per_period",
        "visibility",
        "color",
        "is_archived",
    ):
        resp = await client.patch(f"/api/v1/habits/{habit['id']}", headers=alice, json={field: None})
        assert resp.status_code == 422, field
        assert resp.json()["errors"][0]["field"] == field
    cleared = await client.patch(f"/api/v1/habits/{habit['id']}", headers=alice, json={"description": None})
    assert cleared.status_code == 200
    assert cleared.json()["description"] is None


async def test_user_updated_event_refreshes_owner_name_and_team_idempotently(client):
    habit = await create(client, tok(ALICE, ENG, "Alice Johnson"), visibility="team")
    event = EventEnvelope.create(
        "user.updated",
        "identity-service",
        UserUpdated(
            user_id=ALICE, team_id=MKT, role="employee", display_name="Alice J.", email="alice@teampulse.io"
        ),
    )
    dispatcher = client.app.state.dispatcher
    assert await dispatcher.dispatch(event)
    assert await dispatcher.dispatch(event)  # duplicate delivery is skipped by the inbox
    seen_by_emma = await client.get(f"/api/v1/habits/{habit['id']}", headers=tok(EMMA, MKT, "Emma"))
    assert seen_by_emma.status_code == 200
    assert seen_by_emma.json()["owner_name"] == "Alice J."


async def test_requires_authentication(client):
    resp = await client.get("/api/v1/habits")
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")
