"""Identity Service — employee sign-in, RS256 token issuance (JWKS), users, teams and roles."""

from __future__ import annotations

from fastapi import FastAPI

from identity_service.api import auth_router, jwks_router, teams_router, users_router
from identity_service.config import Settings, get_settings, load_signer
from identity_service.models import Base
from identity_service.seed import seed_demo_data
from teampulse_common.app import create_service_app
from teampulse_common.events.publishers import EventPublisher
from teampulse_common.security import JwtVerifier


def create_app(
    settings: Settings | None = None, *, publisher: EventPublisher | None = None, bcrypt_rounds: int = 12
) -> FastAPI:
    settings = settings or get_settings()
    signer = load_signer(settings)
    # Identity verifies its own tokens with the in-process public key (no JWKS round trip).
    verifier = JwtVerifier(
        issuer=settings.jwt_issuer, audience=settings.jwt_audience, public_key_pem=signer.public_key_pem()
    )
    app = create_service_app(
        settings,
        title="TeamPulse Identity Service",
        description="Employee login, JWT issuance (RS256 + JWKS), refresh-token rotation, "
        "users, teams and roles.",
        routers=[auth_router, users_router, teams_router, jwks_router],
        metadata=[Base.metadata],
        default_db_name="identity",
        publisher=publisher,
        verifier=verifier,
        on_startup=[seed_demo_data],
        openapi_tags=[
            {"name": "auth", "description": "Login, token refresh/rotation, logout, JWKS"},
            {"name": "users", "description": "Profiles and user administration"},
            {"name": "teams", "description": "Teams and their managers"},
        ],
    )
    app.state.signer = signer
    app.state.bcrypt_rounds = bcrypt_rounds
    return app
