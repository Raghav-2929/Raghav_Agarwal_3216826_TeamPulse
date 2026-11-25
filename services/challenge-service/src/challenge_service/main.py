"""Challenge Service — team competitions, leaderboards and badge rules."""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI

from challenge_service.api import badge_rules, challenges
from challenge_service.models import Base
from challenge_service.service import ChallengeService, apply_progress
from teampulse_common.app import create_service_app, notify_outbox
from teampulse_common.events import EventDispatcher, EventPublisher, EventType
from teampulse_common.security import JwtVerifier
from teampulse_common.settings import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "challenge-service"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def register_handlers(dispatcher: EventDispatcher) -> None:
    dispatcher.on(EventType.PROGRESS_UPDATED)(apply_progress)


async def publish_badge_rules(app: FastAPI) -> None:
    async with app.state.db.session_factory() as session:
        await ChallengeService(session, on_commit=lambda: notify_outbox(app)).seed_and_publish_rules()


def create_app(
    settings: Settings | None = None,
    *,
    publisher: EventPublisher | None = None,
    verifier: JwtVerifier | None = None,
) -> FastAPI:
    return create_service_app(
        settings or get_settings(),
        title="TeamPulse Challenge Service",
        description="Team competitions, privacy-aware leaderboards and badge rules "
        "(rules are pushed to the streak processor via `badge_rules.changed`).",
        routers=[challenges, badge_rules],
        metadata=[Base.metadata],
        default_db_name="challenges",
        register_handlers=register_handlers,
        publisher=publisher,
        verifier=verifier,
        on_startup=[publish_badge_rules],
        openapi_tags=[
            {"name": "challenges", "description": "Competitions, participation, leaderboards"},
            {"name": "badge-rules", "description": "Badge rule administration"},
        ],
    )
