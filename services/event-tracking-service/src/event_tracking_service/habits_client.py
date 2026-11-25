"""Anti-corruption layer over the Habit Service (synchronous, circuit-breaker protected)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

import httpx

from teampulse_common.errors import ServiceUnavailableError
from teampulse_common.events.contracts import Category, Frequency
from teampulse_common.http import ServiceClient
from teampulse_common.resilience import CircuitBreaker


@dataclass(frozen=True)
class HabitSnapshot:
    id: uuid.UUID
    owner_id: uuid.UUID
    category: Category
    frequency: Frequency
    target_per_period: int
    is_archived: bool


class HabitLookup(Protocol):
    async def get_habit(self, habit_id: uuid.UUID, token: str) -> HabitSnapshot | None: ...
    async def aclose(self) -> None: ...


class HttpHabitLookup:
    """Forwards the caller's own JWT, so the Habit Service applies its normal visibility rules."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 2.0,
        transport: httpx.AsyncBaseTransport | None = None,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self._client = ServiceClient(
            "habit-service",
            base_url,
            timeout=timeout,
            transport=transport,
            breaker=breaker or CircuitBreaker("habit-service", failure_threshold=5, recovery_timeout=20),
        )

    @property
    def breaker(self) -> CircuitBreaker:
        return self._client.breaker

    async def get_habit(self, habit_id: uuid.UUID, token: str) -> HabitSnapshot | None:
        resp = await self._client.get(f"/api/v1/habits/{habit_id}", token=token)
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise ServiceUnavailableError(f"habit-service answered HTTP {resp.status_code}")
        body = resp.json()
        return HabitSnapshot(
            id=uuid.UUID(body["id"]),
            owner_id=uuid.UUID(body["owner_id"]),
            category=Category(body["category"]),
            frequency=Frequency(body["frequency"]),
            target_per_period=int(body["target_per_period"]),
            is_archived=bool(body["is_archived"]),
        )

    async def aclose(self) -> None:
        await self._client.aclose()
