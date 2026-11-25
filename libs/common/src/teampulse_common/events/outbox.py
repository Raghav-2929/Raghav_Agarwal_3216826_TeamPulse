"""Transactional outbox: business rows and the events describing them commit atomically; a relay
publishes pending rows afterwards. This removes the dual-write problem (DB committed but the
broker publish lost, or vice versa)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from datetime import timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from teampulse_common.db import OutboxEvent, utcnow
from teampulse_common.events.envelope import EventEnvelope
from teampulse_common.events.publishers import EventPublisher

logger = logging.getLogger("teampulse.outbox")
STUCK_AFTER_ATTEMPTS = 10  # log one ERROR line ("outbox.event_stuck") when an event fails this often


def enqueue(session: AsyncSession, *events: EventEnvelope) -> None:
    """Stage events in the caller's transaction. They are published only if it commits."""
    for event in events:
        session.add(
            OutboxEvent(
                id=event.id,
                event_type=event.type,
                payload=event.model_dump(mode="json"),
                created_at=event.time,
            )
        )


class OutboxRelay:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        publisher: EventPublisher,
        *,
        poll_interval: float = 1.0,
        batch_size: int = 50,
        retention: timedelta = timedelta(days=7),
    ) -> None:
        self._sessions = session_factory
        self._publisher = publisher
        self._poll = poll_interval
        self._batch = batch_size
        self._retention = retention
        self._wake = asyncio.Event()
        self._run_lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def notify(self) -> None:
        """Called after a commit that enqueued events → publish now instead of on the next poll."""
        self._wake.set()

    def _pending(self, lock: bool):  # type: ignore[no-untyped-def]
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at)
            .limit(self._batch)
        )
        return stmt.with_for_update(skip_locked=True) if lock else stmt

    async def _send(self, envelopes: list[EventEnvelope]) -> dict[uuid.UUID, str]:
        """Publish a batch. Returns ``{event id: error}`` for the events that could not be sent.

        If the whole batch fails, each event is tried on its own, so one event that always fails
        (for example a subscriber that rejects it) cannot hold back the events behind it. Events
        that already arrived during the failed batch may arrive twice; consumers' inboxes drop them.
        """
        try:
            await self._publisher.publish(envelopes)
            return {}
        except Exception as exc:
            if len(envelopes) == 1:
                return {envelopes[0].id: str(exc)[:500]}
        failed: dict[uuid.UUID, str] = {}
        for envelope in envelopes:
            try:
                await self._publisher.publish([envelope])
            except Exception as exc:
                failed[envelope.id] = str(exc)[:500]
        return failed

    @staticmethod
    def _log_result(
        sent_types: list[str], failed: dict[uuid.UUID, str], attempts: dict[uuid.UUID, int]
    ) -> None:
        if sent_types:
            logger.info(
                "outbox.published", extra={"count": len(sent_types), "types": sorted(set(sent_types))}
            )
        if failed:
            logger.warning(
                "outbox.publish_failed",
                extra={"pending": len(failed), "error": next(iter(failed.values()))[:200]},
            )
        for event_id, count in attempts.items():
            if count == STUCK_AFTER_ATTEMPTS:
                # The relay keeps retrying (an event is never dropped), but someone should look.
                logger.error(
                    "outbox.event_stuck",
                    extra={"event_id": str(event_id), "attempts": count, "error": failed.get(event_id)},
                )

    async def _publish_rows(self, rows: list[OutboxEvent]) -> int:
        failed = await self._send([EventEnvelope.model_validate(r.payload) for r in rows])
        now = utcnow()
        attempts: dict[uuid.UUID, int] = {}
        for row in rows:
            if row.id in failed:
                row.attempts += 1
                row.last_error = failed[row.id]
                attempts[row.id] = row.attempts
            else:
                row.published_at = now
        self._log_result([r.event_type for r in rows if r.id not in failed], failed, attempts)
        return len(rows) - len(failed)

    async def run_once(self) -> int:
        async with self._run_lock:  # one batch at a time per process (no double publish)
            return await self._run_once()

    async def _run_once(self) -> int:
        engine = self._sessions.kw["bind"]
        if engine.dialect.name == "postgresql":
            # Multiple replicas: SKIP LOCKED gives each relay a disjoint batch.
            async with self._sessions() as session, session.begin():
                rows = list((await session.scalars(self._pending(lock=True))).all())
                if not rows:
                    return 0
                return await self._publish_rows(rows)
        # SQLite (single local process): never hold a read snapshot while publishing, otherwise a
        # synchronous subscriber writing back into this database could hit SQLITE_BUSY_SNAPSHOT.
        async with self._sessions() as session:
            rows = list((await session.scalars(self._pending(lock=False))).all())
            pending = [(r.id, r.event_type, r.attempts) for r in rows]
            envelopes = [EventEnvelope.model_validate(r.payload) for r in rows]
        if not pending:
            return 0
        failed = await self._send(envelopes)
        sent_ids = [event_id for event_id, _, _ in pending if event_id not in failed]
        attempts = {event_id: n + 1 for event_id, _, n in pending if event_id in failed}
        async with self._sessions() as session, session.begin():
            if sent_ids:
                await session.execute(
                    update(OutboxEvent).where(OutboxEvent.id.in_(sent_ids)).values(published_at=utcnow())
                )
            for event_id, error in failed.items():
                await session.execute(
                    update(OutboxEvent)
                    .where(OutboxEvent.id == event_id)
                    .values(attempts=OutboxEvent.attempts + 1, last_error=error)
                )
        self._log_result([t for i, t, _ in pending if i not in failed], failed, attempts)
        return len(sent_ids)

    async def purge(self) -> None:
        async with self._sessions() as session, session.begin():
            await session.execute(
                delete(OutboxEvent).where(OutboxEvent.published_at < utcnow() - self._retention)
            )

    async def _loop(self) -> None:
        iterations = 0
        while self._running:
            published = 0
            try:
                published = await self.run_once()
                iterations += 1
                if iterations % 3600 == 0:
                    await self.purge()
            except Exception:
                logger.exception("outbox.relay_error")
            if published == self._batch:
                continue
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout=self._poll)
            self._wake.clear()

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="outbox-relay")

    async def stop(self) -> None:
        self._running = False
        self._wake.set()
        if self._task:
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait_for(self._task, timeout=5)
