"""Test helpers shared by every service's test-suite (never imported by production code)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from datetime import timedelta
from functools import lru_cache
from typing import Any

import httpx
from fastapi import FastAPI

from teampulse_common.events.outbox import OutboxRelay
from teampulse_common.security import JwtSigner, JwtVerifier, Role, generate_private_key_pem

ISSUER = "teampulse-identity"
AUDIENCE = "teampulse"


@lru_cache(maxsize=1)
def signer_for_tests() -> JwtSigner:
    return JwtSigner(generate_private_key_pem(), key_id="test-key", issuer=ISSUER, audience=AUDIENCE)


def verifier_for_tests() -> JwtVerifier:
    return JwtVerifier(issuer=ISSUER, audience=AUDIENCE, public_key_pem=signer_for_tests().public_key_pem())


def make_token(
    user_id: uuid.UUID | str | None = None,
    *,
    role: Role | str = Role.EMPLOYEE,
    name: str = "Test User",
    team_id: uuid.UUID | str | None = None,
    team_name: str | None = "Engineering",
    managed_team_ids: Iterable[uuid.UUID | str] = (),
    ttl: timedelta = timedelta(minutes=15),
    token_type: str = "access",  # noqa: S107 - claim value, not a secret
) -> str:
    claims: dict[str, Any] = {
        "name": name,
        "email": f"{name.split()[0].lower()}@teampulse.io",
        "role": str(role),
        "team_id": str(team_id) if team_id else None,
        "team_name": team_name if team_id else None,
        "managed_team_ids": [str(t) for t in managed_team_ids],
    }
    return signer_for_tests().sign(str(user_id or uuid.uuid4()), claims, ttl, token_type)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@asynccontextmanager
async def running_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Run the app's lifespan (schema creation, relays…) and yield an in-process HTTP client."""
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def flush_outbox(app: FastAPI) -> int:
    relay: OutboxRelay | None = app.state.outbox
    total = 0
    if relay:
        while (n := await relay.run_once()) > 0:
            total += n
    return total


def sqlite_url(tmp_path: Any, name: str = "test") -> str:
    """File-backed SQLite per test. (``:memory:`` + StaticPool shares ONE connection between the request
    session and background tasks such as the outbox relay, so one session's rollback could discard
    another's pending writes — a file DB gives each session its own connection, like production.)"""
    return f"sqlite+aiosqlite:///{(tmp_path / f'{name}.db').as_posix()}"
