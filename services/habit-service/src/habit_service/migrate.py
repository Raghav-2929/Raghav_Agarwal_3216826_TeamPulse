"""``python -m habit_service.migrate`` — apply Alembic migrations (ECS one-off task in AWS)."""

from pathlib import Path

from habit_service.main import get_settings
from teampulse_common.migrations import upgrade

if __name__ == "__main__":
    upgrade(Path(__file__).parent / "migrations", get_settings().resolve_database_url("habits"))
