"""``python -m identity_service.migrate`` — apply Alembic migrations (ECS one-off task in AWS)."""

from pathlib import Path

from identity_service.config import get_settings
from teampulse_common.migrations import upgrade

if __name__ == "__main__":
    upgrade(Path(__file__).parent / "migrations", get_settings().resolve_database_url("identity"))
