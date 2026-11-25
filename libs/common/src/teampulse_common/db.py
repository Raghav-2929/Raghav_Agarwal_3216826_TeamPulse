"""Async SQLAlchemy plumbing shared by every service that owns a relational database.

Database-per-service: each service gets its own schema/database (``identity``, ``habits`` …) and
never reads another service's tables. Locally that is a SQLite file per service; in AWS each service
has its own database + least-privileged user on the shared RDS PostgreSQL instance.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import JSON, DateTime, MetaData, String, TypeDecorator, Uuid, event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware datetimes on every backend (SQLite drops tzinfo otherwise)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def new_metadata() -> MetaData:
    return MetaData(naming_convention=NAMING_CONVENTION)


class MessagingBase(DeclarativeBase):
    """Tables every service shares in *its own* database: transactional outbox + idempotent inbox."""

    metadata = new_metadata()


class OutboxEvent(MessagingBase):
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True, index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ProcessedEvent(MessagingBase):
    __tablename__ = "processed_events"

    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100))
    processed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Database:
    def __init__(self, url: str, *, echo: bool = False, ssl: str | None = None) -> None:
        self.url = url
        kwargs: dict[str, Any] = {"echo": echo}
        connect_args: dict[str, Any] = {}
        if url.startswith("sqlite"):
            if ":memory:" in url:
                kwargs["poolclass"] = StaticPool
            else:
                db_path = url.split("///", 1)[-1]
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            connect_args["timeout"] = 30
        else:
            kwargs.update(pool_size=5, max_overflow=10, pool_pre_ping=True, pool_recycle=1800)
            if ssl:
                connect_args["ssl"] = ssl
        self.engine: AsyncEngine = create_async_engine(url, connect_args=connect_args, **kwargs)
        if url.startswith("sqlite"):
            event.listen(self.engine.sync_engine, "connect", _sqlite_pragmas)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_all(self, *metadatas: MetaData) -> None:
        async with self.engine.begin() as conn:
            for md in (*metadatas, MessagingBase.metadata):
                await conn.run_sync(md.create_all)

    async def ping(self) -> bool:
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def dispose(self) -> None:
        await self.engine.dispose()


def _sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    db: Database = request.app.state.db
    async with db.session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
