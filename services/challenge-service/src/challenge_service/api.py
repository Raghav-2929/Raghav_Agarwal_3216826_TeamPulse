from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status

from challenge_service.schemas import (
    BadgeRuleIn,
    ChallengeCreate,
    ChallengeOut,
    ChallengeStatus,
    ChallengeUpdate,
    JoinRequest,
    LeaderboardOut,
    ParticipationUpdate,
)
from challenge_service.service import ChallengeService
from teampulse_common.app import notify_outbox
from teampulse_common.db import SessionDep
from teampulse_common.events.contracts import BadgeRule, Category
from teampulse_common.pagination import Page, PageDep
from teampulse_common.security import AdminPrincipal, CurrentPrincipal, ManagerOrAdminPrincipal


def get_service(request: Request, session: SessionDep) -> ChallengeService:
    return ChallengeService(session, on_commit=lambda: notify_outbox(request.app))


Service = Annotated[ChallengeService, Depends(get_service)]
challenges = APIRouter(prefix="/api/v1/challenges", tags=["challenges"])
badge_rules = APIRouter(prefix="/api/v1/badge-rules", tags=["badge-rules"])
RuleCode = Annotated[str, Path(pattern=r"^[a-z0-9_]{3,40}$")]


@challenges.get("", response_model=Page[ChallengeOut], summary="Browse challenges (org-wide + my team)")
async def list_challenges(
    principal: CurrentPrincipal,
    service: Service,
    page: PageDep,
    status_: Annotated[ChallengeStatus | None, Query(alias="status")] = None,
    category: Category | None = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    joined: bool | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> Page[ChallengeOut]:
    return await service.list(
        principal,
        status=status_,
        category=category,
        search=search,
        joined=joined,
        date_from=date_from,
        date_to=date_to,
        page=page,
    )


@challenges.post(
    "",
    response_model=ChallengeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a challenge (manager: own team or org-wide; admin: any)",
)
async def create_challenge(
    body: ChallengeCreate, principal: ManagerOrAdminPrincipal, service: Service
) -> ChallengeOut:
    return await service.create(principal, body)


@challenges.get("/{challenge_id}", response_model=ChallengeOut, summary="Challenge details")
async def get_challenge(
    challenge_id: uuid.UUID, principal: CurrentPrincipal, service: Service
) -> ChallengeOut:
    return await service.get(principal, challenge_id)


@challenges.patch("/{challenge_id}", response_model=ChallengeOut, summary="Edit a challenge (creator/admin)")
async def update_challenge(
    challenge_id: uuid.UUID, body: ChallengeUpdate, principal: CurrentPrincipal, service: Service
) -> ChallengeOut:
    return await service.update(principal, challenge_id, body)


@challenges.delete("/{challenge_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a challenge")
async def delete_challenge(
    challenge_id: uuid.UUID, principal: CurrentPrincipal, service: Service
) -> Response:
    await service.delete(principal, challenge_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@challenges.post(
    "/{challenge_id}/join",
    response_model=ChallengeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Join a challenge",
)
async def join_challenge(
    challenge_id: uuid.UUID, principal: CurrentPrincipal, service: Service, body: JoinRequest | None = None
) -> ChallengeOut:
    return await service.join(principal, challenge_id, (body or JoinRequest()).show_on_leaderboard)


@challenges.patch(
    "/{challenge_id}/participation",
    response_model=ChallengeOut,
    summary="Show or hide my name on the leaderboard",
)
async def update_participation(
    challenge_id: uuid.UUID, body: ParticipationUpdate, principal: CurrentPrincipal, service: Service
) -> ChallengeOut:
    return await service.set_visibility(principal, challenge_id, body.show_on_leaderboard)


@challenges.delete(
    "/{challenge_id}/participation", status_code=status.HTTP_204_NO_CONTENT, summary="Leave a challenge"
)
async def leave_challenge(challenge_id: uuid.UUID, principal: CurrentPrincipal, service: Service) -> Response:
    await service.leave(principal, challenge_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@challenges.get(
    "/{challenge_id}/leaderboard",
    response_model=LeaderboardOut,
    summary="Individual + team leaderboard (opted-out participants are anonymised)",
)
async def leaderboard(
    challenge_id: uuid.UUID,
    principal: CurrentPrincipal,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> LeaderboardOut:
    return await service.leaderboard(principal, challenge_id, limit)


@badge_rules.get("", response_model=list[BadgeRule], summary="Badge rules")
async def list_rules(_: CurrentPrincipal, service: Service) -> list[BadgeRule]:
    return await service.list_rules()


@badge_rules.put("/{code}", response_model=BadgeRule, summary="Create or update a badge rule (admin)")
async def upsert_rule(code: RuleCode, body: BadgeRuleIn, _: AdminPrincipal, service: Service) -> BadgeRule:
    return await service.upsert_rule(code, body)


@badge_rules.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a badge rule (admin)")
async def delete_rule(code: RuleCode, _: AdminPrincipal, service: Service) -> Response:
    await service.delete_rule(code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
