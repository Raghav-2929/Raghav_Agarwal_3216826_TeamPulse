"""Resilient service-to-service HTTP client (timeouts, retries for idempotent calls, circuit breaker,
correlation-id propagation; W3C ``traceparent`` is injected by the OpenTelemetry httpx instrumentation)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from teampulse_common.errors import ServiceUnavailableError
from teampulse_common.logging import request_id_var
from teampulse_common.resilience import CircuitBreaker, CircuitOpenError, retry_async

logger = logging.getLogger("teampulse.http")
_IDEMPOTENT = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}


class UpstreamServerError(Exception):
    def __init__(self, response: httpx.Response) -> None:
        super().__init__(f"upstream returned HTTP {response.status_code}")
        self.response = response


class ServiceClient:
    def __init__(
        self,
        name: str,
        base_url: str,
        *,
        timeout: float = 3.0,
        retries: int = 2,
        breaker: CircuitBreaker | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.name = name
        self.breaker = breaker or CircuitBreaker(name)
        self._retries = retries
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)

    async def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        headers: dict[str, str] = {}
        if rid := request_id_var.get():
            headers["X-Request-ID"] = rid
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async def _once() -> httpx.Response:
            resp = await self._client.request(method, path, headers=headers, json=json, params=params)
            if resp.status_code >= 500:
                raise UpstreamServerError(resp)
            return resp

        async def _guarded() -> httpx.Response:
            return await self.breaker.call(_once)

        attempts = 1 + (self._retries if method.upper() in _IDEMPOTENT else 0)
        try:
            return await retry_async(
                _guarded, attempts=attempts, retry_on=(httpx.TransportError, UpstreamServerError)
            )
        except CircuitOpenError as exc:
            raise ServiceUnavailableError(
                f"{self.name} is temporarily unavailable (circuit open)", code="dependency_unavailable"
            ) from exc
        except (httpx.TransportError, UpstreamServerError) as exc:
            logger.warning("upstream.failed", extra={"upstream": self.name, "error": str(exc)})
            raise ServiceUnavailableError(
                f"{self.name} is unavailable", code="dependency_unavailable"
            ) from exc

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()
