"""Transport-agnostic event envelope (CloudEvents-inspired)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from teampulse_common.logging import request_id_var


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    type: str
    source: str
    version: int = 1
    time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    subject: str | None = None
    correlation_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, value: Any) -> Any:
        """Producers outside our control (e.g. EventBridge Scheduler's ``<aws.scheduler.execution-id>``)
        may send non-UUID ids. Map them deterministically (UUIDv5) so inbox de-duplication still works."""
        if isinstance(value, str):
            try:
                return uuid.UUID(value)
            except ValueError:
                return uuid.uuid5(uuid.NAMESPACE_URL, f"teampulse-event:{value}")
        return value

    @classmethod
    def create(
        cls, event_type: str, source: str, data: BaseModel | dict[str, Any], *, subject: str | None = None
    ) -> EventEnvelope:
        payload = data.model_dump(mode="json") if isinstance(data, BaseModel) else data
        return cls(
            type=event_type,
            source=source,
            data=payload,
            subject=subject,
            correlation_id=request_id_var.get(),
        )

    @classmethod
    def from_transport(cls, raw: dict[str, Any] | str | bytes) -> EventEnvelope:
        """Accept a bare envelope, or an EventBridge event (as delivered to Lambda / SQS) wrapping one."""
        body: dict[str, Any] = json.loads(raw) if isinstance(raw, str | bytes) else raw
        if "detail-type" in body and isinstance(body.get("detail"), dict):
            body = body["detail"]
        return cls.model_validate(body)

    def to_json(self) -> str:
        return self.model_dump_json()
