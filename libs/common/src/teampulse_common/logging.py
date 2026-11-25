"""Structured logging with request/trace correlation.

* ``json`` format: one JSON object per line — CloudWatch Logs Insights / ELK friendly.
* ``console`` format: compact, human readable for local development.

Correlation identifiers are carried in context variables so every log line written while handling a
request (or consuming an event) carries the same ``request_id``; when OpenTelemetry is enabled the
``trace_id``/``span_id`` are attached too.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)

_RESERVED = set(logging.LogRecord("x", logging.INFO, "x", 0, "x", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}
# Never let these leak into logs even if passed as ``extra``.
_REDACTED_KEYS = {"password", "token", "access_token", "refresh_token", "authorization", "note"}


def _trace_context() -> dict[str, str]:
    try:
        from opentelemetry import trace
    except ImportError:  # pragma: no cover - optional
        return {}
    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid:
        return {}
    return {"trace_id": format(ctx.trace_id, "032x"), "span_id": format(ctx.span_id, "016x")}


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    extras: dict[str, Any] = {}
    for key, value in record.__dict__.items():
        if key in _RESERVED or (key.startswith("_") and key != "_aws"):
            continue
        extras[key] = "***" if key.lower() in _REDACTED_KEYS else value
    return extras


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if rid := request_id_var.get():
            payload["request_id"] = rid
        if uid := user_id_var.get():
            payload["user_id"] = uid
        payload.update(_trace_context())
        payload.update(_extras(record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        rid = request_id_var.get()
        extras = {k: v for k, v in _extras(record).items() if k != "_aws"}
        tail = " ".join(f"{k}={v}" for k, v in extras.items())
        line = f"{ts} {record.levelname:<7} [{self.service}] {record.name}: {record.getMessage()}"
        if rid:
            line += f" (req={rid[:8]})"
        if tail:
            line += f" | {tail}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def configure_logging(service: str, level: str = "INFO", fmt: str = "console") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service) if fmt == "json" else ConsoleFormatter(service))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # Route uvicorn through our formatter; our middleware writes the access log.
    for name in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    for noisy in ("aiosqlite", "botocore", "boto3", "urllib3", "aiormq", "aio_pika", "httpcore", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_metrics_logger = logging.getLogger("teampulse.metrics")


def emit_metric(
    service: str,
    name: str,
    value: float,
    unit: str = "Milliseconds",
    dimensions: dict[str, str] | None = None,
    namespace: str = "TeamPulse",
) -> None:
    """Write a CloudWatch Embedded Metric Format record (picked up automatically by CloudWatch Logs)."""
    dims = {"Service": service, **(dimensions or {})}
    _metrics_logger.info(
        "metric",
        extra={
            "_aws": {
                "Timestamp": int(datetime.now(UTC).timestamp() * 1000),
                "CloudWatchMetrics": [
                    {
                        "Namespace": namespace,
                        "Dimensions": [list(dims)],
                        "Metrics": [{"Name": name, "Unit": unit}],
                    }
                ],
            },
            name: value,
            **dims,
        },
    )
