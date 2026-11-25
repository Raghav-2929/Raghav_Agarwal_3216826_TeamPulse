"""JWT (RS256) authentication and role-based authorization.

Only the Identity Service holds the RSA *private* key (Secrets Manager → identity task only). Every
other service — and the gateway — verifies tokens with the *public* key published at
``/.well-known/jwks.json``. A compromised downstream service therefore cannot mint tokens.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import time
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from teampulse_common.errors import ForbiddenError, UnauthorizedError
from teampulse_common.logging import user_id_var

ALGORITHM = "RS256"


class Role(StrEnum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated caller, built from verified JWT claims."""

    user_id: uuid.UUID
    role: Role
    name: str
    email: str | None = None
    team_id: uuid.UUID | None = None
    team_name: str | None = None
    managed_team_ids: frozenset[uuid.UUID] = field(default_factory=frozenset)
    token: str = field(default="", repr=False)

    @property
    def is_admin(self) -> bool:
        return self.role is Role.ADMIN

    @property
    def is_manager(self) -> bool:
        return self.role is Role.MANAGER

    def manages(self, team_id: uuid.UUID | None) -> bool:
        return team_id is not None and team_id in self.managed_team_ids

    @classmethod
    def from_claims(cls, claims: dict[str, Any], token: str = "") -> Principal:
        def _uuid(value: Any) -> uuid.UUID | None:
            return uuid.UUID(str(value)) if value else None

        return cls(
            user_id=uuid.UUID(str(claims["sub"])),
            role=Role(claims.get("role", Role.EMPLOYEE)),
            name=claims.get("name", ""),
            email=claims.get("email"),
            team_id=_uuid(claims.get("team_id")),
            team_name=claims.get("team_name"),
            managed_team_ids=frozenset(uuid.UUID(str(t)) for t in claims.get("managed_team_ids", [])),
            token=token,
        )


# --------------------------------------------------------------------------- signing (identity only)
def generate_private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


class JwtSigner:
    def __init__(self, private_key_pem: str, *, key_id: str, issuer: str, audience: str) -> None:
        self._private_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
        self.key_id = key_id
        self.issuer = issuer
        self.audience = audience

    def sign(self, subject: str, claims: dict[str, Any], ttl: timedelta, token_type: str = "access") -> str:  # noqa: S107 - claim value, not a secret
        now = datetime.now(UTC)
        payload = {
            **claims,
            "sub": subject,
            "iss": self.issuer,
            "aud": self.audience,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + ttl).timestamp()),
            "jti": uuid.uuid4().hex,
            "typ": token_type,
        }
        return jwt.encode(payload, self._private_key, algorithm=ALGORITHM, headers={"kid": self.key_id})  # type: ignore[arg-type]

    def public_key_pem(self) -> str:
        return (
            self._private_key.public_key()  # type: ignore[union-attr]
            .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
            .decode()
        )

    def jwks(self) -> dict[str, Any]:
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self._private_key.public_key()))  # type: ignore[arg-type]
        jwk.update({"kid": self.key_id, "use": "sig", "alg": ALGORITHM})
        return {"keys": [jwk]}


# --------------------------------------------------------------------------- verification (everyone)
class JwtVerifier:
    """Verifies RS256 access tokens against a static public key or a cached remote JWKS."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str | None = None,
        public_key_pem: str | None = None,
        leeway_seconds: int = 30,
        jwks_ttl_seconds: int = 600,
        http_timeout: float = 3.0,
    ) -> None:
        if not jwks_url and not public_key_pem:
            raise ValueError("JwtVerifier needs jwks_url or public_key_pem")
        self.issuer = issuer
        self.audience = audience
        self._jwks_url = jwks_url
        self._static_key = (
            serialization.load_pem_public_key(public_key_pem.encode()) if public_key_pem else None
        )
        self._leeway = leeway_seconds
        self._ttl = jwks_ttl_seconds
        self._timeout = http_timeout
        self._keys: dict[str, Any] = {}
        self._fetched_at = 0.0
        self._lock = asyncio.Lock()

    async def _refresh_jwks(self) -> None:
        assert self._jwks_url
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(self._jwks_url)
            resp.raise_for_status()
        keyset = jwt.PyJWKSet.from_dict(resp.json())
        self._keys = {k.key_id: k.key for k in keyset.keys if k.key_id}
        self._fetched_at = time.monotonic()

    async def _key_for(self, kid: str | None) -> Any:
        if self._static_key is not None:
            return self._static_key
        stale = time.monotonic() - self._fetched_at > self._ttl
        # Refetch on expiry, or on an unknown kid (key rotation) at most every 30 s.
        if stale or (kid not in self._keys and time.monotonic() - self._fetched_at > 30):
            async with self._lock:
                try:
                    await self._refresh_jwks()
                except (httpx.HTTPError, jwt.PyJWKError) as exc:
                    if not self._keys:
                        raise UnauthorizedError(
                            "Unable to validate token right now", code="jwks_unavailable"
                        ) from exc
        if kid in self._keys:
            return self._keys[kid]
        if kid is None and len(self._keys) == 1:
            return next(iter(self._keys.values()))
        raise UnauthorizedError("Unknown signing key", code="invalid_token")

    async def verify(self, token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("Malformed token", code="invalid_token") from exc
        if header.get("alg") != ALGORITHM:
            raise UnauthorizedError("Unsupported token algorithm", code="invalid_token")
        key = await self._key_for(header.get("kid"))
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[ALGORITHM],
                audience=self.audience,
                issuer=self.issuer,
                leeway=self._leeway,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise UnauthorizedError("Access token expired", code="token_expired") from exc
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("Invalid access token", code="invalid_token") from exc
        if claims.get("typ") != "access":
            raise UnauthorizedError("Not an access token", code="invalid_token")
        return claims


# --------------------------------------------------------------------------- FastAPI dependencies
_bearer = HTTPBearer(auto_error=False, description="RS256 access token from POST /api/v1/auth/login")


async def get_principal(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Missing bearer token", code="missing_token")
    verifier: JwtVerifier = request.app.state.verifier
    claims = await verifier.verify(credentials.credentials)
    principal = Principal.from_claims(claims, credentials.credentials)
    user_id_var.set(str(principal.user_id))
    request.state.principal = principal
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def require_roles(*roles: Role) -> Callable[..., Coroutine[Any, Any, Principal]]:
    allowed = set(roles)

    async def _dependency(principal: CurrentPrincipal) -> Principal:
        if principal.role not in allowed:
            raise ForbiddenError(
                f"This action requires one of the roles: {', '.join(sorted(allowed))}",
                code="insufficient_role",
            )
        return principal

    return _dependency


AdminPrincipal = Annotated[Principal, Depends(require_roles(Role.ADMIN))]
ManagerOrAdminPrincipal = Annotated[Principal, Depends(require_roles(Role.MANAGER, Role.ADMIN))]


async def require_internal_token(
    request: Request, x_internal_token: str | None = Header(default=None)
) -> None:
    """Guards service-to-service endpoints (``/internal/**``) used by the local ``direct`` event bus."""
    expected = request.app.state.settings.internal_token
    if not x_internal_token or not hmac.compare_digest(x_internal_token, expected):
        raise UnauthorizedError("Internal endpoint", code="internal_only")
