"""Event Tracking Service — captures activity completions and publishes ``activity.completed``."""

from __future__ import annotations

import uuid
from datetime import date
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Query, Request, status

from event_tracking_service.habits_client import HttpHabitLookup
from event_tracking_service.models import Base
from event_tracking_service.service import ActivityCreate, ActivityOut, ActivityService
from teampulse_common.app import create_service_app, notify_outbox
from teampulse_common.db import SessionDep
from teampulse_common.events.contracts import Category
from teampulse_common.events.publishers import EventPublisher
from teampulse_common.pagination import Page, PageDep
from teampulse_common.resilience import CircuitState
from teampulse_common.security import CurrentPrincipal, JwtVerifier
from teampulse_common.settings import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "event-tracking-service"
    habit_service_url: str = "http://localhost:8002"
    activity_backfill_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_service(request: Request, session: SessionDep) -> ActivityService:
    return ActivityService(
        session,
        request.app.state.habit_lookup,
        backfill_days=request.app.state.settings.activity_backfill_days,
        on_commit=lambda: notify_outbox(request.app),
    )


Service = Annotated[ActivityService, Depends(get_service)]
router = APIRouter(prefix="/api/v1/activities", tags=["activities"])


@router.post(
    "",
    response_model=ActivityOut,
    status_code=status.HTTP_201_CREATED,
    summary="Log a habit completion",
    responses={
        404: {"description": "Habit not found / not yours"},
        409: {"description": "Already logged for that day"},
        503: {"description": "Habit Service unavailable (circuit open)"},
    },
)
async def log_activity(body: ActivityCreate, principal: CurrentPrincipal, service: Service) -> ActivityOut:
    return await service.log(principal, body)


@router.get("", response_model=Page[ActivityOut], summary="My activity history")
async def list_activities(
    principal: CurrentPrincipal,
    service: Service,
    page: PageDep,
    habit_id: uuid.UUID | None = None,
    category: Category | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> Page[ActivityOut]:
    return await service.list(
        principal, habit_id=habit_id, category=category, date_from=date_from, date_to=date_to, page=page
    )


async def _habit_service_reachable(app: FastAPI) -> bool:
    return app.state.habit_lookup.breaker.state is not CircuitState.OPEN


def create_app(
    settings: Settings | None = None,
    *,
    publisher: EventPublisher | None = None,
    verifier: JwtVerifier | None = None,
    habit_lookup=None,
) -> FastAPI:  # type: ignore[no-untyped-def]
    settings = settings or get_settings()
    lookup = habit_lookup or HttpHabitLookup(settings.habit_service_url)

    async def _close(app: FastAPI) -> None:
        await app.state.habit_lookup.aclose()

    app = create_service_app(
        settings,
        title="TeamPulse Event Tracking Service",
        description="Captures activity completions (stored in RDS) and publishes `activity.completed` "
        "through a transactional outbox.",
        routers=[router],
        metadata=[Base.metadata],
        default_db_name="event_tracking",
        publisher=publisher,
        verifier=verifier,
        on_shutdown=[_close],
        readiness_checks={"habit_service_circuit": _habit_service_reachable}
        if habit_lookup is None
        else None,
        openapi_tags=[{"name": "activities", "description": "Habit completions"}],
    )
    app.state.habit_lookup = lookup
    return app
