"""Tests for the shared chassis: circuit breaker, retry, envelope parsing, analytics adapters,
direct-HTTP routing and outbox relay semantics."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import httpx
import pytest

from teampulse_common.analytics_store import MemoryAnalyticsStore, SqlAnalyticsStore, _from_dynamo, _to_dynamo
from teampulse_common.db import Database, OutboxEvent
from teampulse_common.events import EventEnvelope, InMemoryEventBus, OutboxRelay, enqueue
from teampulse_common.events.publishers import DirectHttpPublisher, matches
from teampulse_common.resilience import CircuitBreaker, CircuitOpenError, CircuitState, retry_async
from teampulse_common.settings import ServiceSettings
from teampulse_common.testing import sqlite_url


class TestCircuitBreaker:
    def make(self):
        now = [0.0]
        return CircuitBreaker("x", failure_threshold=2, recovery_timeout=10, clock=lambda: now[0]), now

    def test_opens_after_threshold_and_half_opens_after_timeout(self):
        breaker, now = self.make()
        breaker.record_failure()
        assert breaker.state is CircuitState.CLOSED
        breaker.record_failure()
        assert breaker.state is CircuitState.OPEN
        with pytest.raises(CircuitOpenError):
            breaker.before_call()
        now[0] = 10
        assert breaker.state is CircuitState.HALF_OPEN

    def test_half_open_allows_one_trial_then_closes_on_success(self):
        breaker, now = self.make()
        breaker.record_failure()
        breaker.record_failure()
        now[0] = 11
        breaker.before_call()
        with pytest.raises(CircuitOpenError):
            breaker.before_call()  # only one trial call at a time
        breaker.record_success()
        assert breaker.state is CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        breaker, now = self.make()
        breaker.record_failure()
        breaker.record_failure()
        now[0] = 11
        breaker.before_call()
        breaker.record_failure()
        assert breaker.state is CircuitState.OPEN

    def test_success_resets_consecutive_failures(self):
        breaker, _ = self.make()
        breaker.record_failure()
        breaker.record_success()
        breaker.record_failure()
        assert breaker.state is CircuitState.CLOSED


async def test_retry_async_retries_then_succeeds():
    attempts = {"n": 0}

    async def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ConnectionError
        return "ok"

    assert await retry_async(flaky, attempts=3, base_delay=0) == "ok"
    attempts["n"] = -10
    with pytest.raises(ConnectionError):
        await retry_async(flaky, attempts=2, base_delay=0)


def test_envelope_unwraps_eventbridge_detail():
    env = EventEnvelope(type="activity.completed", source="event-tracking-service", data={"a": 1})
    wrapped = {
        "detail-type": "activity.completed",
        "source": "teampulse.x",
        "detail": env.model_dump(mode="json"),
    }
    assert EventEnvelope.from_transport(wrapped) == env
    assert EventEnvelope.from_transport(env.to_json()) == env


@pytest.mark.parametrize(
    ("event_type", "pattern", "ok"),
    [
        ("challenge.created", "challenge.*", True),
        ("challenge.created", "*", True),
        ("activity.completed", "challenge.*", False),
        ("user.updated", "user.updated", True),
    ],
)
def test_pattern_matching(event_type, pattern, ok):
    assert matches(event_type, pattern) is ok


def test_envelope_maps_non_uuid_ids_deterministically():
    # EventBridge Scheduler fills `id` with its execution id, which is not guaranteed to be a UUID.
    raw = {"id": "scheduler-exec-42", "type": "reminder.tick", "source": "scheduler", "data": {}}
    first, second = EventEnvelope.from_transport(raw), EventEnvelope.from_transport(raw)
    assert first.id == second.id  # stable → inbox de-duplication still works
    assert EventEnvelope.from_transport({**raw, "id": "other"}).id != first.id


async def test_direct_publisher_fans_out_to_matching_subscribers_only():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(f"{request.url.host}:{request.headers['x-internal-token']}")
        return httpx.Response(202)

    publisher = DirectHttpPublisher(
        {"activity.*": ["http://processor/internal/events"], "*": ["http://notification/internal/events"]},
        "secret",
    )
    publisher._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await publisher.publish([EventEnvelope(type="activity.completed", source="t")])
    await publisher.publish([EventEnvelope(type="user.updated", source="t")])
    assert seen == ["processor:secret", "notification:secret", "notification:secret"]


@pytest.mark.parametrize("kind", ["memory", "sql"])
async def test_analytics_store_contract(kind, tmp_path):
    store = MemoryAnalyticsStore() if kind == "memory" else SqlAnalyticsStore(sqlite_url(tmp_path, "a"))
    assert await store.put_if_absent("P", "S", {"x": 1})
    assert not await store.put_if_absent("P", "S", {"x": 2})
    item = await store.increment("T", "DAY#2026-11-08", {"n": 1, "v": 2.5}, add_to_sets={"u": {"a"}})
    item = await store.increment(
        "T", "DAY#2026-11-08", {"n": 1}, add_to_sets={"u": {"a", "b"}}, set_attrs={"label": "x"}
    )
    assert (item["n"], item["v"], item["u"], item["label"]) == (2, 2.5, {"a", "b"}, "x")
    await store.put("T", "DAY#2026-11-01", {"n": 5})
    await store.put("T", "STREAK#h", {"n": 9})
    days = await store.query("T", sk_between=("DAY#2026-11-01", "DAY#2026-11-30"))
    assert [d["sk"] for d in days] == ["DAY#2026-11-01", "DAY#2026-11-08"]
    assert [d["sk"] for d in await store.query("T", sk_prefix="STREAK#")] == ["STREAK#h"]
    await store.delete("P", "S")
    assert await store.get("P", "S") is None
    await store.close()


@pytest.fixture(params=["memory", "sql", "dynamodb"])
async def any_store(request, tmp_path, monkeypatch):
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


async def test_transact_is_all_or_nothing(any_store):
    from teampulse_common.analytics_store import Increment, Put, TransactionConflictError

    s = any_store
    await s.transact(
        [
            Put("U", "STREAK#h", {"dates": ["2026-11-02"], "version": 1}, if_version=0),
            Increment("U", "STATS", {"total": 1, "value": 2.5}),
            Increment("ORG", "TEAMS", {}, add_to_sets={"team_ids": {"t1"}}),
        ]
    )
    assert (await s.get("U", "STATS"))["total"] == 1

    # A stale version fails the whole transaction: the STATS increment is not applied either.
    with pytest.raises(TransactionConflictError) as stale:
        await s.transact(
            [Increment("U", "STATS", {"total": 1}), Put("U", "STREAK#h", {"version": 2}, if_version=0)]
        )
    assert stale.value.keys == {("U", "STREAK#h")}
    assert (await s.get("U", "STATS"))["total"] == 1
    assert (await s.get("U", "STREAK#h"))["version"] == 1

    await s.transact([Put("E#1", "PROCESSED", {"status": "publishing"}, if_absent=True)])
    with pytest.raises(TransactionConflictError) as taken:
        await s.transact(
            [Put("E#1", "PROCESSED", {"status": "x"}, if_absent=True), Increment("U", "STATS", {"total": 1})]
        )
    assert taken.value.keys == {("E#1", "PROCESSED")}
    assert (await s.get("U", "STATS"))["total"] == 1
    assert (await s.get("E#1", "PROCESSED"))["status"] == "publishing"

    await s.transact(
        [
            Put("U", "STREAK#h", {"dates": [], "version": 2}, if_version=1),
            Increment("ORG", "TEAMS", {}, add_to_sets={"team_ids": {"t2"}}),
        ]
    )
    assert (await s.get("U", "STREAK#h"))["version"] == 2
    assert (await s.get("ORG", "TEAMS"))["team_ids"] == {"t1", "t2"}
    assert (await s.get("U", "STATS"))["value"] == 2.5
    with pytest.raises(ValueError, match="only once"):
        await s.transact([Increment("U", "STATS", {"total": 1}), Increment("U", "STATS", {"total": 1})])
    with pytest.raises(ValueError, match="not both"):
        Put("U", "X", {}, if_absent=True, if_version=1)


def test_dynamodb_number_conversion_round_trip():
    assert _to_dynamo({"a": 1.5, "b": [2.0]}) == {"a": Decimal("1.5"), "b": [Decimal("2.0")]}
    assert _from_dynamo({"a": Decimal("3"), "b": Decimal("1.25"), "s": {"x"}}) == {
        "a": 3,
        "b": 1.25,
        "s": {"x"},
    }


async def test_outbox_relay_publishes_once_and_retries_failures(tmp_path):
    db = Database(sqlite_url(tmp_path))
    await db.create_all()

    class DownBus(InMemoryEventBus):
        def __init__(self) -> None:
            super().__init__()
            self.down = True

        async def publish(self, events):
            if self.down:
                raise RuntimeError("broker down")
            await super().publish(events)

    bus = DownBus()
    relay = OutboxRelay(db.session_factory, bus)
    async with db.session_factory() as session:
        enqueue(session, EventEnvelope(type="a.b", source="t"), EventEnvelope(type="a.c", source="t"))
        await session.commit()
    assert await relay.run_once() == 0  # broker down → kept, attempts recorded
    bus.down = False
    async with db.session_factory() as session:
        rows = (await session.execute(OutboxEvent.__table__.select())).all()
        assert all(r.attempts == 1 and r.published_at is None for r in rows)
    results = await asyncio.gather(relay.run_once(), relay.run_once())
    assert sorted(results) == [0, 2]  # concurrent runs never double-publish
    assert [e.type for e in bus.published] == ["a.b", "a.c"]
    await db.dispose()


async def test_outbox_one_failing_event_does_not_hold_back_the_others(tmp_path, caplog):
    db = Database(sqlite_url(tmp_path))
    await db.create_all()

    class PickyBus(InMemoryEventBus):
        """A subscriber that always rejects one event type."""

        async def publish(self, events):
            if any(e.type == "bad.event" for e in events):
                raise RuntimeError("subscriber answered 400")
            await super().publish(events)

    bus = PickyBus()
    relay = OutboxRelay(db.session_factory, bus)
    async with db.session_factory() as session:
        enqueue(session, EventEnvelope(type="bad.event", source="t"))
        await session.commit()
    async with db.session_factory() as session:
        enqueue(session, EventEnvelope(type="a.b", source="t"), EventEnvelope(type="a.c", source="t"))
        await session.commit()

    assert await relay.run_once() == 2  # the two good events go out although the oldest one fails
    assert [e.type for e in bus.published] == ["a.b", "a.c"]
    for _ in range(9):
        assert await relay.run_once() == 0  # only the bad event is left; it is retried, never dropped
    async with db.session_factory() as session:
        rows = (await session.execute(OutboxEvent.__table__.select())).all()
    [bad] = [r for r in rows if r.event_type == "bad.event"]
    assert bad.published_at is None
    assert bad.attempts == 10
    assert "subscriber answered 400" in bad.last_error
    assert any(r.message == "outbox.event_stuck" for r in caplog.records)
    await db.dispose()


async def test_handler_constraint_error_is_not_mistaken_for_a_duplicate(tmp_path):
    from sqlalchemy import Column, Integer, MetaData, Table
    from sqlalchemy.exc import IntegrityError

    from teampulse_common.db import ProcessedEvent
    from teampulse_common.events import EventDispatcher

    db = Database(sqlite_url(tmp_path))
    await db.create_all()
    extra = MetaData()
    things = Table("things", extra, Column("id", Integer, primary_key=True))
    async with db.engine.begin() as conn:
        await conn.run_sync(extra.create_all)

    dispatcher = EventDispatcher("t", db.session_factory)

    @dispatcher.on("thing.added")
    async def add_thing(envelope, session):
        await session.execute(things.insert().values(id=1))

    assert await dispatcher.dispatch(EventEnvelope(type="thing.added", source="t"))
    with pytest.raises(IntegrityError):  # a second, different event breaks the handler's own constraint
        await dispatcher.dispatch(EventEnvelope(type="thing.added", source="t"))
    async with db.session_factory() as session:
        assert len((await session.execute(ProcessedEvent.__table__.select())).all()) == 1  # not marked done

    same = EventEnvelope(type="thing.added", source="t")
    async with db.session_factory() as session, session.begin():
        await session.execute(things.delete())
    assert await dispatcher.dispatch(same)
    assert await dispatcher.dispatch(same)  # a real duplicate is still skipped quietly
    await db.dispose()


def test_settings_build_postgres_url_from_parts_and_parse_lists():
    s = ServiceSettings(
        _env_file=None,
        db_host="db",
        db_user="svc",
        db_password="p@ss:word",
        db_name="habits",
        cors_origins="https://a.example, https://b.example",
    )
    assert s.resolve_database_url("x") == "postgresql+asyncpg://svc:p%40ss%3Aword@db:5432/habits"
    assert s.cors_origins == ["https://a.example", "https://b.example"]
    assert (
        ServiceSettings(_env_file=None, data_dir="d").resolve_database_url("n")
        == "sqlite+aiosqlite:///d/n.db"
    )


async def test_unexpected_error_still_returns_the_request_id(tmp_path):
    from fastapi import APIRouter

    from teampulse_common.app import create_service_app

    router = APIRouter()

    @router.get("/boom")
    async def boom() -> None:
        raise RuntimeError("a bug nobody expected")

    settings = ServiceSettings(
        _env_file=None, service_name="t", environment="test", data_dir=str(tmp_path), log_level="CRITICAL"
    )
    app = create_service_app(
        settings, title="t", description="t", routers=[router], publisher=InMemoryEventBus()
    )
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/boom", headers={"X-Request-ID": "req-500-check"})
    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == "internal_error"
    assert "a bug nobody expected" not in resp.text  # the real error stays in the log
    assert body["request_id"] == "req-500-check"
    assert resp.headers["x-request-id"] == "req-500-check"
    assert resp.headers["x-content-type-options"] == "nosniff"  # same security headers as other replies
    assert resp.headers["cache-control"] == "no-store"
