"""TeamPulse API Gateway — the single entry point behind the ALB.

Responsibilities (cross-cutting concerns at the edge):
* prefix routing to the six services (static URLs / ECS Service Connect, or Consul discovery)
* JWT validation at the edge (services re-validate: defence in depth)
* per-upstream circuit breakers + timeouts → fast 503 problem responses
* token-bucket rate limiting (stricter for login), request body size limit
* blocks ``/internal/**``; strips hop-by-hop and spoofable headers; adds X-Forwarded-*
* correlation id propagation and structured access logs (via the shared middleware)
* aggregated Swagger UI for every service at ``/docs``
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import httpx
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from gateway.ratelimit import TokenBucketLimiter
from teampulse_common.app import create_service_app
from teampulse_common.discovery import ServiceResolver
from teampulse_common.errors import (
    PROBLEM_JSON,
    NotFoundError,
    PayloadTooLargeError,
    ServiceUnavailableError,
    TooManyRequestsError,
    UnauthorizedError,
)
from teampulse_common.logging import request_id_var, user_id_var
from teampulse_common.resilience import CircuitBreaker, CircuitOpenError, CircuitState
from teampulse_common.security import JwtVerifier
from teampulse_common.settings import ServiceSettings

logger = logging.getLogger("gateway")


class Settings(ServiceSettings):
    service_name: str = "gateway"
    identity_service_url: str = "http://localhost:8001"
    habit_service_url: str = "http://localhost:8002"
    challenge_service_url: str = "http://localhost:8003"
    event_tracking_service_url: str = "http://localhost:8004"
    insight_service_url: str = "http://localhost:8005"
    notification_service_url: str = "http://localhost:8006"
    service_discovery: Literal["static", "consul"] = "static"
    upstream_timeout_seconds: float = 10.0
    rate_limit_per_minute: int = 300
    login_rate_limit_per_minute: int = 10
    max_body_bytes: int = 1_048_576
    # How many of our own proxies stand in front of the gateway and add an address to X-Forwarded-For:
    # 1 = one proxy (nginx in Docker Compose, or the ALB alone), 2 = CloudFront + ALB (AWS),
    # 0 = ignore the header and use the TCP peer address.
    trusted_proxy_hops: int = 1


@lru_cache
def get_settings() -> Settings:
    return Settings()


@dataclass(frozen=True)
class Route:
    prefix: str
    service: str


ROUTES: tuple[Route, ...] = (
    Route("/api/v1/auth", "identity-service"),
    Route("/api/v1/users", "identity-service"),
    Route("/api/v1/teams", "identity-service"),
    Route("/.well-known", "identity-service"),
    Route("/api/v1/habits", "habit-service"),
    Route("/api/v1/activities", "event-tracking-service"),
    Route("/api/v1/challenges", "challenge-service"),
    Route("/api/v1/badge-rules", "challenge-service"),
    Route("/api/v1/insights", "insight-service"),
    Route("/api/v1/notifications", "notification-service"),
)
SERVICES = sorted({r.service for r in ROUTES})
PUBLIC_PATHS = {"/api/v1/auth/login", "/api/v1/auth/refresh", "/.well-known/jwks.json"}
LOGIN_PATHS = {"/api/v1/auth/login", "/api/v1/auth/refresh"}
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}
STRIP_REQUEST = HOP_BY_HOP | {
    "x-internal-token",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-proto",
    "origin",
    "cookie",
    "x-request-id",
}
STRIP_RESPONSE = HOP_BY_HOP | {"content-encoding", "x-request-id", "server", "date"}


def match_route(path: str) -> Route | None:
    candidates = [r for r in ROUTES if path == r.prefix or path.startswith(r.prefix + "/")]
    return max(candidates, key=lambda r: len(r.prefix), default=None)


def client_ip(request: Request, trusted_hops: int) -> str:
    """The caller's real address, for the per-IP login limit and for the services' logs.

    Each proxy adds the address it received the request from to the *end* of X-Forwarded-For. The
    caller can put anything at the start, so the first entry cannot be trusted. With N of our own
    proxies in front, the N-th entry from the end is the one our first proxy wrote: the real caller.
    """
    peer = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if trusted_hops <= 0 or not forwarded:
        return peer
    entries = [e.strip() for e in forwarded.split(",") if e.strip()]
    if not entries:
        return peer
    return entries[-trusted_hops] if len(entries) >= trusted_hops else entries[0]


def upstream_failed(response: httpx.Response) -> bool:
    """Should this answer count as a failure of the service (for its circuit breaker)?

    502 and 504 always do. A 503 does too, unless the service itself answered with the problem code
    ``dependency_unavailable``: then the service is up, and only something *it* calls is down (for
    example event tracking while habit-service is down). Opening the breaker for it would also
    block its other endpoints, such as the activity history.
    """
    if response.status_code in (502, 504):
        return True
    if response.status_code != 503:
        return False
    if not response.headers.get("content-type", "").startswith(PROBLEM_JSON):
        return True
    try:
        return response.json().get("code") != "dependency_unavailable"
    except ValueError:
        return True


class Gateway:
    def __init__(
        self, settings: Settings, verifier: JwtVerifier, transport: httpx.AsyncBaseTransport | None = None
    ):
        self.settings = settings
        self.verifier = verifier
        static = {
            "identity-service": settings.identity_service_url,
            "habit-service": settings.habit_service_url,
            "challenge-service": settings.challenge_service_url,
            "event-tracking-service": settings.event_tracking_service_url,
            "insight-service": settings.insight_service_url,
            "notification-service": settings.notification_service_url,
        }
        consul = settings.consul_url if settings.service_discovery == "consul" else None
        self.resolver = ServiceResolver(static, consul)
        self.breakers = {s: CircuitBreaker(s, failure_threshold=5, recovery_timeout=30) for s in SERVICES}
        self.client = httpx.AsyncClient(
            timeout=settings.upstream_timeout_seconds, transport=transport, follow_redirects=False
        )
        self.limiter = TokenBucketLimiter(
            settings.rate_limit_per_minute, burst=settings.rate_limit_per_minute // 3
        )
        self.login_limiter = TokenBucketLimiter(settings.login_rate_limit_per_minute)

    async def _authenticate(self, request: Request, path: str) -> str | None:
        if path in PUBLIC_PATHS:
            return None
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            raise UnauthorizedError("Missing bearer token", code="missing_token")
        claims = await self.verifier.verify(auth[7:].strip())
        user_id_var.set(str(claims["sub"]))
        return str(claims["sub"])

    def _rate_limit(self, request: Request, path: str, subject: str | None) -> dict[str, str]:
        ip = client_ip(request, self.settings.trusted_proxy_hops)
        limiter, key = (
            (self.login_limiter, f"login:{ip}")
            if path in LOGIN_PATHS
            else (self.limiter, f"user:{subject}" if subject else f"ip:{ip}")
        )
        allowed, remaining, retry_after = limiter.check(key)
        if not allowed:
            logger.warning("gateway.rate_limited", extra={"key_type": key.split(":")[0], "path": path})
            raise TooManyRequestsError(
                "Too many requests — slow down and retry shortly.",
                headers={"Retry-After": str(max(1, round(retry_after)))},
            )
        return {"X-RateLimit-Limit": str(int(limiter.capacity)), "X-RateLimit-Remaining": str(remaining)}

    async def _read_body(self, request: Request) -> bytes:
        """Read the body, but stop as soon as it is larger than the limit (413)."""
        limit = self.settings.max_body_bytes
        too_large = PayloadTooLargeError(f"Request body exceeds {limit} bytes")
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > limit:
            raise too_large  # refused before any of the body is read
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > limit:
                raise too_large  # no Content-Length (chunked upload): stop at the limit
            chunks.append(chunk)
        return b"".join(chunks)

    async def proxy(self, request: Request) -> Response:
        path = request.url.path
        if "/internal" in path.split("?")[0]:
            raise NotFoundError("Not found")
        route = match_route(path)
        if route is None:
            raise NotFoundError(f"No route for {path}")
        try:
            subject = await self._authenticate(request, path)
        except UnauthorizedError:
            # Requests with a missing or bad token count against the caller's IP bucket too, so a
            # flood of them gets 429 (slow down) like any other caller, not endless 401s.
            self._rate_limit(request, path, None)
            raise
        limit_headers = self._rate_limit(request, path, subject)

        body = await self._read_body(request)

        breaker = self.breakers[route.service]
        try:
            breaker.before_call()
        except CircuitOpenError as exc:
            raise ServiceUnavailableError(
                f"{route.service} is temporarily unavailable (circuit open)",
                headers={"Retry-After": str(max(1, round(exc.retry_after)))},
            ) from exc

        base = await self.resolver.resolve(route.service)
        headers = {k: v for k, v in request.headers.items() if k.lower() not in STRIP_REQUEST}
        headers["X-Request-ID"] = request_id_var.get() or ""
        headers["X-Forwarded-For"] = client_ip(request, self.settings.trusted_proxy_hops)
        headers["X-Forwarded-Proto"] = request.headers.get("x-forwarded-proto", request.url.scheme)
        headers["X-Forwarded-Host"] = request.headers.get("host", "")
        try:
            # The raw query string is passed on unchanged, so repeated keys (?tag=a&tag=b) keep every value.
            query = request.url.query
            url = httpx.URL(base + path, query=query.encode()) if query else httpx.URL(base + path)
            upstream = await self.client.request(request.method, url, content=body, headers=headers)
        except httpx.HTTPError as exc:
            breaker.record_failure()
            logger.warning(
                "gateway.upstream_error", extra={"upstream": route.service, "error": type(exc).__name__}
            )
            raise ServiceUnavailableError(f"{route.service} is unavailable") from exc
        if upstream_failed(upstream):
            breaker.record_failure()
        else:
            breaker.record_success()

        response_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in STRIP_RESPONSE}
        response_headers.update(limit_headers)
        return Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers)

    async def upstream_status(self, service: str) -> str:
        if self.breakers[service].state is CircuitState.OPEN:
            return "circuit_open"
        try:
            resp = await self.client.get(await self.resolver.resolve(service) + "/health/live", timeout=2)
            return "up" if resp.status_code == 200 else "down"
        except httpx.HTTPError:
            return "down"

    async def aclose(self) -> None:
        await self.client.aclose()
        await self.resolver.aclose()


def build_router(gateway_ref: dict[str, Gateway]) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/health/services", tags=["health"], summary="Downstream service status (up/down/circuit_open)"
    )
    async def services_health() -> JSONResponse:
        gw = gateway_ref["gw"]
        results = await asyncio.gather(*(gw.upstream_status(s) for s in SERVICES))
        services = dict(zip(SERVICES, results, strict=True))
        healthy = all(v == "up" for v in services.values())
        return JSONResponse(
            {"status": "ok" if healthy else "degraded", "services": services},
            status_code=200 if healthy else 503,
        )

    @router.get("/openapi/{service}.json", include_in_schema=False)
    async def service_openapi(service: str) -> Response:
        gw = gateway_ref["gw"]
        if service not in SERVICES:
            raise NotFoundError("Unknown service")
        try:
            resp = await gw.client.get(await gw.resolver.resolve(service) + "/openapi.json", timeout=5)
        except httpx.HTTPError as exc:
            raise ServiceUnavailableError(f"{service} is unavailable") from exc
        return Response(resp.content, media_type="application/json")

    @router.get("/docs", include_in_schema=False)
    async def docs() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url=f"/openapi/{SERVICES[0]}.json",
            title="TeamPulse API (via gateway)",
            swagger_ui_parameters={
                "urls": [{"url": f"/openapi/{s}.json", "name": s} for s in SERVICES],
                "urls.primaryName": "identity-service",
                "persistAuthorization": True,
                "layout": "StandaloneLayout",
            },
        )

    @router.api_route(
        "/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False
    )
    async def proxy(request: Request, full_path: str) -> Response:
        return await gateway_ref["gw"].proxy(request)

    return router


def create_app(
    settings: Settings | None = None,
    *,
    verifier: JwtVerifier | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    ref: dict[str, Gateway] = {}

    async def _close(app: FastAPI) -> None:
        await ref["gw"].aclose()

    app = create_service_app(
        settings,
        title="TeamPulse API Gateway",
        description="Single entry point: routing, edge authentication, rate limiting, circuit breaking.",
        routers=[build_router(ref)],
        verifier=verifier,
        on_shutdown=[_close],
        docs_url=None,
    )
    ref["gw"] = Gateway(settings, app.state.verifier, transport)
    app.state.gateway = ref["gw"]
    return app
