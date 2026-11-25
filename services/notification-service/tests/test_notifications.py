from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from notification_service.handlers import send_due_reminders
from notification_service.main import Settings, create_app
from teampulse_common.events import EventEnvelope, InMemoryEventBus
from teampulse_common.events.contracts import (
    ActivityCompleted,
    BadgeAwarded,
    Category,
    ChallengeCreated,
    Frequency,
    StreakMilestone,
    UserRegistered,
)
from teampulse_common.testing import bearer, make_token, running_client, sqlite_url, verifier_for_tests

ENG, MKT = uuid.uuid4(), uuid.uuid4()
ALICE, BEN, EMMA, MAYA = (uuid.uuid4() for _ in range(4))


@pytest.fixture
async def client(tmp_path) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=sqlite_url(tmp_path),
        data_dir=str(tmp_path),
        log_level="WARNING",
        reminder_scheduler="external",
    )
    app = create_app(settings, publisher=InMemoryEventBus(), verifier=verifier_for_tests())
    async with running_client(app) as c:
        c.app = app  # type: ignore[attr-defined]
        dispatcher = app.state.dispatcher
        for uid, name, team in [
            (ALICE, "Alice Johnson", ENG),
            (BEN, "Ben Carter", ENG),
            (EMMA, "Emma Davis", MKT),
            (MAYA, "Maya Patel", ENG),
        ]:
            await dispatcher.dispatch(
                EventEnvelope.create(
                    "user.registered",
                    "identity-service",
                    UserRegistered(
                        user_id=uid,
                        team_id=team,
                        role="employee",
                        display_name=name,
                        email=f"{uid}@teampulse.io",
                    ),
                )
            )
        yield c


def h(user: uuid.UUID) -> dict[str, str]:
    return bearer(make_token(user))


async def inbox(client, user) -> list[dict]:
    return (await client.get("/api/v1/notifications", headers=h(user))).json()["items"]


async def test_welcome_notification_from_user_registered(client):
    [welcome] = await inbox(client, ALICE)
    assert welcome["type"] == "welcome"
    assert "Alice" in welcome["title"]


async def test_badge_and_milestone_messages_go_to_the_right_person(client):
    d = client.app.state.dispatcher
    await d.dispatch(
        EventEnvelope.create(
            "badge.awarded",
            "streak-processor",
            BadgeAwarded(
                user_id=ALICE, code="week_warrior", name="Week Warrior", description="7-day streak", icon="🔥"
            ),
        )
    )
    await d.dispatch(
        EventEnvelope.create(
            "streak.milestone",
            "streak-processor",
            StreakMilestone(user_id=ALICE, habit_id=uuid.uuid4(), streak=7, frequency=Frequency.DAILY),
        )
    )
    titles = [n["title"] for n in await inbox(client, ALICE)]
    assert "New badge: Week Warrior 🔥" in titles
    assert "🔥 7-day streak!" in titles
    assert [n["type"] for n in await inbox(client, BEN)] == ["welcome"]


async def test_team_challenge_announcement_targets_team_and_skips_creator(client):
    await client.app.state.dispatcher.dispatch(
        EventEnvelope.create(
            "challenge.created",
            "challenge-service",
            ChallengeCreated(
                challenge_id=uuid.uuid4(),
                title="Hydration Week",
                team_id=ENG,
                starts_on=date(2026, 11, 9),
                ends_on=date(2026, 11, 15),
                created_by=MAYA,
            ),
        )
    )
    assert any(n["type"] == "challenge.created" for n in await inbox(client, ALICE))
    assert all(n["type"] != "challenge.created" for n in await inbox(client, EMMA))  # other team
    assert all(n["type"] != "challenge.created" for n in await inbox(client, MAYA))  # creator


async def test_unread_count_mark_read_and_read_all_are_scoped_to_owner(client):
    assert (await client.get("/api/v1/notifications/unread-count", headers=h(ALICE))).json() == {"count": 1}
    [welcome] = await inbox(client, ALICE)
    assert (
        await client.post(f"/api/v1/notifications/{welcome['id']}/read", headers=h(BEN))
    ).status_code == 404
    read = await client.post(f"/api/v1/notifications/{welcome['id']}/read", headers=h(ALICE))
    assert read.json()["is_read"] is True
    assert (await client.get("/api/v1/notifications?unread_only=true", headers=h(ALICE))).json()["total"] == 0
    assert (await client.post("/api/v1/notifications/read-all", headers=h(BEN))).json() == {"updated": 1}


async def test_preferences_round_trip_and_validate_timezone(client):
    assert (await client.get("/api/v1/notifications/preferences", headers=h(ALICE))).json()[
        "reminder_hour"
    ] == 9
    body = {"reminders_enabled": True, "reminder_hour": 18, "timezone": "Asia/Kolkata", "email_enabled": True}
    assert (await client.put("/api/v1/notifications/preferences", json=body, headers=h(ALICE))).json() == body
    bad = await client.put(
        "/api/v1/notifications/preferences", headers=h(ALICE), json={**body, "timezone": "Mars/Olympus_Mons"}
    )
    assert bad.status_code == 422


async def test_reminders_respect_local_hour_skip_active_people_and_send_once(client):
    await client.put(
        "/api/v1/notifications/preferences",
        headers=h(ALICE),
        json={"reminders_enabled": True, "reminder_hour": 9, "timezone": "UTC", "email_enabled": False},
    )
    await client.put(
        "/api/v1/notifications/preferences",
        headers=h(EMMA),
        json={"reminders_enabled": False, "reminder_hour": 9, "timezone": "UTC", "email_enabled": False},
    )
    nine_am = datetime(2026, 11, 9, 9, 15, tzinfo=UTC)
    # Ben already logged something today → no reminder for him.
    await client.app.state.dispatcher.dispatch(
        EventEnvelope.create(
            "activity.completed",
            "event-tracking-service",
            ActivityCompleted(
                activity_id=uuid.uuid4(),
                user_id=BEN,
                team_id=ENG,
                habit_id=uuid.uuid4(),
                category=Category.FITNESS,
                frequency=Frequency.DAILY,
                target_per_period=1,
                completed_on=nine_am.date(),
                occurred_at=nine_am,
            ),
        )
    )
    async with client.app.state.db.session_factory() as session:
        sent_at_8 = await send_due_reminders(session, nine_am - timedelta(hours=1))
        sent_at_9 = await send_due_reminders(session, nine_am)
        sent_again = await send_due_reminders(session, nine_am + timedelta(minutes=30))
        await session.commit()
    assert (sent_at_8, sent_at_9, sent_again) == (0, 2, 0)  # Alice + Maya (default prefs); not Ben/Emma
    assert any(n["type"] == "reminder" for n in await inbox(client, ALICE))
    assert all(n["type"] != "reminder" for n in await inbox(client, BEN))
    assert all(n["type"] != "reminder" for n in await inbox(client, EMMA))
