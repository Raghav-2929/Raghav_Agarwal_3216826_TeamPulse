"""Habit Service — team-shared and private wellness goals."""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI

from habit_service.api import router
from habit_service.models import Base
from habit_service.service import on_user_updated
from teampulse_common.app import create_service_app
from teampulse_common.events import EventDispatcher, EventType
from teampulse_common.events.publishers import EventPublisher
from teampulse_common.security import JwtVerifier
from teampulse_common.settings import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "habit-service"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def register_handlers(dispatcher: EventDispatcher) -> None:
    dispatcher.on(EventType.USER_UPDATED)(on_user_updated)


def create_app(
    settings: Settings | None = None,
    *,
    publisher: EventPublisher | None = None,
    verifier: JwtVerifier | None = None,
) -> FastAPI:
    return create_service_app(
        settings or get_settings(),
        title="TeamPulse Habit Service",
        description="Private and team-shared wellness goals. Private habits are visible to their owner only.",
        routers=[router],
        metadata=[Base.metadata],
        default_db_name="habits",
        register_handlers=register_handlers,
        publisher=publisher,
        verifier=verifier,
        openapi_tags=[{"name": "habits", "description": "Personal and team-shared habits"}],
    )
