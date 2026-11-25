"""Event publishers — one interface, four transports (ports & adapters).

``memory``      unit tests (optionally dispatches straight into in-process dispatchers)
``direct``      zero-infrastructure local mode: HTTP POST to each subscriber's ``/internal/events``
``rabbitmq``    Docker Compose: topic exchange, routing key = event type
``eventbridge`` AWS: PutEvents onto the custom bus (``detail-type`` = event type)
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Protocol

import httpx

from teampulse_common.events.envelope import EventEnvelope

if TYPE_CHECKING:
    from teampulse_common.events.consumers import EventDispatcher
    from teampulse_common.settings import ServiceSettings

logger = logging.getLogger("teampulse.events")


class EventPublisher(Protocol):
    async def start(self) -> None: ...
    async def publish(self, events: Sequence[EventEnvelope]) -> None: ...
    async def close(self) -> None: ...


class NullPublisher:
    async def start(self) -> None:
        return None

    async def publish(self, events: Sequence[EventEnvelope]) -> None:
        for e in events:
            logger.debug("event.dropped", extra={"event_type": e.type, "event_id": str(e.id)})

    async def close(self) -> None:
        return None


class InMemoryEventBus:
    """Records events; optionally delivers them to subscribed dispatchers (integration tests)."""

    def __init__(self) -> None:
        self.published: list[EventEnvelope] = []
        self._subscribers: list[EventDispatcher] = []

    def subscribe(self, dispatcher: EventDispatcher) -> None:
        self._subscribers.append(dispatcher)

    async def start(self) -> None:
        return None

    async def publish(self, events: Sequence[EventEnvelope]) -> None:
        for event in events:
            self.published.append(event)
            for dispatcher in self._subscribers:
                await dispatcher.dispatch(event)

    def of_type(self, event_type: str) -> list[EventEnvelope]:
        return [e for e in self.published if e.type == event_type]

    def clear(self) -> None:
        self.published.clear()

    async def close(self) -> None:
        return None


def matches(event_type: str, pattern: str) -> bool:
    return pattern in ("*", "#") or fnmatch.fnmatchcase(event_type, pattern)


class DirectHttpPublisher:
    """Local stand-in for EventBridge rules: ``EVENT_ROUTES`` maps type patterns → subscriber URLs."""

    def __init__(self, routes: dict[str, list[str]], internal_token: str, timeout: float = 5.0) -> None:
        self._routes = routes
        self._token = internal_token
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(timeout=self._timeout)

    def targets_for(self, event_type: str) -> list[str]:
        urls: list[str] = []
        for pattern, targets in self._routes.items():
            if matches(event_type, pattern):
                urls.extend(t for t in targets if t not in urls)
        return urls

    async def publish(self, events: Sequence[EventEnvelope]) -> None:
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        for event in events:
            body = event.model_dump(mode="json")
            for url in self.targets_for(event.type):
                resp = await client.post(url, json=body, headers={"X-Internal-Token": self._token})
                if resp.status_code >= 300:
                    raise RuntimeError(f"subscriber {url} rejected {event.type}: HTTP {resp.status_code}")

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()


class RabbitMQPublisher:
    def __init__(self, url: str, exchange: str) -> None:
        self._url = url
        self._exchange_name = exchange
        self._connection: Any = None
        self._exchange: Any = None

    async def start(self) -> None:
        import aio_pika

        self._connection = await aio_pika.connect_robust(self._url)
        channel = await self._connection.channel(publisher_confirms=True)
        self._exchange = await channel.declare_exchange(
            self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )

    async def publish(self, events: Sequence[EventEnvelope]) -> None:
        import aio_pika

        if self._exchange is None:
            await self.start()
        for event in events:
            message = aio_pika.Message(
                body=event.to_json().encode(),
                content_type="application/json",
                message_id=str(event.id),
                type=event.type,
                correlation_id=event.correlation_id,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await self._exchange.publish(message, routing_key=event.type)

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()


class EventBridgePublisher:
    MAX_BATCH = 10

    def __init__(
        self, bus_name: str, source_prefix: str, region: str, endpoint_url: str | None = None
    ) -> None:
        import boto3

        self._bus = bus_name
        self._prefix = source_prefix
        self._client = boto3.client("events", region_name=region, endpoint_url=endpoint_url)

    async def start(self) -> None:
        return None

    async def publish(self, events: Sequence[EventEnvelope]) -> None:
        for i in range(0, len(events), self.MAX_BATCH):
            batch = events[i : i + self.MAX_BATCH]
            entries = [
                {
                    "EventBusName": self._bus,
                    "Source": f"{self._prefix}.{e.source}",
                    "DetailType": e.type,
                    "Detail": e.to_json(),
                    "Time": e.time,
                }
                for e in batch
            ]
            result = await asyncio.to_thread(self._client.put_events, Entries=entries)
            if result.get("FailedEntryCount"):
                failed = [r for r in result["Entries"] if r.get("ErrorCode")]
                raise RuntimeError(f"EventBridge rejected {len(failed)} event(s): {failed[:1]}")

    async def close(self) -> None:
        return None


def build_publisher(settings: ServiceSettings) -> EventPublisher:
    driver = settings.event_bus_driver
    if driver == "memory":
        return InMemoryEventBus()
    if driver == "direct":
        return DirectHttpPublisher(settings.event_routes, settings.internal_token)
    if driver == "rabbitmq":
        return RabbitMQPublisher(settings.rabbitmq_url, settings.rabbitmq_exchange)
    if driver == "eventbridge":
        return EventBridgePublisher(
            settings.event_bus_name,
            settings.event_source_prefix,
            settings.aws_region,
            settings.aws_endpoint_url,
        )
    return NullPublisher()
