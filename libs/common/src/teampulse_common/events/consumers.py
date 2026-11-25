"""Event consumption: handler registry + idempotent inbox + transport runners."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from teampulse_common.db import ProcessedEvent, utcnow
from teampulse_common.events.envelope import EventEnvelope
from teampulse_common.events.publishers import matches
from teampulse_common.logging import request_id_var
from teampulse_common.security import require_internal_token

logger = logging.getLogger("teampulse.events")

Handler = Callable[[EventEnvelope, AsyncSession | None], Awaitable[None]]


class _ConcurrentDuplicateError(Exception):
    """Another copy of the same event claimed its id first (inbox primary key clash)."""


class EventDispatcher:
    """Routes envelopes to handlers. With a session factory, each event is applied exactly once:
    the ``processed_events`` insert and the handler's writes commit in one transaction (inbox)."""

    def __init__(self, service: str, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        self.service = service
        self.session_factory = session_factory
        self._handlers: list[tuple[str, Handler]] = []
        self.after_commit: list[Callable[[], None]] = []

    def on(self, *patterns: str) -> Callable[[Handler], Handler]:
        def register(handler: Handler) -> Handler:
            for pattern in patterns:
                self._handlers.append((pattern, handler))
            return handler

        return register

    @property
    def patterns(self) -> list[str]:
        return sorted({p for p, _ in self._handlers})

    def handlers_for(self, event_type: str) -> list[Handler]:
        return [h for p, h in self._handlers if matches(event_type, p)]

    async def dispatch(self, envelope: EventEnvelope) -> bool:
        handlers = self.handlers_for(envelope.type)
        if not handlers:
            return False
        token = request_id_var.set(envelope.correlation_id or f"evt-{envelope.id}")
        try:
            if self.session_factory is None:
                for handler in handlers:
                    await handler(envelope, None)
            else:
                try:
                    async with self.session_factory() as session, session.begin():
                        if await session.get(ProcessedEvent, envelope.id) is not None:
                            logger.info(
                                "event.duplicate_skipped",
                                extra={"event_type": envelope.type, "event_id": str(envelope.id)},
                            )
                            return True
                        session.add(
                            ProcessedEvent(
                                event_id=envelope.id, event_type=envelope.type, processed_at=utcnow()
                            )
                        )
                        try:
                            # Claim the event id before any handler runs. A unique clash here can
                            # only mean "another copy of this event got here first". A clash inside
                            # a handler is a real error: it rolls back and goes up to the transport,
                            # which retries the event (and finally dead-letters it).
                            await session.flush()
                        except IntegrityError as exc:
                            raise _ConcurrentDuplicateError from exc
                        for handler in handlers:
                            await handler(envelope, session)
                except _ConcurrentDuplicateError:
                    logger.info("event.concurrent_duplicate", extra={"event_id": str(envelope.id)})
                    return True
                for callback in self.after_commit:
                    callback()
            logger.info("event.consumed", extra={"event_type": envelope.type, "event_id": str(envelope.id)})
            return True
        finally:
            request_id_var.reset(token)


def build_internal_events_router(dispatcher: EventDispatcher) -> APIRouter:
    router = APIRouter(tags=["internal"], include_in_schema=False)

    @router.post(
        "/internal/events",
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(require_internal_token)],
    )
    async def receive_event(body: dict[str, Any]) -> dict[str, str]:
        envelope = EventEnvelope.from_transport(body)
        handled = await dispatcher.dispatch(envelope)
        return {"status": "processed" if handled else "ignored"}

    return router


class RabbitMQConsumer:
    """Durable queue per service bound to its patterns, with a dead-letter exchange."""

    def __init__(self, url: str, exchange: str, service: str, dispatcher: EventDispatcher) -> None:
        self._url = url
        self._exchange = exchange
        self._queue = f"{exchange}.{service}"
        self._dispatcher = dispatcher
        self._connection: Any = None

    async def start(self) -> None:
        import aio_pika

        self._connection = await aio_pika.connect_robust(self._url)
        channel = await self._connection.channel()
        await channel.set_qos(prefetch_count=20)
        exchange = await channel.declare_exchange(self._exchange, aio_pika.ExchangeType.TOPIC, durable=True)
        dlx = await channel.declare_exchange(
            f"{self._exchange}.dlx", aio_pika.ExchangeType.FANOUT, durable=True
        )
        dlq = await channel.declare_queue(f"{self._queue}.dlq", durable=True)
        await dlq.bind(dlx)
        queue = await channel.declare_queue(
            self._queue, durable=True, arguments={"x-dead-letter-exchange": f"{self._exchange}.dlx"}
        )
        for pattern in self._dispatcher.patterns:
            await queue.bind(exchange, routing_key="#" if pattern == "*" else pattern)
        await queue.consume(self._on_message)
        logger.info("consumer.started", extra={"transport": "rabbitmq", "queue": self._queue})

    async def _on_message(self, message: Any) -> None:
        try:
            await self._dispatcher.dispatch(EventEnvelope.from_transport(message.body))
            await message.ack()
        except Exception:
            logger.exception("event.handler_failed", extra={"message_id": message.message_id})
            # First failure: retry once; second: dead-letter for inspection.
            if message.redelivered:
                await message.reject(requeue=False)
            else:
                await message.nack(requeue=True)

    async def stop(self) -> None:
        if self._connection:
            await self._connection.close()


class SqsConsumer:
    """AWS: EventBridge rule → SQS queue (with DLQ redrive) → long-polling consumer in the ECS task."""

    def __init__(
        self, queue_url: str, region: str, dispatcher: EventDispatcher, endpoint_url: str | None = None
    ) -> None:
        import boto3

        self._queue_url = queue_url
        self._dispatcher = dispatcher
        self._client = boto3.client("sqs", region_name=region, endpoint_url=endpoint_url)
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="sqs-consumer")
        logger.info("consumer.started", extra={"transport": "sqs", "queue": self._queue_url})

    async def _loop(self) -> None:
        while self._running:
            try:
                resp = await asyncio.to_thread(
                    self._client.receive_message,
                    QueueUrl=self._queue_url,
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=20,
                    VisibilityTimeout=60,
                )
            except Exception:
                logger.exception("consumer.receive_failed")
                await asyncio.sleep(5)
                continue
            for msg in resp.get("Messages", []):
                try:
                    await self._dispatcher.dispatch(EventEnvelope.from_transport(json.loads(msg["Body"])))
                    await asyncio.to_thread(
                        self._client.delete_message,
                        QueueUrl=self._queue_url,
                        ReceiptHandle=msg["ReceiptHandle"],
                    )
                except Exception:
                    # Left on the queue: visibility timeout → retry → DLQ after maxReceiveCount.
                    logger.exception("event.handler_failed", extra={"message_id": msg.get("MessageId")})

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
