"""Pure-ASGI middleware: request correlation, access logging, latency metrics, security headers."""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from teampulse_common.logging import emit_metric, request_id_var, user_id_var

logger = logging.getLogger("teampulse.access")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._\-]{1,128}$")

SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-resource-policy", b"same-site"),
]


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp, *, service: str, emit_metrics: bool = False) -> None:
        self.app = app
        self.service = service
        self.emit_metrics = emit_metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        incoming = headers.get("x-request-id", "")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        rid_token = request_id_var.set(request_id)
        # Also keep a copy in the request scope. The catch-all 500 handler runs in Starlette's outermost
        # layer, after this middleware has already reset the context variable, and reads it from here.
        scope.setdefault("state", {})["request_id"] = request_id
        uid_token = user_id_var.set(None)
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                raw: list[Any] = list(message.get("headers", []))
                present = {k.lower() for k, _ in raw}
                raw.append((b"x-request-id", request_id.encode()))
                raw.extend(h for h in SECURITY_HEADERS if h[0] not in present)
                if b"cache-control" not in present:
                    raw.append((b"cache-control", b"no-store"))
                message["headers"] = raw
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            path = scope.get("path", "")
            is_health = path.startswith("/health")
            route = scope.get("route")
            log = logger.debug if is_health else logger.info
            log(
                "request.completed",
                extra={
                    "method": scope.get("method"),
                    "path": path,
                    "route": getattr(route, "path", None),
                    "status": status_code,
                    "duration_ms": duration_ms,
                },
            )
            if self.emit_metrics and not is_health:
                emit_metric(
                    self.service,
                    "RequestLatency",
                    duration_ms,
                    dimensions={"StatusClass": f"{status_code // 100}xx"},
                )
            request_id_var.reset(rid_token)
            user_id_var.reset(uid_token)
