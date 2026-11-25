"""Event handlers: turn integration events into in-app notifications (+ simulated e-mail via logs).

Delivery channels: in-app (stored, shown in the UI) and e-mail, which is *simulated by a structured
log entry* (``notification.email_sent``) — in production this is where Amazon SES would be called.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from notification_service.models import Contact, Notification, Preference
from teampulse_common.events import EventDispatcher, EventEnvelope, EventType
from teampulse_common.events.contracts import (
    ActivityCompleted,
    BadgeAwarded,
    ChallengeCreated,
    ChallengeGoalReached,
    ChallengeJoined,
    ReminderTick,
    StreakMilestone,
    UserRegistered,
    UserUpdated,
)

logger = logging.getLogger("notification")


async def notify(
    session: AsyncSession, user_id: uuid.UUID, kind: str, title: str, body: str, data: dict | None = None
) -> Notification:
    notification = Notification(user_id=user_id, type=kind, title=title, body=body, data=data or {})
    session.add(notification)
    logger.info("notification.created", extra={"notification_type": kind, "recipient": str(user_id)})
    prefs = await session.get(Preference, user_id)
    if prefs and prefs.email_enabled:
        contact = await session.get(Contact, user_id)
        if contact and contact.email:
            # Simulated e-mail channel (Amazon SES in production).
            logger.info(
                "notification.email_sent",
                extra={"notification_type": kind, "recipient": str(user_id), "subject_line": title},
            )
    return notification


async def _upsert_contact(session: AsyncSession, data: UserRegistered | UserUpdated) -> Contact:
    contact = await session.get(Contact, data.user_id)
    if contact is None:
        contact = Contact(user_id=data.user_id)
        session.add(contact)
    contact.team_id = data.team_id
    contact.display_name = data.display_name
    contact.email = data.email
    contact.role = data.role
    contact.is_active = getattr(data, "is_active", True)
    return contact


async def on_user_registered(envelope: EventEnvelope, session: AsyncSession | None) -> None:
    assert session
    data = UserRegistered.model_validate(envelope.data)
    await _upsert_contact(session, data)
    first_name = data.display_name.split()[0] if data.display_name else "there"
    await notify(
        session,
        data.user_id,
        "welcome",
        f"Welcome to TeamPulse, {first_name}! 👋",
        "Create your first habit and join a team challenge to get started.",
    )


async def on_user_updated(envelope: EventEnvelope, session: AsyncSession | None) -> None:
    assert session
    await _upsert_contact(session, UserUpdated.model_validate(envelope.data))


async def on_activity_completed(envelope: EventEnvelope, session: AsyncSession | None) -> None:
    assert session
    data = ActivityCompleted.model_validate(envelope.data)
    contact = await session.get(Contact, data.user_id)
    if contact is None:
        contact = Contact(user_id=data.user_id, team_id=data.team_id)
        session.add(contact)
    if contact.last_activity_on is None or data.completed_on > contact.last_activity_on:
        contact.last_activity_on = data.completed_on


async def on_streak_milestone(envelope: EventEnvelope, session: AsyncSession | None) -> None:
    assert session
    data = StreakMilestone.model_validate(envelope.data)
    unit = "day" if data.frequency == "daily" else "week"
    await notify(
        session,
        data.user_id,
        "streak.milestone",
        f"🔥 {data.streak}-{unit} streak!",
        f"You've kept a habit going for {data.streak} {unit}s in a row. Keep it up!",
        {"habit_id": str(data.habit_id), "streak": data.streak},
    )


async def on_badge_awarded(envelope: EventEnvelope, session: AsyncSession | None) -> None:
    assert session
    data = BadgeAwarded.model_validate(envelope.data)
    await notify(
        session,
        data.user_id,
        "badge.awarded",
        f"New badge: {data.name} {data.icon}",
        data.description,
        {"code": data.code},
    )


async def on_challenge_created(envelope: EventEnvelope, session: AsyncSession | None) -> None:
    assert session
    data = ChallengeCreated.model_validate(envelope.data)
    stmt = select(Contact).where(Contact.is_active.is_(True), Contact.user_id != data.created_by)
    if data.team_id is not None:
        stmt = stmt.where(Contact.team_id == data.team_id)
    audience = "your team" if data.team_id else "everyone"
    for contact in (await session.scalars(stmt)).all():
        await notify(
            session,
            contact.user_id,
            "challenge.created",
            f"New challenge: {data.title}",
            f"Open to {audience} from {data.starts_on:%d %b} to {data.ends_on:%d %b}. Join in!",
            {"challenge_id": str(data.challenge_id)},
        )


async def on_challenge_joined(envelope: EventEnvelope, session: AsyncSession | None) -> None:
    assert session
    data = ChallengeJoined.model_validate(envelope.data)
    await notify(
        session,
        data.user_id,
        "challenge.joined",
        f"You joined “{data.title}”",
        "Every matching activity you log now counts towards the leaderboard.",
        {"challenge_id": str(data.challenge_id)},
    )


async def on_goal_reached(envelope: EventEnvelope, session: AsyncSession | None) -> None:
    assert session
    data = ChallengeGoalReached.model_validate(envelope.data)
    await notify(
        session,
        data.user_id,
        "challenge.goal_reached",
        f"Goal reached in “{data.title}” 🎉",
        f"You hit the challenge target with {data.score} completions.",
        {"challenge_id": str(data.challenge_id), "score": data.score},
    )


def _local_now(tz: str, now: datetime) -> datetime:
    try:
        return now.astimezone(ZoneInfo(tz))
    except (ZoneInfoNotFoundError, ValueError):
        return now.astimezone(UTC)


async def send_due_reminders(session: AsyncSession, now: datetime) -> int:
    """Remind people at their chosen local hour, once a day, only if they haven't logged anything yet."""
    sent = 0
    contacts = (await session.scalars(select(Contact).where(Contact.is_active.is_(True)))).all()
    for contact in contacts:
        prefs = await session.get(Preference, contact.user_id) or Preference(
            user_id=contact.user_id, reminders_enabled=True, reminder_hour=9, timezone="UTC"
        )
        if not prefs.reminders_enabled:
            continue
        local = _local_now(prefs.timezone or "UTC", now)
        today: date = local.date()
        if local.hour != prefs.reminder_hour or contact.last_reminded_on == today:
            continue
        if contact.last_activity_on is not None and contact.last_activity_on >= today:
            continue
        await notify(
            session,
            contact.user_id,
            "reminder",
            "Time for your habits ⏰",
            "A small step today keeps your streak alive. Log an activity in TeamPulse.",
        )
        contact.last_reminded_on = today
        sent += 1
    logger.info("reminders.run", extra={"sent": sent})
    return sent


async def on_reminder_tick(envelope: EventEnvelope, session: AsyncSession | None) -> None:
    assert session
    ReminderTick.model_validate(envelope.data)
    await send_due_reminders(session, envelope.time.astimezone(UTC))


def register_handlers(dispatcher: EventDispatcher) -> None:
    dispatcher.on(EventType.USER_REGISTERED)(on_user_registered)
    dispatcher.on(EventType.USER_UPDATED)(on_user_updated)
    dispatcher.on(EventType.ACTIVITY_COMPLETED)(on_activity_completed)
    dispatcher.on(EventType.STREAK_MILESTONE)(on_streak_milestone)
    dispatcher.on(EventType.BADGE_AWARDED)(on_badge_awarded)
    dispatcher.on(EventType.CHALLENGE_CREATED)(on_challenge_created)
    dispatcher.on(EventType.CHALLENGE_JOINED)(on_challenge_joined)
    dispatcher.on(EventType.CHALLENGE_GOAL_REACHED)(on_goal_reached)
    dispatcher.on(EventType.REMINDER_TICK)(on_reminder_tick)
