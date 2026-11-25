"""Twelve-factor configuration shared by all services.

Configuration comes only from environment variables (or a local ``.env`` file). In AWS the ECS task
definition injects plain settings as ``environment`` and secrets (DB password, JWT private key) as
``secrets`` sourced from AWS Secrets Manager, so nothing sensitive is baked into images.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL

EventBusDriver = Literal["memory", "direct", "rabbitmq", "eventbridge", "none"]


def _split_list(value: Any) -> Any:
    """Accept JSON arrays *or* comma-separated strings for list settings."""
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            return json.loads(stripped)
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return value


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- identity of the running process
    service_name: str = "teampulse-service"
    service_version: str = "1.0.0"
    environment: Literal["local", "docker", "aws", "test"] = "local"
    host_address: str | None = None  # address registered in Consul (defaults to service name)
    port: int = 8000

    # ---- observability
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"
    metrics_emf: bool = False  # CloudWatch Embedded Metric Format lines on stdout
    otel_exporter_otlp_endpoint: str | None = None  # e.g. http://jaeger:4318

    # ---- database (either a full URL or discrete parts injected by ECS)
    database_url: str | None = None
    db_host: str | None = None
    db_port: int = 5432
    db_name: str | None = None
    db_user: str | None = None
    db_password: str | None = None
    db_ssl: str | None = None  # "require" in AWS
    db_echo: bool = False
    auto_create_schema: bool = True  # dev/test convenience; AWS runs Alembic migrations instead
    data_dir: str = ".data"

    # ---- JWT verification (every service verifies; only identity signs)
    jwt_issuer: str = "teampulse-identity"
    jwt_audience: str = "teampulse"
    jwt_jwks_url: str | None = "http://localhost:8001/.well-known/jwks.json"
    jwt_public_key: str | None = None
    jwt_leeway_seconds: int = 30

    # ---- integration events
    event_bus_driver: EventBusDriver = "memory"
    event_bus_name: str = "teampulse-events"
    event_source_prefix: str = "teampulse"
    event_routes: dict[str, list[str]] = {}
    event_queue_url: str | None = None
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    rabbitmq_exchange: str = "teampulse.events"
    internal_token: str = "local-dev-internal-token"
    outbox_poll_interval_seconds: float = 1.0

    # ---- cloud
    aws_region: str = "eu-west-1"
    aws_endpoint_url: str | None = None  # LocalStack / DynamoDB Local

    # ---- discovery & edge
    consul_url: str | None = None
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: Any) -> Any:
        return _split_list(value)

    @field_validator("event_routes", mode="before")
    @classmethod
    def _parse_routes(cls, value: Any) -> Any:
        if isinstance(value, str):
            return json.loads(value) if value.strip() else {}
        return value

    # ------------------------------------------------------------------ helpers
    @property
    def is_production_like(self) -> bool:
        return self.environment in {"aws"}

    def resolve_database_url(self, default_name: str) -> str:
        """DATABASE_URL wins; else build a Postgres URL from parts; else a local SQLite file."""
        if self.database_url:
            return self.database_url
        if self.db_host:
            return URL.create(
                "postgresql+asyncpg",
                username=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.db_port,
                database=self.db_name or default_name,
            ).render_as_string(hide_password=False)
        path = Path(self.data_dir) / f"{default_name}.db"
        return f"sqlite+aiosqlite:///{path.as_posix()}"


class AnalyticsSettings(ServiceSettings):
    """Settings for the analytics single table (streak processor writes, insight service reads)."""

    analytics_store_driver: Literal["dynamodb", "sql", "memory"] = "sql"
    analytics_table_name: str = "teampulse-analytics"
    analytics_database_url: str | None = None  # sql driver only; defaults to DATA_DIR/analytics.db
    min_cohort_size: int = 3

    def analytics_sql_url(self) -> str:
        if self.analytics_database_url:
            return self.analytics_database_url
        return f"sqlite+aiosqlite:///{(Path(self.data_dir) / 'analytics.db').as_posix()}"

    def build_analytics_store(self):  # type: ignore[no-untyped-def]
        from teampulse_common.analytics_store import build_analytics_store

        return build_analytics_store(
            self.analytics_store_driver,
            table_name=self.analytics_table_name,
            region=self.aws_region,
            endpoint_url=self.aws_endpoint_url,
            sql_url=self.analytics_sql_url(),
        )
