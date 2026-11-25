"""AWS Lambda entry point (``streak_processor.handler.lambda_handler``).

Invoked by an EventBridge rule (one event per invocation; failures are retried by EventBridge and then
sent to the Lambda DLQ) or by an SQS event-source mapping (batch with partial-batch-failure reporting).
Clients are created once per execution environment and reused across warm invocations.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from streak_processor.config import get_settings
from streak_processor.processor import StreakProcessor
from teampulse_common.events import EventEnvelope, build_publisher
from teampulse_common.logging import configure_logging, request_id_var

logger = logging.getLogger("streak_processor.lambda")
_processor: StreakProcessor | None = None


def _get_processor() -> StreakProcessor:
    global _processor
    if _processor is None:
        settings = get_settings()
        configure_logging(settings.service_name, settings.log_level, "json")
        _processor = StreakProcessor(settings.build_analytics_store(), build_publisher(settings))
    return _processor


async def _process(envelope: EventEnvelope) -> None:
    token = request_id_var.set(envelope.correlation_id or f"evt-{envelope.id}")
    try:
        await _get_processor().handle(envelope)
    finally:
        request_id_var.reset(token)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    processor = _get_processor()  # noqa: F841 - warm the clients before timing starts
    if "Records" in event:  # SQS batch
        failures = []
        for record in event["Records"]:
            try:
                asyncio.run(_process(EventEnvelope.from_transport(json.loads(record["body"]))))
            except Exception:
                logger.exception("lambda.record_failed", extra={"message_id": record.get("messageId")})
                failures.append({"itemIdentifier": record["messageId"]})
        return {"batchItemFailures": failures}

    envelope = EventEnvelope.from_transport(event)  # EventBridge: detail = envelope
    asyncio.run(_process(envelope))
    logger.info(
        "lambda.processed",
        extra={
            "event_type": envelope.type,
            "event_id": str(envelope.id),
            "aws_request_id": getattr(context, "aws_request_id", None),
        },
    )
    return {"status": "ok", "event_id": str(envelope.id)}
