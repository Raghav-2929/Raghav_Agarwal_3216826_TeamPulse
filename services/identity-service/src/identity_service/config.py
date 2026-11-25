from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from teampulse_common.security import JwtSigner, generate_private_key_pem
from teampulse_common.settings import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "identity-service"

    jwt_private_key: str | None = None  # PEM — injected from AWS Secrets Manager in production
    jwt_private_key_file: str | None = None
    jwt_key_id: str = "teampulse-key-1"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 7

    max_failed_logins: int = 5
    lockout_minutes: int = 15

    seed_demo_data: bool = True
    demo_password: str = "TeamPulse@2026"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_signer(settings: Settings) -> JwtSigner:
    """Private key from env/secret, or (non-AWS only) a generated key persisted under ``DATA_DIR``."""
    pem = settings.jwt_private_key
    if not pem and settings.jwt_private_key_file and Path(settings.jwt_private_key_file).exists():
        pem = Path(settings.jwt_private_key_file).read_text()
    if not pem:
        if settings.environment == "aws":
            raise RuntimeError("JWT_PRIVATE_KEY must be injected from Secrets Manager in AWS")
        key_path = Path(settings.data_dir) / "jwt-private.pem"
        if key_path.exists():
            pem = key_path.read_text()
        else:
            key_path.parent.mkdir(parents=True, exist_ok=True)
            pem = generate_private_key_pem()
            key_path.write_text(pem)
    return JwtSigner(
        pem.replace("\\n", "\n"),
        key_id=settings.jwt_key_id,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )
