from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from habit_service.schemas import HabitCreate, HabitOut, HabitUpdate, Visibility
from habit_service.service import HabitService
from teampulse_common.db import SessionDep
from teampulse_common.events.contracts import Category
from teampulse_common.pagination import Page, PageDep
from teampulse_common.security import CurrentPrincipal


def get_service(session: SessionDep) -> HabitService:
    return HabitService(session)


Service = Annotated[HabitService, Depends(get_service)]
router = APIRouter(prefix="/api/v1/habits", tags=["habits"])
Search = Annotated[str | None, Query(max_length=80)]


@router.get("", response_model=Page[HabitOut], summary="My habits (private + team-shared)")
async def list_my_habits(
    principal: CurrentPrincipal,
    service: Service,
    page: PageDep,
    category: Category | None = None,
    visibility: Visibility | None = None,
    include_archived: bool = False,
    search: Search = None,
) -> Page[HabitOut]:
    return await service.list_mine(
        principal,
        category=category,
        visibility=visibility,
        include_archived=include_archived,
        search=search,
        page=page,
    )


@router.post("", response_model=HabitOut, status_code=status.HTTP_201_CREATED, summary="Create a habit")
async def create_habit(body: HabitCreate, principal: CurrentPrincipal, service: Service) -> HabitOut:
    return await service.create(principal, body)


@router.get("/team", response_model=Page[HabitOut], summary="Teammates' habits they chose to share")
async def list_team_habits(
    principal: CurrentPrincipal,
    service: Service,
    page: PageDep,
    category: Category | None = None,
    search: Search = None,
) -> Page[HabitOut]:
    return await service.list_team(principal, category=category, search=search, page=page)


@router.get("/{habit_id}", response_model=HabitOut, summary="Get a habit (owner, or teammate if shared)")
async def get_habit(habit_id: uuid.UUID, principal: CurrentPrincipal, service: Service) -> HabitOut:
    return HabitOut.model_validate(await service.get_visible(principal, habit_id))


@router.patch("/{habit_id}", response_model=HabitOut, summary="Update own habit")
async def update_habit(
    habit_id: uuid.UUID, body: HabitUpdate, principal: CurrentPrincipal, service: Service
) -> HabitOut:
    return await service.update(principal, habit_id, body)


@router.delete("/{habit_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Archive own habit")
async def archive_habit(habit_id: uuid.UUID, principal: CurrentPrincipal, service: Service) -> Response:
    await service.archive(principal, habit_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
