"""Identity domain logic: authentication, token lifecycle, users and teams."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import NoReturn

import bcrypt
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from identity_service.config import Settings
from identity_service.models import RefreshToken, Team, User
from identity_service.schemas import (
    BCRYPT_MAX_BYTES,
    MemberOut,
    MeUpdate,
    PasswordChange,
    TeamCreate,
    TeamOut,
    TeamUpdate,
    TokenResponse,
    UserCreate,
    UserOut,
    UserUpdate,
)
from teampulse_common.db import utcnow
from teampulse_common.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    LockedError,
    NotFoundError,
    UnauthorizedError,
)
from teampulse_common.events import EventEnvelope, EventType, enqueue
from teampulse_common.events.contracts import UserRegistered, UserUpdated
from teampulse_common.pagination import Page, PageParams
from teampulse_common.security import JwtSigner, Principal, Role

logger = logging.getLogger("identity.auth")
SOURCE = "identity-service"


# --------------------------------------------------------------------------- password hashing
async def hash_password(password: str, rounds: int = 12) -> str:
    return await asyncio.to_thread(lambda: bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds)).decode())


async def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode()
    if len(raw) > BCRYPT_MAX_BYTES:
        # The password rules cap passwords at 72 bytes, so no stored password is longer, and bcrypt 5
        # raises an error for longer input. Still run one check so the reply takes the usual time.
        await asyncio.to_thread(bcrypt.checkpw, raw[:BCRYPT_MAX_BYTES], password_hash.encode())
        return False
    return await asyncio.to_thread(bcrypt.checkpw, raw, password_hash.encode())


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    # Used for unknown e-mails so response time does not reveal which accounts exist.
    return bcrypt.hashpw(b"timing-equaliser", bcrypt.gensalt(12)).decode()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def to_user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.team_name = user.team.name if user.team else None
    return out


def user_event(event_type: EventType, user: User) -> EventEnvelope:
    payload_cls = UserRegistered if event_type is EventType.USER_REGISTERED else UserUpdated
    data = payload_cls(
        user_id=user.id,
        team_id=user.team_id,
        role=user.role,
        display_name=user.full_name,
        email=user.email,
        **({"is_active": user.is_active} if payload_cls is UserUpdated else {}),
    )
    return EventEnvelope.create(event_type, SOURCE, data, subject=f"user:{user.id}")


class IdentityService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        signer: JwtSigner,
        on_commit: Callable[[], None] = lambda: None,
        bcrypt_rounds: int = 12,
    ) -> None:
        self.session = session
        self.settings = settings
        self.signer = signer
        self._on_commit = on_commit
        self._rounds = bcrypt_rounds

    async def _commit(self) -> None:
        await self.session.commit()
        self._on_commit()

    # ------------------------------------------------------------------ authentication
    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self.session.scalar(select(User).where(func.lower(User.email) == email.lower()))
        now = utcnow()
        if user is None:
            await verify_password(password, _dummy_hash())
            logger.warning(
                "auth.login_failed", extra={"event": "auth.login_failed", "reason": "unknown_user"}
            )
            raise UnauthorizedError("Invalid email or password", code="invalid_credentials")
        if user.locked_until and user.locked_until > now:
            logger.warning(
                "auth.login_failed",
                extra={"event": "auth.login_failed", "reason": "locked", "subject": str(user.id)},
            )
            raise LockedError(
                "Account temporarily locked after repeated failed sign-ins. Try again later.",
                code="account_locked",
            )
        if not await verify_password(password, user.password_hash) or not user.is_active:
            user.failed_login_attempts += 1
            reason = "inactive" if not user.is_active else "bad_password"
            if user.failed_login_attempts >= self.settings.max_failed_logins:
                user.locked_until = now + timedelta(minutes=self.settings.lockout_minutes)
                user.failed_login_attempts = 0
                reason = "locked_out"
            await self.session.commit()
            logger.warning(
                "auth.login_failed",
                extra={"event": "auth.login_failed", "reason": reason, "subject": str(user.id)},
            )
            raise UnauthorizedError("Invalid email or password", code="invalid_credentials")

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        response = await self._issue_tokens(user)
        await self.session.commit()
        logger.info("auth.login_succeeded", extra={"event": "auth.login_succeeded", "subject": str(user.id)})
        return response

    async def _issue_tokens(self, user: User) -> TokenResponse:
        managed = (await self.session.scalars(select(Team.id).where(Team.manager_id == user.id))).all()
        claims = {
            "name": user.full_name,
            "email": user.email,
            "role": user.role,
            "team_id": str(user.team_id) if user.team_id else None,
            "team_name": user.team.name if user.team else None,
            "managed_team_ids": [str(t) for t in managed],
        }
        ttl = timedelta(seconds=self.settings.access_token_ttl_seconds)
        access = self.signer.sign(str(user.id), claims, ttl)
        refresh = secrets.token_urlsafe(48)
        self.session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=_hash_token(refresh),
                expires_at=utcnow() + timedelta(days=self.settings.refresh_token_ttl_days),
            )
        )
        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=self.settings.access_token_ttl_seconds,
            user=to_user_out(user),
        )

    async def refresh(self, token: str) -> TokenResponse:
        stored = await self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == _hash_token(token))
        )
        now = utcnow()
        if stored is None:
            raise UnauthorizedError("Invalid refresh token", code="invalid_refresh_token")
        if stored.revoked_at is not None:
            # A rotated token was replayed → assume theft, revoke every session of this user.
            await self._reuse_detected(stored.user_id, now)
        if stored.expires_at <= now:
            raise UnauthorizedError("Refresh token expired", code="invalid_refresh_token")
        user = await self.session.get(User, stored.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("Account disabled", code="invalid_refresh_token")
        # Revoke the old token with one conditional UPDATE. If two refreshes with the same token run
        # at the same moment, both can pass the check above, but only one UPDATE finds the token still
        # active. The other one is treated like any replay of a used token.
        rotated = await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.id == stored.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        if rotated.rowcount != 1:  # type: ignore[attr-defined]
            user_id = user.id  # read before the rollback expires the loaded objects
            await self.session.rollback()
            await self._reuse_detected(user_id, now)
        response = await self._issue_tokens(user)
        await self.session.commit()
        return response

    async def _reuse_detected(self, user_id: uuid.UUID, now: datetime) -> NoReturn:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self.session.commit()
        logger.warning(
            "auth.refresh_reuse_detected",
            extra={"event": "auth.login_failed", "reason": "refresh_reuse", "subject": str(user_id)},
        )
        raise UnauthorizedError(
            "Refresh token reuse detected; please sign in again", code="invalid_refresh_token"
        )

    async def logout(self, token: str, principal: Principal) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == _hash_token(token),
                RefreshToken.user_id == principal.user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=utcnow())
        )
        await self.session.commit()

    # ------------------------------------------------------------------ users
    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def update_me(self, principal: Principal, data: MeUpdate) -> UserOut:
        user = await self.get_user(principal.user_id)
        user.full_name = data.full_name
        enqueue(self.session, user_event(EventType.USER_UPDATED, user))
        await self._commit()
        return to_user_out(user)

    async def change_password(self, principal: Principal, data: PasswordChange) -> None:
        user = await self.get_user(principal.user_id)
        if not await verify_password(data.current_password, user.password_hash):
            raise BadRequestError("Current password is incorrect", code="invalid_current_password")
        user.password_hash = await hash_password(data.new_password, self._rounds)
        # Changing the password signs out every other session.
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        await self.session.commit()

    async def list_users(
        self, *, role: Role | None, team_id: uuid.UUID | None, search: str | None, page: PageParams
    ) -> Page[UserOut]:
        stmt = select(User)
        if role:
            stmt = stmt.where(User.role == role.value)
        if team_id:
            stmt = stmt.where(User.team_id == team_id)
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(or_(func.lower(User.full_name).like(like), func.lower(User.email).like(like)))
        total = await self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        users = (
            await self.session.scalars(stmt.order_by(User.full_name).offset(page.offset).limit(page.size))
        ).all()
        return Page(items=[to_user_out(u) for u in users], total=total, page=page.page, size=page.size)

    async def _ensure_team(self, team_id: uuid.UUID | None) -> None:
        if team_id and await self.session.get(Team, team_id) is None:
            raise BadRequestError("Team does not exist", code="unknown_team")

    async def create_user(self, data: UserCreate) -> UserOut:
        if await self.session.scalar(select(User.id).where(func.lower(User.email) == data.email.lower())):
            raise ConflictError("A user with this email already exists", code="email_taken")
        await self._ensure_team(data.team_id)
        user = User(
            email=data.email.lower(),
            full_name=data.full_name,
            role=data.role.value,
            team_id=data.team_id,
            password_hash=await hash_password(data.password, self._rounds),
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user, ["team"])
        enqueue(self.session, user_event(EventType.USER_REGISTERED, user))
        await self._commit()
        return to_user_out(user)

    async def update_user(self, user_id: uuid.UUID, data: UserUpdate, principal: Principal) -> UserOut:
        user = await self.get_user(user_id)
        changes = data.model_dump(exclude_unset=True)
        if user.id == principal.user_id and (
            changes.get("is_active") is False or changes.get("role", Role.ADMIN) != Role.ADMIN
        ):
            raise BadRequestError(
                "Administrators cannot demote or deactivate themselves", code="self_lockout"
            )
        if "team_id" in changes:
            await self._ensure_team(changes["team_id"])
        for field, value in changes.items():
            setattr(user, field, value.value if isinstance(value, Role) else value)
        if changes.get("is_active") is False:
            await self.session.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=utcnow())
            )
        await self.session.flush()
        await self.session.refresh(user, ["team"])
        enqueue(self.session, user_event(EventType.USER_UPDATED, user))
        await self._commit()
        return to_user_out(user)

    # ------------------------------------------------------------------ teams
    async def _team_out(self, team: Team) -> TeamOut:
        count = await self.session.scalar(
            select(func.count(User.id)).where(User.team_id == team.id, User.is_active.is_(True))
        )
        return TeamOut(
            id=team.id,
            name=team.name,
            description=team.description,
            manager_id=team.manager_id,
            manager_name=team.manager.full_name if team.manager else None,
            member_count=count or 0,
        )

    async def list_teams(self) -> list[TeamOut]:
        teams = (await self.session.scalars(select(Team).order_by(Team.name))).unique().all()
        return [await self._team_out(t) for t in teams]

    async def _validate_manager(self, manager_id: uuid.UUID | None) -> None:
        if manager_id is None:
            return
        manager = await self.session.get(User, manager_id)
        if manager is None or manager.role not in (Role.MANAGER.value, Role.ADMIN.value):
            raise BadRequestError(
                "Team manager must be an existing user with the manager role", code="invalid_manager"
            )

    async def _ensure_team_name_free(self, name: str, *, except_id: uuid.UUID | None = None) -> None:
        stmt = select(Team.id).where(func.lower(Team.name) == name.lower())
        if except_id is not None:
            stmt = stmt.where(Team.id != except_id)
        if await self.session.scalar(stmt):
            raise ConflictError("A team with this name already exists", code="team_name_taken")

    async def create_team(self, data: TeamCreate) -> TeamOut:
        await self._ensure_team_name_free(data.name)
        await self._validate_manager(data.manager_id)
        team = Team(name=data.name, description=data.description, manager_id=data.manager_id)
        self.session.add(team)
        await self.session.commit()
        await self.session.refresh(team, ["manager"])
        return await self._team_out(team)

    async def update_team(self, team_id: uuid.UUID, data: TeamUpdate) -> TeamOut:
        team = await self.session.get(Team, team_id)
        if team is None:
            raise NotFoundError("Team not found")
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes:
            await self._ensure_team_name_free(changes["name"], except_id=team.id)
        if "manager_id" in changes:
            await self._validate_manager(changes["manager_id"])
        for field, value in changes.items():
            setattr(team, field, value)
        await self.session.commit()
        await self.session.refresh(team, ["manager"])
        return await self._team_out(team)

    async def team_members(self, team_id: uuid.UUID, principal: Principal) -> list[MemberOut]:
        if not (principal.is_admin or principal.manages(team_id)):
            raise ForbiddenError("Only the team's manager or an administrator can list its members")
        if await self.session.get(Team, team_id) is None:
            raise NotFoundError("Team not found")
        users = (
            await self.session.scalars(
                select(User).where(User.team_id == team_id, User.is_active.is_(True)).order_by(User.full_name)
            )
        ).all()
        return [MemberOut(id=u.id, full_name=u.full_name, role=Role(u.role)) for u in users]


def now_utc() -> datetime:
    return datetime.now(UTC)
