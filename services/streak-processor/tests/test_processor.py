from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from streak_processor import handler
from streak_processor.processor import StreakProcessor
from teampulse_common.analytics_store import MemoryAnalyticsStore, SqlAnalyticsStore
from teampulse_common.events import EventEnvelope, InMemoryEventBus
from teampulse_common.events.contracts import (
    ActivityCompleted,
    BadgeCriterion,
    BadgeRule,
    BadgeRulesChanged,
    Category,
    Frequency,
)
from teampulse_common.testing import sqlite_url

USER, TEAM, HABIT = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
START = date(2026, 11, 2)


def completed(
    day: date,
    *,
    user=USER,
    team=TEAM,
    habit=HABIT,
    category=Category.FITNESS,
    frequency=Frequency.DAILY,
    target=1,
    value=1.0,
) -> EventEnvelope:
    return EventEnvelope.create(
        "activity.completed",
        "event-tracking-service",
        ActivityCompleted(
            activity_id=uuid.uuid4(),
            user_id=user,
            team_id=team,
            habit_id=habit,
            category=category,
            frequency=frequency,
            target_per_period=target,
            value=value,
            completed_on=day,
            occurred_at=datetime.now(UTC),
        ),
    )


@pytest.fixture(params=["memory", "sql", "dynamodb"])
async def store(request, tmp_path, monkeypatch):
    if request.param == "memory":
        s = MemoryAnalyticsStore()
    elif request.param == "sql":
        s = SqlAnalyticsStore(sqlite_url(tmp_path, "analytics"))
    else:
        # moto imitates DynamoDB in memory, so the real boto3 code path (TransactWriteItems,
        # condition expressions, cancellation reasons) runs without an AWS account.
        import boto3
        from moto import mock_aws

        from teampulse_common.analytics_store import DynamoDBAnalyticsStore

        for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
            monkeypatch.setenv(name, "testing")
        with mock_aws():
            boto3.client("dynamodb", region_name="eu-west-1").create_table(
                TableName="analytics",
                KeySchema=[
                    {"AttributeName": "pk", "KeyType": "HASH"},
                    {"AttributeName": "sk", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "pk", "AttributeType": "S"},
                    {"AttributeName": "sk", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            s = DynamoDBAnalyticsStore("analytics", "eu-west-1")
            yield s
            return
    yield s
    await s.close()


@pytest.fixture
def bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest.fixture
def processor(store, bus) -> StreakProcessor:
    return StreakProcessor(store, bus)


async def test_first_completion_creates_streak_badge_rollups_and_progress(processor, store, bus):
    await processor.handle(completed(START, value=30))

    streak = await store.get(f"USER#{USER}", f"STREAK#{HABIT}")
    assert (streak["current"], streak["longest"], streak["total"]) == (1, 1, 1)
    assert [e.data["code"] for e in bus.of_type("badge.awarded")] == ["first_step"]
    [progress] = bus.of_type("progress.updated")
    assert progress.data["category"] == "fitness"
    assert progress.data["current_streak"] == 1

    day = await store.get(f"USER#{USER}", f"DAY#{START}")
    assert (day["completions"], day["value"], day["cat_fitness"]) == (1, 30, 1)
    team_day = await store.get(f"TEAM#{TEAM}", f"DAY#{START}")
    assert team_day["active_users"] == {str(USER)}


async def test_duplicate_delivery_is_processed_once(processor, store, bus):
    event = completed(START)
    await processor.handle(event)
    await processor.handle(event)
    assert (await store.get(f"USER#{USER}", "STATS"))["total"] == 1
    assert len(bus.of_type("progress.updated")) == 1


async def test_three_day_streak_fires_milestone_and_badge_once(processor, bus):
    for offset in range(4):
        await processor.handle(completed(START + timedelta(days=offset)))
    milestones = [e.data["streak"] for e in bus.of_type("streak.milestone")]
    assert milestones == [3]
    badges = [e.data["code"] for e in bus.of_type("badge.awarded")]
    assert badges.count("on_a_roll") == 1


async def test_team_rollup_counts_distinct_members(processor, store):
    other = uuid.uuid4()
    await processor.handle(completed(START))
    await processor.handle(completed(START, habit=uuid.uuid4()))  # same user, second habit
    await processor.handle(completed(START, user=other, habit=uuid.uuid4()))
    team_day = await store.get(f"TEAM#{TEAM}", f"DAY#{START}")
    assert team_day["completions"] == 3
    assert len(team_day["active_users"]) == 2


async def test_an_older_rules_list_arriving_late_is_ignored(processor, store, bus):
    def rules_event(code: str, minutes_ago: int) -> EventEnvelope:
        rule = BadgeRule(
            code=code, name=code, criterion=BadgeCriterion.TOTAL_COMPLETIONS, threshold=1, icon="⭐"
        )
        envelope = EventEnvelope.create(
            "badge_rules.changed", "challenge-service", BadgeRulesChanged(rules=[rule])
        )
        envelope.time = datetime.now(UTC) - timedelta(minutes=minutes_ago)
        return envelope

    await processor.handle(rules_event("newer_rule", minutes_ago=1))
    await processor.handle(rules_event("older_rule", minutes_ago=5))  # sent earlier, arrives later
    await processor.handle(completed(START))
    assert [e.data["code"] for e in bus.of_type("badge.awarded")] == ["newer_rule"]


async def test_rules_from_challenge_service_replace_defaults(processor, store, bus):
    rules = [
        BadgeRule(
            code="hydro_starter",
            name="Hydro Starter",
            criterion=BadgeCriterion.CATEGORY_COMPLETIONS,
            category=Category.HYDRATION,
            threshold=1,
            icon="💧",
        )
    ]
    await processor.handle(
        EventEnvelope.create("badge_rules.changed", "challenge-service", BadgeRulesChanged(rules=rules))
    )
    await processor.handle(completed(START, category=Category.HYDRATION))
    assert [e.data["code"] for e in bus.of_type("badge.awarded")] == ["hydro_starter"]


async def test_weekly_habit_streak_uses_target(processor, store):
    for offset in (0, 1, 7, 8):
        await processor.handle(
            completed(START + timedelta(days=offset), frequency=Frequency.WEEKLY, target=2)
        )
    streak = await store.get(f"USER#{USER}", f"STREAK#{HABIT}")
    assert (streak["current"], streak["last_period"]) == (2, "2026-W46")


async def test_failed_send_is_retried_and_progress_is_sent_once(store):
    class FlakyBus(InMemoryEventBus):
        fail = True

        async def publish(self, events):
            if self.fail:
                self.fail = False
                raise RuntimeError("EventBridge throttled")
            await super().publish(events)

    bus = FlakyBus()
    processor = StreakProcessor(store, bus)
    event = completed(START)
    with pytest.raises(RuntimeError):
        await processor.handle(event)
    await processor.handle(event)  # retry by EventBridge
    assert len(bus.of_type("progress.updated")) == 1


async def test_retry_after_failed_publish_resends_saved_events_without_recounting(store):
    class FlakyBus(InMemoryEventBus):
        fail = True

        async def publish(self, events):
            if self.fail:
                self.fail = False
                raise RuntimeError("EventBridge throttled")
            await super().publish(events)

    bus = FlakyBus()
    processor = StreakProcessor(store, bus)
    for offset in range(2):
        bus.fail = False
        await processor.handle(completed(START + timedelta(days=offset)))
    third = completed(START + timedelta(days=2))  # reaches a 3-day streak: milestone + on_a_roll
    bus.fail = True
    with pytest.raises(RuntimeError):
        await processor.handle(third)
    await processor.handle(third)  # retry
    await processor.handle(third)  # a late duplicate after success is still skipped

    stats = await store.get(f"USER#{USER}", "STATS")
    assert stats["total"] == 3
    day = await store.get(f"USER#{USER}", f"DAY#{START + timedelta(days=2)}")
    assert day["completions"] == 1
    team_day = await store.get(f"TEAM#{TEAM}", f"DAY#{START + timedelta(days=2)}")
    assert team_day["completions"] == 1
    assert [e.data["streak"] for e in bus.of_type("streak.milestone")] == [3]
    assert [e.data["code"] for e in bus.of_type("badge.awarded")].count("on_a_roll") == 1
    assert len(bus.of_type("progress.updated")) == 3


class InterceptingStore:
    """Wraps a store; ``before_transact`` runs once, just before the first ``transact`` call."""

    def __init__(self, inner, before_transact):
        self.inner, self.before_transact = inner, before_transact

    def __getattr__(self, name):
        return getattr(self.inner, name)

    async def transact(self, writes):
        if self.before_transact:
            hook, self.before_transact = self.before_transact, None
            await hook()
        return await self.inner.transact(writes)


async def test_a_failed_write_saves_nothing_so_the_retry_counts_once(store, bus):
    async def fail():
        raise RuntimeError("DynamoDB throttled")

    processor = StreakProcessor(store, bus)
    for offset in range(2):
        await processor.handle(completed(START + timedelta(days=offset)))
    third = completed(START + timedelta(days=2))  # reaches a 3-day streak: milestone + on_a_roll
    with pytest.raises(RuntimeError):
        await StreakProcessor(InterceptingStore(store, fail), bus).handle(third)
    assert (await store.get(f"USER#{USER}", "STATS"))["total"] == 2  # nothing of the third was saved
    assert await store.get(f"EVENT#{third.id}", "PROCESSED") is None

    await processor.handle(third)  # retry
    assert (await store.get(f"USER#{USER}", "STATS"))["total"] == 3
    assert (await store.get(f"USER#{USER}", f"DAY#{START + timedelta(days=2)}"))["completions"] == 1
    assert [e.data["streak"] for e in bus.of_type("streak.milestone")] == [3]
    assert [e.data["code"] for e in bus.of_type("badge.awarded")].count("on_a_roll") == 1
    assert (await store.get(f"USER#{USER}", f"STREAK#{HABIT}"))["current"] == 3


async def test_two_events_for_one_habit_at_the_same_moment_keep_both_dates(store, bus):
    other_day = completed(START + timedelta(days=1))

    async def other_event_wins_the_race():
        await StreakProcessor(store, bus).handle(other_day)

    processor = StreakProcessor(InterceptingStore(store, other_event_wins_the_race), bus)
    await processor.handle(completed(START))  # read the streak, then lost the race, so it plans again

    streak = await store.get(f"USER#{USER}", f"STREAK#{HABIT}")
    assert streak["dates"] == [START.isoformat(), (START + timedelta(days=1)).isoformat()]
    assert (streak["current"], streak["version"]) == (2, 2)
    assert (await store.get(f"USER#{USER}", "STATS"))["total"] == 2
    assert len(bus.of_type("progress.updated")) == 2


async def test_two_copies_of_one_event_at_the_same_moment_count_once(store, bus):
    event = completed(START)

    async def the_other_copy_finishes_first():
        await StreakProcessor(store, bus).handle(event)

    await StreakProcessor(InterceptingStore(store, the_other_copy_finishes_first), bus).handle(event)
    assert (await store.get(f"USER#{USER}", "STATS"))["total"] == 1
    assert len(bus.of_type("progress.updated")) == 1
    assert (await store.get(f"EVENT#{event.id}", "PROCESSED"))["status"] == "done"


async def test_gives_up_after_repeated_conflicts_without_saving_anything(store, bus):
    from teampulse_common.analytics_store import TransactionConflictError

    class AlwaysConflicting:
        def __init__(self, inner):
            self.inner, self.calls = inner, 0

        def __getattr__(self, name):
            return getattr(self.inner, name)

        async def transact(self, writes):
            self.calls += 1
            raise TransactionConflictError([(f"USER#{USER}", f"STREAK#{HABIT}")])

    flaky = AlwaysConflicting(store)
    with pytest.raises(RuntimeError, match="write conflict"):
        await StreakProcessor(flaky, bus).handle(completed(START))
    assert flaky.calls == 5
    assert await store.get(f"USER#{USER}", "STATS") is None
    assert bus.published == []


async def test_backfill_that_joins_two_runs_does_not_repeat_a_milestone(processor, bus):
    # Worked example A from the guide: 2-4 Nov, then 7-8 Nov, then late 5 Nov and 6 Nov.
    for offset in (0, 1, 2, 5, 6, 3, 4):
        await processor.handle(completed(START + timedelta(days=offset)))
    assert [e.data["streak"] for e in bus.of_type("streak.milestone")] == [3, 7]


async def test_a_new_run_after_a_break_announces_milestones_again(processor, bus):
    for offset in (0, 1, 2, 5, 6, 7):  # 2-4 Nov, a gap on 5-6 Nov, then 7-9 Nov
        await processor.handle(completed(START + timedelta(days=offset)))
    assert [e.data["streak"] for e in bus.of_type("streak.milestone")] == [3, 3]


def test_lambda_handler_accepts_eventbridge_and_sqs_shapes(monkeypatch):
    bus, store = InMemoryEventBus(), MemoryAnalyticsStore()
    monkeypatch.setattr(handler, "_processor", StreakProcessor(store, bus))
    envelope = completed(START)
    eventbridge_event = {
        "version": "0",
        "id": "x",
        "detail-type": "activity.completed",
        "source": "teampulse.event-tracking-service",
        "detail": envelope.model_dump(mode="json"),
    }
    assert handler.lambda_handler(eventbridge_event, None)["status"] == "ok"

    second = completed(START + timedelta(days=1))
    sqs_event = {
        "Records": [
            {
                "messageId": "m1",
                "body": json.dumps(
                    {"detail-type": "activity.completed", "detail": second.model_dump(mode="json")}
                ),
            },
            {"messageId": "m2", "body": "{not json"},
        ]
    }
    result = handler.lambda_handler(sqs_event, None)
    assert result == {"batchItemFailures": [{"itemIdentifier": "m2"}]}
    assert len(bus.of_type("progress.updated")) == 2
