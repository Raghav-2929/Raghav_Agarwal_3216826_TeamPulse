"""Alembic helpers. Each service keeps its migrations *inside* its package so the production image
(installed non-editable) can run ``python -m <service>.migrate`` as an ECS one-off task."""

from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command, context
from alembic.config import Config
from sqlalchemy import MetaData, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

TEMPLATE = Path(__file__).parent / "alembic_script.py.mako"


def alembic_config(script_location: Path, url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(script_location))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def upgrade(script_location: Path, url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(script_location, url), revision)


def revision(script_location: Path, url: str, message: str) -> None:
    command.revision(alembic_config(script_location, url), message=message, autogenerate=True)


def run_env(target_metadata: list[MetaData]) -> None:
    """Body of every service's ``migrations/env.py``."""
    config = context.config
    url = config.get_main_option("sqlalchemy.url")

    if context.is_offline_mode():
        context.configure(url=url, target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    def _run(connection) -> None:  # type: ignore[no-untyped-def]
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()

    async def _online() -> None:
        engine = async_engine_from_config(
            config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
        )
        async with engine.connect() as connection:
            await connection.run_sync(_run)
        await engine.dispose()

    asyncio.run(_online())
