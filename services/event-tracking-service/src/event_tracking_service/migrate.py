"""``python -m event_tracking_service.migrate`` — apply Alembic migrations (ECS one-off task in AWS)."""

from pathlib import Path

from event_tracking_service.main import get_settings
from teampulse_common.migrations import upgrade

if __name__ == "__main__":
    upgrade(Path(__file__).parent / "migrations", get_settings().resolve_database_url("event_tracking"))
