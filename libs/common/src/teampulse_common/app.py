"""Service factory: one call wires every cross-cutting concern the same way in every service."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import MetaData

from teampulse_common.db import Database
from teampulse_common.discovery import ConsulRegistration
from teampulse_common.errors import register_exception_handlers
from teampulse_common.events.consumers import (
    EventDispatcher,
    RabbitMQConsumer,
    SqsConsumer,
    build_internal_events_router,
)
from teampulse_common.events.outbox import OutboxRelay
from teampulse_common.events.publishers import EventPublisher, InMemoryEventBus, build_publisher
from teampulse_common.logging import configure_logging
from teampulse_common.middleware import RequestContextMiddleware
from teampulse_common.security import JwtVerifier
from teampulse_common.settings import ServiceSettings
from teampulse_common.tracing import setup_tracing

logger = logging.getLogger("teampulse.app")
Hook = Callable[[FastAPI], Awaitable[None]]
ReadinessCheck = Callable[[FastAPI], Awaitable[bool]]


def build_verifier(settings: ServiceSettings) -> JwtVerifier:
    return JwtVerifier(
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        jwks_url=None if settings.jwt_public_key else settings.jwt_jwks_url,
        public_key_pem=settings.jwt_public_key,
        leeway_seconds=settings.jwt_leeway_seconds,
    )


def health_router(checks: dict[str, ReadinessCheck]) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health/live", summary="Liveness probe")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/health/ready", summary="Readiness probe (dependencies reachable)")
    async def ready(request: Request) -> JSONResponse:
        results: dict[str, str] = {}
        for name, check in checks.items():
            try:
                results[name] = "up" if await check(request.app) else "down"
            except Exception:
                results[name] = "down"
        healthy = all(v == "up" for v in results.values())
        return JSONResponse(
            {"status": "ready" if healthy else "degraded", "checks": results},
            status_code=200 if healthy else 503,
        )

    return router


def create_service_app(
    settings: ServiceSettings,
    *,
    title: str,
    description: str,
    routers: Sequence[APIRouter],
    metadata: Sequence[MetaData] = (),
    default_db_name: str | None = None,
    register_handlers: Callable[[EventDispatcher], None] | None = None,
    publisher: EventPublisher | None = None,
    verifier: JwtVerifier | None = None,
    on_startup: Sequence[Hook] = (),
    on_shutdown: Sequence[Hook] = (),
    readiness_checks: dict[str, ReadinessCheck] | None = None,
    openapi_tags: list[dict[str, Any]] | None = None,
    docs_url: str | None = "/docs",
) -> FastAPI:
    configure_logging(settings.service_name, settings.log_level, settings.log_format)

    db: Database | None = None
    if metadata:
        db = Database(
            settings.resolve_database_url(default_db_name or settings.service_name),
            echo=settings.db_echo,
            ssl=settings.db_ssl,
        )
    bus = publisher or build_publisher(settings)
    relay = (
        OutboxRelay(db.session_factory, bus, poll_interval=settings.outbox_poll_interval_seconds)
        if db
        else None
    )

    dispatcher: EventDispatcher | None = None
    if register_handlers:
        dispatcher = EventDispatcher(settings.service_name, db.session_factory if db else None)
        register_handlers(dispatcher)
        if relay:
            dispatcher.after_commit.append(relay.notify)

    consumer: RabbitMQConsumer | SqsConsumer | None = None
    if dispatcher and dispatcher.patterns:
        if settings.event_bus_driver == "rabbitmq":
            consumer = RabbitMQConsumer(
                settings.rabbitmq_url, settings.rabbitmq_exchange, settings.service_name, dispatcher
            )
        elif settings.event_bus_driver == "eventbridge" and settings.event_queue_url:
            consumer = SqsConsumer(
                settings.event_queue_url, settings.aws_region, dispatcher, settings.aws_endpoint_url
            )

    registration: ConsulRegistration | None = None
    if settings.consul_url:
        registration = ConsulRegistration(
            settings.consul_url,
            settings.service_name,
            settings.host_address or settings.service_name,
            settings.port,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if db and settings.auto_create_schema:
            await db.create_all(*metadata)
        await bus.start()
        if relay:
            await relay.start()
        if consumer:
            await consumer.start()
        for hook in on_startup:
            await hook(app)
        if registration:
            await registration.register()
        logger.info(
            "service.started",
            extra={"environment": settings.environment, "event_bus": settings.event_bus_driver},
        )
        try:
            yield
        finally:
            if registration:
                await registration.deregister()
            for hook in on_shutdown:
                await hook(app)
            if consumer:
                await consumer.stop()
            if relay:
                await relay.stop()
            await bus.close()
            if db:
                await db.dispose()
            logger.info("service.stopped")

    app = FastAPI(
        title=title,
        description=description,
        version=settings.service_version,
        lifespan=lifespan,
        openapi_tags=openapi_tags,
        docs_url=docs_url,
        redoc_url="/redoc" if docs_url else None,
        swagger_ui_parameters={"persistAuthorization": True},
    )
    app.state.settings = settings
    app.state.db = db
    app.state.publisher = bus
    app.state.outbox = relay
    app.state.dispatcher = dispatcher
    app.state.verifier = verifier or build_verifier(settings)

    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(
        RequestContextMiddleware, service=settings.service_name, emit_metrics=settings.metrics_emf
    )

    checks: dict[str, ReadinessCheck] = dict(readiness_checks or {})
    if db:
        checks.setdefault("database", lambda a: a.state.db.ping())
    app.include_router(health_router(checks))
    for router in routers:
        app.include_router(router)
    if dispatcher and settings.event_bus_driver in ("direct", "memory"):
        app.include_router(build_internal_events_router(dispatcher))
    if isinstance(bus, InMemoryEventBus):
        app.state.memory_bus = bus

    setup_tracing(app, settings)
    return app


def notify_outbox(app: FastAPI) -> None:
    """Wake the relay right after a commit that enqueued events (low-latency publish)."""
    relay: OutboxRelay | None = app.state.outbox
    if relay:
        relay.notify()
