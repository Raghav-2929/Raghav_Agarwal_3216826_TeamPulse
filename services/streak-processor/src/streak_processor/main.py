"""Local / Docker runtime for the streak processor.

The same ``StreakProcessor`` that runs inside AWS Lambda is hosted here as a small worker: it consumes
from RabbitMQ (Docker Compose) or receives ``POST /internal/events`` (zero-infra ``direct`` mode),
mirroring the EventBridge → Lambda integration.
"""

from __future__ import annotations

from fastapi import FastAPI

from streak_processor.config import Settings, get_settings
from streak_processor.processor import StreakProcessor
from teampulse_common.app import create_service_app
from teampulse_common.events import EventDispatcher, EventPublisher, EventType, build_publisher


def create_app(
    settings: Settings | None = None, *, publisher: EventPublisher | None = None, store=None
) -> FastAPI:  # type: ignore[no-untyped-def]
    settings = settings or get_settings()
    bus = publisher or build_publisher(settings)
    processor = StreakProcessor(store or settings.build_analytics_store(), bus)

    def register(dispatcher: EventDispatcher) -> None:
        @dispatcher.on(EventType.ACTIVITY_COMPLETED, EventType.BADGE_RULES_CHANGED)
        async def _handle(envelope, _session) -> None:  # type: ignore[no-untyped-def]
            await processor.handle(envelope)

    async def _close(app: FastAPI) -> None:
        await processor.store.close()

    app = create_service_app(
        settings,
        title="TeamPulse Streak Processor (local Lambda host)",
        description="Hosts the Lambda's StreakProcessor for local/Docker runs.",
        routers=[],
        register_handlers=register,
        publisher=bus,
        on_shutdown=[_close],
    )
    app.state.processor = processor
    return app
