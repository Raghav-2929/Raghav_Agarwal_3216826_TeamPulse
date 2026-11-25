"""Service discovery.

* Docker Compose: every service self-registers in **Consul** with an HTTP health check; the gateway
  resolves healthy instances from Consul (client-side load balancing).
* AWS: **ECS Service Connect / Cloud Map** gives each service a stable DNS name
  (``http://habit-service:8000``) so static URLs are enough — no registry code runs there.
"""

from __future__ import annotations

import logging
import random
import time

import httpx

logger = logging.getLogger("teampulse.discovery")


class ConsulRegistration:
    def __init__(
        self, consul_url: str, service_name: str, address: str, port: int, health_path: str = "/health/live"
    ) -> None:
        self._consul = consul_url.rstrip("/")
        self.service_id = f"{service_name}-{address}-{port}"
        self._payload = {
            "ID": self.service_id,
            "Name": service_name,
            "Address": address,
            "Port": port,
            "Tags": ["teampulse", "fastapi"],
            "Check": {
                "HTTP": f"http://{address}:{port}{health_path}",
                "Interval": "10s",
                "Timeout": "2s",
                "DeregisterCriticalServiceAfter": "1m",
            },
        }

    async def register(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.put(f"{self._consul}/v1/agent/service/register", json=self._payload)
                resp.raise_for_status()
            logger.info("discovery.registered", extra={"service_id": self.service_id})
        except httpx.HTTPError as exc:
            logger.warning("discovery.register_failed", extra={"error": str(exc)})

    async def deregister(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                await client.put(f"{self._consul}/v1/agent/service/deregister/{self.service_id}")
        except httpx.HTTPError:
            logger.warning("discovery.deregister_failed")


class ServiceResolver:
    """Resolves a logical service name → base URL; Consul first (if configured), static fallback."""

    def __init__(
        self, static_urls: dict[str, str], consul_url: str | None = None, cache_ttl: float = 10.0
    ) -> None:
        self._static = static_urls
        self._consul = consul_url.rstrip("/") if consul_url else None
        self._ttl = cache_ttl
        self._cache: dict[str, tuple[float, list[str]]] = {}
        self._client = httpx.AsyncClient(timeout=2)

    async def resolve(self, service: str) -> str:
        if self._consul:
            cached = self._cache.get(service)
            if cached and time.monotonic() - cached[0] < self._ttl and cached[1]:
                return random.choice(cached[1])  # noqa: S311 - load balancing, not crypto
            try:
                resp = await self._client.get(
                    f"{self._consul}/v1/health/service/{service}", params={"passing": "true"}
                )
                resp.raise_for_status()
                urls = [f"http://{e['Service']['Address']}:{e['Service']['Port']}" for e in resp.json()]
                self._cache[service] = (time.monotonic(), urls)
                if urls:
                    return random.choice(urls)  # noqa: S311
            except httpx.HTTPError as exc:
                logger.warning("discovery.consul_unavailable", extra={"error": str(exc)})
        return self._static[service]

    async def aclose(self) -> None:
        await self._client.aclose()
