"""Insight Service — read model (CQRS query side) over the DynamoDB analytics table.

Individuals see their own detail; managers see *only* k-anonymised aggregates for teams they manage;
administrators see organisation-wide aggregates. Nobody can query another person's data.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Query, Request

from insight_service.aggregation import (
    BadgeOut,
    OrgInsights,
    OrgTeamSummary,
    PersonalInsights,
    StreakOut,
    TeamInsights,
    badges_from,
    personal_series,
    streaks_from,
    team_series,
)
from teampulse_common.analytics_store import AnalyticsStore
from teampulse_common.app import create_service_app
from teampulse_common.db import utcnow
from teampulse_common.errors import ForbiddenError, UnprocessableError
from teampulse_common.events.contracts import Category
from teampulse_common.security import AdminPrincipal, CurrentPrincipal, JwtVerifier
from teampulse_common.settings import AnalyticsSettings

MAX_RANGE_DAYS = 180
DEFAULT_RANGE_DAYS = 30


class Settings(AnalyticsSettings):
    service_name: str = "insight-service"


@lru_cache
def get_settings() -> Settings:
    return Settings()


class DateRange:
    def __init__(
        self,
        date_from: Annotated[
            date | None, Query(alias="from", description="Default: 29 days before `to`")
        ] = None,
        date_to: Annotated[date | None, Query(alias="to", description="Default: today (UTC)")] = None,
    ) -> None:
        self.end = date_to or utcnow().date()
        self.start = date_from or self.end - timedelta(days=DEFAULT_RANGE_DAYS - 1)
        if self.start > self.end:
            raise UnprocessableError("`from` must be on or before `to`", code="invalid_range")
        if (self.end - self.start).days + 1 > MAX_RANGE_DAYS:
            raise UnprocessableError(f"Range is limited to {MAX_RANGE_DAYS} days", code="invalid_range")

    def sk_between(self) -> tuple[str, str]:
        return f"DAY#{self.start.isoformat()}", f"DAY#{self.end.isoformat()}"


Range = Annotated[DateRange, Depends()]


def get_store(request: Request) -> AnalyticsStore:
    return request.app.state.store


Store = Annotated[AnalyticsStore, Depends(get_store)]
router = APIRouter(prefix="/api/v1/insights", tags=["insights"])


@router.get("/me", response_model=PersonalInsights, summary="My trends, streaks and badges")
async def my_insights(
    principal: CurrentPrincipal, store: Store, rng: Range, category: Category | None = None
) -> PersonalInsights:
    pk = f"USER#{principal.user_id}"
    days = await store.query(pk, sk_between=rng.sk_between())
    daily, by_category, totals = personal_series(days, rng.start, rng.end, category)
    return PersonalInsights(
        from_=rng.start,
        to=rng.end,
        totals=totals,
        daily=daily,
        by_category=by_category,
        streaks=streaks_from(await store.query(pk, sk_prefix="STREAK#"), utcnow().date()),
        badges=badges_from(await store.query(pk, sk_prefix="BADGE#")),
    )


@router.get("/me/streaks", response_model=list[StreakOut], summary="My streak per habit")
async def my_streaks(principal: CurrentPrincipal, store: Store) -> list[StreakOut]:
    return streaks_from(await store.query(f"USER#{principal.user_id}", sk_prefix="STREAK#"), utcnow().date())


@router.get("/me/badges", response_model=list[BadgeOut], summary="Badges I have earned")
async def my_badges(principal: CurrentPrincipal, store: Store) -> list[BadgeOut]:
    return badges_from(await store.query(f"USER#{principal.user_id}", sk_prefix="BADGE#"))


@router.get(
    "/teams/{team_id}",
    response_model=TeamInsights,
    summary="Aggregated, k-anonymised team trends (team manager or admin)",
)
async def team_insights(
    team_id: uuid.UUID,
    principal: CurrentPrincipal,
    store: Store,
    rng: Range,
    request: Request,
    category: Category | None = None,
) -> TeamInsights:
    if not (principal.is_admin or principal.manages(team_id)):
        raise ForbiddenError(
            "Team insights are available to that team's manager and administrators only", code="not_your_team"
        )
    k = request.app.state.settings.min_cohort_size
    items = await store.query(f"TEAM#{team_id}", sk_between=rng.sk_between())
    daily, totals, by_category, suppressed = team_series(items, rng.start, rng.end, k, category)
    return TeamInsights(
        from_=rng.start,
        to=rng.end,
        team_id=team_id,
        min_cohort_size=k,
        totals=totals,
        daily=daily,
        by_category=by_category,
        suppressed_categories=suppressed,
    )


@router.get("/org", response_model=OrgInsights, summary="Organisation-wide aggregates per team (admin)")
async def org_insights(_: AdminPrincipal, store: Store, rng: Range, request: Request) -> OrgInsights:
    k = request.app.state.settings.min_cohort_size
    index = await store.get("ORG", "TEAMS") or {}
    teams = []
    for team_id in sorted(index.get("team_ids", ())):
        items = await store.query(f"TEAM#{team_id}", sk_between=rng.sk_between())
        _, totals, _, _ = team_series(items, rng.start, rng.end, k, None)
        teams.append(OrgTeamSummary(team_id=uuid.UUID(team_id), **totals.model_dump()))
    return OrgInsights(from_=rng.start, to=rng.end, min_cohort_size=k, teams=teams)


def create_app(
    settings: Settings | None = None,
    *,
    store: AnalyticsStore | None = None,
    verifier: JwtVerifier | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    analytics = store or settings.build_analytics_store()

    async def _close(app: FastAPI) -> None:
        await app.state.store.close()

    async def _store_reachable(app: FastAPI) -> bool:
        await app.state.store.get("ORG", "TEAMS")
        return True

    app = create_service_app(
        settings,
        title="TeamPulse Insight Service",
        description="Personal analytics for employees and k-anonymised team trends for managers "
        "(reads the DynamoDB analytics table written by the streak processor).",
        routers=[router],
        verifier=verifier,
        on_shutdown=[_close],
        readiness_checks={"analytics_store": _store_reachable},
        openapi_tags=[{"name": "insights", "description": "Personal and aggregated analytics"}],
    )
    app.state.store = analytics
    return app
