"""Streak processor: reacts to ``activity.completed`` (End-to-End Flow steps 5-6).

For every completion it
1. recomputes the habit's streak from its completion history,
2. evaluates badge rules and awards new badges (idempotently),
3. updates per-user and per-team daily rollups in the analytics table (DynamoDB),
4. publishes ``progress.updated`` (→ challenge progress), ``streak.milestone`` and ``badge.awarded``
   (→ notifications).

Delivery is at-least-once, and a run can fail at any point. So everything one completion changes is
saved in ONE all-or-nothing write (``store.transact``, DynamoDB ``TransactWriteItems``):

* the claim ``EVENT#<id>`` - only if it does not exist yet - holding the events still to be sent,
* the counters (lifetime stats, user and team day rollups, the team list),
* new badges - only if the user does not have them yet,
* the streak item - only if no other event changed it since it was read (``version`` check).

If anything fails before or during that write, nothing is saved and the retry starts cleanly. If a
condition fails because another event of the same user got there first, the work is read and planned
again. After the write, the events are sent and the claim is set to ``done``. If sending fails, the
claim stays ``publishing`` and the retry re-sends the saved events (same ids, so consumers' inboxes drop
any copy that already arrived) instead of counting the completion a second time.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from streak_processor.badges import UserStats, eligible_badges
from streak_processor.streaks import (
    compute_streak,
    current_run_start,
    merge_history,
    milestones_to_announce,
)
from teampulse_common.analytics_store import (
    AnalyticsStore,
    Increment,
    Put,
    TransactionConflictError,
    Write,
)
from teampulse_common.events import EventEnvelope, EventPublisher, EventType
from teampulse_common.events.contracts import (
    DEFAULT_BADGE_RULES,
    ActivityCompleted,
    BadgeAwarded,
    BadgeRule,
    BadgeRulesChanged,
    ProgressUpdated,
    StreakMilestone,
)

logger = logging.getLogger("streak_processor")
SOURCE = "streak-processor"
IDEMPOTENCY_TTL = timedelta(days=7)
CLAIM_SK = "PROCESSED"
MAX_WRITE_ATTEMPTS = 5  # plan + write again when another event of the same user got there first


def user_pk(user_id: Any) -> str:
    return f"USER#{user_id}"


def team_pk(team_id: Any) -> str:
    return f"TEAM#{team_id}"


@dataclass
class Plan:
    """Everything one completion will change, worked out before anything is written."""

    writes: list[Write]
    events: list[EventEnvelope]
    streak: int


class StreakProcessor:
    def __init__(
        self,
        store: AnalyticsStore,
        publisher: EventPublisher,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.store = store
        self.publisher = publisher
        self.clock = clock

    async def handle(self, envelope: EventEnvelope) -> None:
        if envelope.type == EventType.ACTIVITY_COMPLETED:
            await self._on_activity_completed(envelope)
        elif envelope.type == EventType.BADGE_RULES_CHANGED:
            await self._on_badge_rules_changed(envelope)
        else:
            logger.debug("processor.ignored", extra={"event_type": envelope.type})

    # ------------------------------------------------------------------ badge rules (state transfer)
    async def _on_badge_rules_changed(self, envelope: EventEnvelope) -> None:
        payload = BadgeRulesChanged.model_validate(envelope.data)
        current = await self.store.get("CONFIG", "BADGE_RULES")
        if current and datetime.fromisoformat(current["updated_at"]) > envelope.time:
            # Events can arrive out of order: a late, older list must not replace a newer one.
            logger.info("processor.badge_rules_stale_skipped", extra={"event_id": str(envelope.id)})
            return
        await self.store.put(
            "CONFIG",
            "BADGE_RULES",
            {
                "rules": [r.model_dump(mode="json") for r in payload.rules],
                "updated_at": envelope.time.isoformat(),
            },
        )
        logger.info("processor.badge_rules_updated", extra={"count": len(payload.rules)})

    async def _badge_rules(self) -> list[BadgeRule]:
        item = await self.store.get("CONFIG", "BADGE_RULES")
        if not item:
            return list(DEFAULT_BADGE_RULES)
        return [BadgeRule.model_validate(r) for r in item.get("rules", [])]

    # ------------------------------------------------------------------ activity completed
    async def _on_activity_completed(self, envelope: EventEnvelope) -> None:
        claim_pk = f"EVENT#{envelope.id}"
        if existing := await self.store.get(claim_pk, CLAIM_SK):
            await self._handle_existing_claim(claim_pk, existing, envelope)
            return
        activity = ActivityCompleted.model_validate(envelope.data)
        for attempt in range(1, MAX_WRITE_ATTEMPTS + 1):
            plan = await self._plan(activity, envelope.id)
            claim = {
                "expires_at": int((self.clock() + IDEMPOTENCY_TTL).timestamp()),
                "type": envelope.type,
                "status": "publishing",
                "outgoing": [e.model_dump(mode="json") for e in plan.events],
            }
            try:
                # One all-or-nothing write: the claim (with the events to send) and every change.
                await self.store.transact([Put(claim_pk, CLAIM_SK, claim, if_absent=True), *plan.writes])
                break
            except TransactionConflictError as conflict:
                if (claim_pk, CLAIM_SK) in conflict.keys:  # another copy of this event got there first
                    await self._handle_existing_claim(
                        claim_pk, await self.store.get(claim_pk, CLAIM_SK) or {}, envelope
                    )
                    return
                # Another event of this user changed the streak or won a badge since we read them.
                logger.info(
                    "processor.write_conflict_retry", extra={"event_id": str(envelope.id), "attempt": attempt}
                )
        else:
            # Nothing was saved. Raising lets Lambda (or the queue) retry the event later.
            raise RuntimeError(f"event {envelope.id}: write conflict after {MAX_WRITE_ATTEMPTS} attempts")
        logger.info(
            "processor.activity_processed",
            extra={
                "habit_streak": plan.streak,
                "events_out": len(plan.events),
                "category": activity.category.value,
            },
        )
        await self._send_saved(claim_pk, claim)

    async def _handle_existing_claim(
        self, claim_pk: str, existing: dict[str, Any], envelope: EventEnvelope
    ) -> None:
        if existing.get("status") == "publishing":
            # An earlier try saved everything but could not send its events. Send the saved events
            # now; counting the completion again would add it twice.
            logger.info("processor.resending_saved_events", extra={"event_id": str(envelope.id)})
            await self._send_saved(claim_pk, existing)
        else:
            logger.info("processor.duplicate_skipped", extra={"event_id": str(envelope.id)})

    async def _send_saved(self, claim_pk: str, claim: dict[str, Any]) -> None:
        events = [EventEnvelope.model_validate(e) for e in claim.get("outgoing", [])]
        if events:
            await self.publisher.publish(events)  # on failure the claim stays "publishing" for the retry
        await self.store.put(
            claim_pk,
            CLAIM_SK,
            {"expires_at": claim["expires_at"], "type": claim["type"], "status": "done"},
        )

    async def _plan(self, activity: ActivityCompleted, event_id: Any) -> Plan:
        """Read the current state and work out every write and event. Nothing is written here."""
        upk = user_pk(activity.user_id)
        category_key = f"cat_{activity.category.value}"
        day: date = activity.completed_on
        day_sk = f"DAY#{day.isoformat()}"

        # 1. streak ------------------------------------------------------------------------------
        streak_sk = f"STREAK#{activity.habit_id}"
        previous = await self.store.get(upk, streak_sk) or {}
        history = merge_history(previous.get("dates", []), day)
        dates = [date.fromisoformat(d) for d in history]
        result = compute_streak(dates, activity.frequency, activity.target_per_period)
        run_start = current_run_start(dates, activity.frequency, activity.target_per_period)
        same_frequency = previous.get("frequency", activity.frequency.value) == activity.frequency.value
        announced: dict[str, str] = dict(previous.get("milestones_announced", {})) if same_frequency else {}

        # 2. lifetime stats + daily rollups (atomic ADDs, so other events' counts are never lost) ---
        stats_before = await self.store.get(upk, "STATS") or {}
        writes: list[Write] = [
            Increment(upk, "STATS", {"total": 1, category_key: 1}),
            Increment(upk, day_sk, {"completions": 1, "value": activity.value, category_key: 1}),
        ]
        if activity.team_id:
            # Team rollup keeps a set of (pseudonymous) member ids only to count *distinct* active
            # members for k-anonymity; the Insight Service never returns the set itself.
            member = {str(activity.user_id)}
            writes.append(
                Increment(
                    team_pk(activity.team_id),
                    day_sk,
                    {"completions": 1, "value": activity.value, category_key: 1},
                    add_to_sets={"active_users": member, f"active_users_{category_key}": member},
                )
            )
            writes.append(Increment("ORG", "TEAMS", {}, add_to_sets={"team_ids": {str(activity.team_id)}}))

        events: list[EventEnvelope] = []
        subject = f"user:{activity.user_id}"

        # 3. milestones: thresholds this completion pushed the streak past, once per run ----------
        new_milestones = milestones_to_announce(
            int(previous.get("current", 0)), result.current, run_start, announced
        )
        for milestone in new_milestones:
            announced[str(milestone)] = run_start or ""
            events.append(
                EventEnvelope.create(
                    EventType.STREAK_MILESTONE,
                    SOURCE,
                    StreakMilestone(
                        user_id=activity.user_id,
                        habit_id=activity.habit_id,
                        streak=milestone,
                        frequency=activity.frequency,
                    ),
                    subject=subject,
                )
            )

        # 4. badges: the stats as they will be after this completion ------------------------------
        categories = {k.removeprefix("cat_"): int(v) for k, v in stats_before.items() if k.startswith("cat_")}
        categories[activity.category.value] = categories.get(activity.category.value, 0) + 1
        stats = UserStats(
            total_completions=int(stats_before.get("total", 0)) + 1,
            streak=result.current,
            category_completions=categories,
        )
        owned = {
            item["sk"].removeprefix("BADGE#") for item in await self.store.query(upk, sk_prefix="BADGE#")
        }
        for rule in eligible_badges(await self._badge_rules(), stats):
            if rule.code in owned:
                continue
            writes.append(
                Put(
                    upk,
                    f"BADGE#{rule.code}",
                    {
                        "code": rule.code,
                        "name": rule.name,
                        "description": rule.description,
                        "icon": rule.icon,
                        "awarded_at": self.clock().isoformat(),
                        "event_id": str(event_id),
                    },
                    if_absent=True,  # if another event awarded it meanwhile, plan again
                )
            )
            events.append(
                EventEnvelope.create(
                    EventType.BADGE_AWARDED,
                    SOURCE,
                    BadgeAwarded(
                        user_id=activity.user_id,
                        code=rule.code,
                        name=rule.name,
                        description=rule.description,
                        icon=rule.icon,
                    ),
                    subject=subject,
                )
            )

        # 5. challenge progress ----------------------------------------------------------------
        events.append(
            EventEnvelope.create(
                EventType.PROGRESS_UPDATED,
                SOURCE,
                ProgressUpdated(
                    activity_id=activity.activity_id,
                    user_id=activity.user_id,
                    team_id=activity.team_id,
                    habit_id=activity.habit_id,
                    category=activity.category,
                    completed_on=day,
                    value=activity.value,
                    current_streak=result.current,
                ),
                subject=subject,
            )
        )

        # 6. the new streak item. "version" goes up by one on every write; the write only succeeds
        # if the stored version is still the one read in step 1, so two events for the same habit
        # at the same moment cannot overwrite each other's dates (the loser plans again).
        version = int(previous.get("version", 0))
        writes.append(
            Put(
                upk,
                streak_sk,
                {
                    "habit_id": str(activity.habit_id),
                    "frequency": activity.frequency.value,
                    "target": activity.target_per_period,
                    "dates": history,
                    "current": result.current,
                    "longest": result.longest,
                    "last_period": result.last_period,
                    "run_start": run_start,
                    "milestones_announced": announced,
                    "total": len(history),
                    "version": version + 1,
                    "updated_at": self.clock().isoformat(),
                },
                if_version=version,
            )
        )
        return Plan(writes=writes, events=events, streak=result.current)
