from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response, status

from identity_service.schemas import (
    LoginRequest,
    MemberOut,
    MeUpdate,
    PasswordChange,
    RefreshRequest,
    TeamCreate,
    TeamOut,
    TeamUpdate,
    TokenResponse,
    UserCreate,
    UserOut,
    UserUpdate,
)
from identity_service.service import IdentityService, to_user_out
from teampulse_common.app import notify_outbox
from teampulse_common.db import SessionDep
from teampulse_common.pagination import Page, PageDep
from teampulse_common.security import AdminPrincipal, CurrentPrincipal, Role


def get_service(request: Request, session: SessionDep) -> IdentityService:
    return IdentityService(
        session,
        request.app.state.settings,
        request.app.state.signer,
        on_commit=lambda: notify_outbox(request.app),
        bcrypt_rounds=request.app.state.bcrypt_rounds,
    )


Service = Annotated[IdentityService, Depends(get_service)]

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/v1/users", tags=["users"])
teams_router = APIRouter(prefix="/api/v1/teams", tags=["teams"])
jwks_router = APIRouter(tags=["auth"])


# ------------------------------------------------------------------------------------------ auth
@auth_router.post(
    "/login",
    response_model=TokenResponse,
    summary="Sign in with email + password",
    responses={401: {"description": "Invalid credentials"}, 423: {"description": "Account locked"}},
)
async def login(body: LoginRequest, service: Service) -> TokenResponse:
    return await service.login(body.email, body.password)


@auth_router.post(
    "/refresh", response_model=TokenResponse, summary="Rotate refresh token, get new access token"
)
async def refresh(body: RefreshRequest, service: Service) -> TokenResponse:
    return await service.refresh(body.refresh_token)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke a refresh token")
async def logout(body: RefreshRequest, principal: CurrentPrincipal, service: Service) -> Response:
    await service.logout(body.refresh_token, principal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@jwks_router.get("/.well-known/jwks.json", summary="Public signing keys (JWKS)")
async def jwks(request: Request, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = "public, max-age=300"
    return request.app.state.signer.jwks()


# ------------------------------------------------------------------------------------------ users
@users_router.get("/me", response_model=UserOut, summary="Current user profile")
async def me(principal: CurrentPrincipal, service: Service) -> UserOut:
    return to_user_out(await service.get_user(principal.user_id))


@users_router.patch("/me", response_model=UserOut, summary="Update own display name")
async def update_me(body: MeUpdate, principal: CurrentPrincipal, service: Service) -> UserOut:
    return await service.update_me(principal, body)


@users_router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT, summary="Change own password")
async def change_password(body: PasswordChange, principal: CurrentPrincipal, service: Service) -> Response:
    await service.change_password(principal, body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@users_router.get("", response_model=Page[UserOut], summary="List users (admin)")
async def list_users(
    _: AdminPrincipal,
    service: Service,
    page: PageDep,
    role: Role | None = None,
    team_id: uuid.UUID | None = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[UserOut]:
    return await service.list_users(role=role, team_id=team_id, search=search, page=page)


@users_router.post(
    "", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="Create user (admin)"
)
async def create_user(body: UserCreate, _: AdminPrincipal, service: Service) -> UserOut:
    return await service.create_user(body)


@users_router.get("/{user_id}", response_model=UserOut, summary="Get user (admin)")
async def get_user(user_id: uuid.UUID, _: AdminPrincipal, service: Service) -> UserOut:
    return to_user_out(await service.get_user(user_id))


@users_router.patch("/{user_id}", response_model=UserOut, summary="Update role / team / status (admin)")
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, principal: AdminPrincipal, service: Service
) -> UserOut:
    return await service.update_user(user_id, body, principal)


# ------------------------------------------------------------------------------------------ teams
@teams_router.get("", response_model=list[TeamOut], summary="List teams")
async def list_teams(_: CurrentPrincipal, service: Service) -> list[TeamOut]:
    return await service.list_teams()


@teams_router.post(
    "", response_model=TeamOut, status_code=status.HTTP_201_CREATED, summary="Create team (admin)"
)
async def create_team(body: TeamCreate, _: AdminPrincipal, service: Service) -> TeamOut:
    return await service.create_team(body)


@teams_router.patch("/{team_id}", response_model=TeamOut, summary="Update team / assign manager (admin)")
async def update_team(team_id: uuid.UUID, body: TeamUpdate, _: AdminPrincipal, service: Service) -> TeamOut:
    return await service.update_team(team_id, body)


@teams_router.get(
    "/{team_id}/members",
    response_model=list[MemberOut],
    summary="Team roster — names and roles only (team manager or admin)",
)
async def team_members(team_id: uuid.UUID, principal: CurrentPrincipal, service: Service) -> list[MemberOut]:
    return await service.team_members(team_id, principal)
